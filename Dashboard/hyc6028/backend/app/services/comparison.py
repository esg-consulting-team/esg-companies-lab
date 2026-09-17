from app.db import get_supabase
from app.schemas_extra import (
    ComparisonResponse,
    DomainGap,
    DomainTarget,
    IntensityTrendRow,
    SectorBucket,
    SectorDistribution,
)
from app.services import diagnosis


def build_comparison(company: str) -> ComparisonResponse | None:
    summary = diagnosis.build_dashboard_summary(company)
    if summary is None:
        return None

    supabase = get_supabase()

    trend_res = (
        supabase.table("intensity_trends").select("*").eq("company", company).execute()
    )
    intensity_trend = [
        IntensityTrendRow(
            metric=r["metric"],
            unit=r.get("unit"),
            y2023=r.get("y2023"),
            y2024=r.get("y2024"),
            y2025=r.get("y2025"),
            cagr=r.get("cagr"),
            verdict=r.get("verdict"),
            formula_conflict=r.get("formula_conflict", False),
        )
        for r in (trend_res.data or [])
    ]

    domain_gap = [
        DomainGap(
            key=d.key,
            label=d.label,
            diff=round((d.achievement_rate - d.benchmark_avg) * 100, 1),
        )
        for d in summary.domains
        if d.benchmark_avg is not None and d.items > 0
    ]

    domain_targets = [
        DomainTarget(
            key=d.key,
            label=d.label,
            achieved=d.achieved,
            max_possible=d.max_possible,
            target=(d.benchmark_avg * d.max_possible) if d.benchmark_avg is not None else d.max_possible,
        )
        for d in summary.domains
        if d.items > 0
    ]

    sector_distribution = None
    meta_res = supabase.table("company_meta").select("*").eq("company", company).execute()
    meta = meta_res.data[0] if meta_res.data else {}
    bucket_res = (
        supabase.table("sector_distribution_buckets")
        .select("*")
        .eq("company", company)
        .execute()
    )
    if bucket_res.data:
        sector_distribution = SectorDistribution(
            sector_label=meta.get("sector"),
            total_companies=meta.get("sector_total_companies"),
            self_grade=summary.official_grade,
            buckets=[SectorBucket(grade=b["grade"], company_count=b["company_count"]) for b in bucket_res.data],
        )

    return ComparisonResponse(
        intensity_trend=intensity_trend,
        domain_gap=domain_gap,
        sector_distribution=sector_distribution,
        domain_targets=domain_targets,
    )
