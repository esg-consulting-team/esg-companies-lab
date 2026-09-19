// AI 상담 챗봇 전용 API 호출 — 대시보드 공용 API 클라이언트(../api/client.ts)와 분리해
// 팀원이 대시보드 엔드포인트를 추가·수정할 때 이 파일과 겹치지 않도록 한다. fetch 로직 자체는
// 중복 구현하지 않고 client.ts가 export하는 post/ApiError를 그대로 재사용한다.
import { post } from "../api/client";
import type { ChatResponse } from "./types";

export const chatApi = {
  ask: (
    company: string,
    question: string,
    itemCode?: string,
    history?: { question: string; conclusion: string }[]
  ) =>
    post<ChatResponse>("/api/chat", { company, question, itemCode: itemCode ?? null, history: history ?? null }),
};
