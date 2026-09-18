import Tooltip from "./Tooltip";

/** L1 KPI② 공식등급 옆 E/S/G 미니칩. S는 회색 + 진단범위 밖 안내 툴팁. */
export default function EsgMiniChips({ e, s, g }) {
  return (
    <span className="mini-egs">
      <span className="mini-chip mini-chip-e">E {e || "–"}</span>
      <Tooltip content="사회(S) 영역은 이번 진단 대상(E/G) 밖이라 KCGS 공식등급만 참고용으로 표시합니다.">
        <span className="mini-chip mini-chip-s">S {s || "–"}</span>
      </Tooltip>
      <span className="mini-chip mini-chip-g">G {g || "–"}</span>
    </span>
  );
}
