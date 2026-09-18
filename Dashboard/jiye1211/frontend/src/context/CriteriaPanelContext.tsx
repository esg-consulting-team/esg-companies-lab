import { createContext, useContext } from "react";

/** "평가 기준 보기" 패널을 앱바(AppShell) 밖에서도(L1 안내선 등) 열 수 있게 하는 최소 컨텍스트. */
export const CriteriaPanelContext = createContext<{ open: () => void } | null>(null);

export function useCriteriaPanel() {
  const ctx = useContext(CriteriaPanelContext);
  if (!ctx) throw new Error("useCriteriaPanel은 AppShell 하위에서만 사용할 수 있습니다.");
  return ctx;
}
