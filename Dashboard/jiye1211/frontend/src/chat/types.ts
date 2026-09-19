// AI 상담 챗봇 전용 타입 — 대시보드 공용 타입(../types.ts)과 분리해 두 파일이 서로
// 겹치지 않도록 한다(팀원이 대시보드 타입을 작업할 때 이 파일과 충돌하지 않는다).

export interface ChatCitation {
  n: number;
  doc: string;
  page?: number | null;
  snippet?: string;
  score?: number;
}

export interface ChatResponse {
  conclusion: string;
  citations: ChatCitation[];
  nextAction: string;
  insufficientEvidence: boolean;
}
