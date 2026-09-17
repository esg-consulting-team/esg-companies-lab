from app.db import get_supabase
from app.schemas_extra import RoadmapResponse, RoadmapTask, RoiRow, SimulationResponse
from app.services import diagnosis


def build_roadmap(company: str) -> RoadmapResponse | None:
    items = diagnosis.fetch_items(company)
    if not items:
        return None
    items_by_code = {r["category_code"]: r for r in items}

    supabase = get_supabase()
    curated_res = supabase.table("roadmap_tasks").select("*").eq("company", company).execute()
    curated_rows = curated_res.data or []

    if curated_rows:
        tasks = []
        for r in curated_rows:
            item = items_by_code.get(r.get("item_code")) if r.get("item_code") else None
            tasks.append(
                RoadmapTask(
                    id=str(r["id"]),
                    item_code=r.get("item_code"),
                    item_name=r.get("item_name") or (item["item_name"] if item else None),
                    lane=r["lane"],
                    task=r["task"],
                    start_month=r.get("start_month"),
                    months=r.get("months"),
                    gain=float(r.get("gain") or 0),
                    cost=r.get("cost"),
                    owner=r.get("owner"),
                    dependency=r.get("dependency"),
                    curated=True,
                )
            )
        return RoadmapResponse(tasks=tasks, has_curated_data=True)

    # 큐레이션 데이터가 없으면(예: 하나마이크론) 실데이터에서 자동 생성한다.
    tasks = []
    for r in items:
        if r.get("score") is None:
            continue
        urgency = r.get("urgency")
        if urgency not in ("즉시", "중기", "장기"):
            continue
        lost = 100 - float(r.get("score") or 0)
        if lost <= 0:
            continue
        sol = diagnosis.parse_solution(r.get("solution"))
        tasks.append(
            RoadmapTask(
                id=f"auto:{r['category_code']}",
                item_code=r["category_code"],
                item_name=r["item_name"],
                lane=urgency,
                task=(sol.direction or r["item_name"])[:200],
                start_month=None,
                months=None,
                gain=lost,
                cost=None,
                owner=None,
                dependency=None,
                curated=False,
            )
        )
    lane_order = {"즉시": 0, "중기": 1, "장기": 2}
    tasks.sort(key=lambda t: (lane_order.get(t.lane, 9), -t.gain))
    return RoadmapResponse(tasks=tasks, has_curated_data=False)


def build_roi(company: str) -> list[RoiRow]:
    supabase = get_supabase()
    res = (
        supabase.table("roadmap_tasks")
        .select("*")
        .eq("company", company)
        .not_.is_("cost", "null")
        .execute()
    )
    rows = []
    for r in res.data or []:
        gain = float(r.get("gain") or 0)
        cost = float(r.get("cost") or 0)
        if gain <= 0:
            continue
        rows.append(
            RoiRow(
                item_code=r.get("item_code"),
                task=r["task"],
                gain=gain,
                cost=cost,
                cost_per_point=round(cost / gain, 1),
            )
        )
    rows.sort(key=lambda r: r.cost_per_point)
    return rows


def simulate(company: str, task_ids: list[str]) -> SimulationResponse | None:
    """선택된 로드맵 과제들의 gain/cost/months를 그대로 합산한다.

    화면에 표시되는 값(build_roadmap 결과)과 동일한 숫자를 사용해야 사용자가
    체크한 항목과 결과가 어긋나지 않는다.
    """
    roadmap = build_roadmap(company)
    if roadmap is None:
        return None

    diagnosis_items = diagnosis.fetch_items(company)
    total_score = sum(float(r.get("score") or 0) for r in diagnosis_items if r.get("score") is not None)
    max_score = sum(100 for r in diagnosis_items if r.get("score") is not None)

    selected = {t.id: t for t in roadmap.tasks}
    gain = 0.0
    total_cost = 0.0
    cost_unknown = 0
    max_months = 0
    for task_id in task_ids:
        task = selected.get(task_id)
        if not task:
            continue
        gain += task.gain
        if task.cost is not None:
            total_cost += task.cost
        else:
            cost_unknown += 1
        if task.months:
            max_months = max(max_months, task.months)

    new_score = min(total_score + gain, max_score)
    return SimulationResponse(
        from_score=total_score,
        to_score=new_score,
        max_score=max_score,
        gain=new_score - total_score,
        rate_from=(total_score / max_score) if max_score else 0,
        rate_to=(new_score / max_score) if max_score else 0,
        total_cost=total_cost if total_cost > 0 else None,
        max_months=max_months or None,
        cost_unknown_count=cost_unknown,
        estimated=True,
    )
