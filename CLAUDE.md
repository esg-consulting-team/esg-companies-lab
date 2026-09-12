# Repository guidance for AI coding assistants

이 저장소에서 작업하는 Claude Code(또는 다른 AI 코딩 도구)는 아래 규칙을 따라야 합니다.

## 프로젝트 개요

기획서를 바탕으로 ESG 등급 데이터에 대한 EDA 작업 내역을 관리하는 저장소입니다. 각 회차 폴더(`1stEDA` ~ `4thEDA`, `Docs`) 하위는 팀원 계정명으로 구분되어 있으며, 팀원별로 자신의 작업물을 해당 폴더에 올립니다.

프로젝트는 esg-hypothesis-lab(초기 가설 탐색), esg-companies-lab(본 저장소, EDA), esg-rag-scoring(RAG 채점 파이프라인) 3개 저장소로 분리되어 있습니다. RAG 파이프라인 관련 작업은 이 저장소가 아니라 esg-rag-scoring에서 진행합니다.

## Git 워크플로

- `main`에 직접 커밋하지 말 것. 작업 전 `main`을 pull해 최신화하고, 항상 새 브랜치를 만들어 작업할 것.
- 작업이 끝나면 브랜치를 push하고 `main`을 대상으로 PR을 만들어 병합할 것.

## 커밋/PR 규칙 — AI attribution 금지

- 커밋 메시지와 PR 본문에 AI 도구가 자동으로 붙이는 attribution/트레일러(예: `Co-Authored-By: Claude`, `Claude-Session:`, `Generated with Claude Code` 등)를 **절대 포함하지 말 것.**
- 커밋하기 전에 커밋 메시지에 위와 같은 문구가 없는지 확인할 것.
- 이미 커밋된 상태라면 push 전에 `git commit --amend`로 트레일러를 제거할 것.
