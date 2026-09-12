# ESG Companies Lab

기획서를 바탕으로 ESG 등급 데이터에 대한 EDA 작업 내역을 관리하는 저장소입니다.

프로젝트는 단계별로 3개 저장소로 분리되어 있습니다.

- **esg-hypothesis-lab**: 초기 5인 가설 탐색 단계
- **esg-consulting-team/esg-companies-lab** (본 저장소): 조직 저장소, 1~4차 EDA 및 기획서
- **esg-rag-scoring**: 채점용 RAG 파이프라인, 채점기준표 및 산출물 (구 `1stRAG`에서 이관됨)

## 폴더 구조

각 회차 폴더 하위는 팀원 계정명으로 구분되어 있으며, 팀원별로 자신의 작업물을 해당 폴더에 올립니다.

```
1stEDA/  ~  4thEDA/   # 회차별 EDA 작업 (fastsloth226, hewonjin, hyc6028, jiye1211, minjukim22)
Docs/                 # 기획서, WBS 등 팀 공용 문서 (+ 팀원별 개인 문서 하위폴더)
```

- `1stEDA` ~ `4thEDA`: 회차별 EDA(탐색적 데이터 분석) 결과물.
  - `3rdEDA`: 채점표 문항과 ESG 등급 간의 상관관계 검증 (작업: fastsloth226, hewonjin)
  - `4thEDA`: 컨설팅 고객 세그먼트 기준 확정 및 컨설팅 대상 기업 선정 (작업: hyc6028, minjukim22, hewonjin)
- `Docs`: 기획서, WBS, 등급표 등 팀 공용 문서.

추후 회차가 진행되며 각 폴더에 작업물이 계속 추가될 예정입니다.

RAG 파이프라인 관련 작업은 **esg-rag-scoring** 저장소에서 진행합니다.

## 작업 방식 (Workflow)

1. 작업 시작 전 `main`을 최신화합니다.
   ```
   git checkout main
   git pull
   ```
2. 본인 작업 내용에 맞는 새 브랜치를 만듭니다. (`main`에서 직접 작업/커밋하지 않습니다)
   ```
   git checkout -b <prefix>/<작업-내용>
   ```
3. 작업 후 커밋합니다. **커밋 메시지에 AI 도구가 자동으로 붙이는 attribution(예: `Co-Authored-By: Claude`, `Claude-Session:` 등 AI 관련 트레일러)을 포함하지 않습니다.** AI 코딩 도구를 사용했다면 커밋 전에 해당 트레일러를 제거하고 커밋해 주세요.
4. 브랜치를 push하고, `main`을 대상으로 PR을 생성해 병합합니다.
   ```
   git push -u origin <브랜치명>
   ```

AI 코딩 어시스턴트(Claude Code 등)를 사용하는 경우 저장소 루트의 `CLAUDE.md`를 참고하세요.
