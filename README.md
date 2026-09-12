# ESG Companies Lab

기획서를 바탕으로 ESG 등급 데이터에 대한 EDA와, 채점용 RAG(Retrieval-Augmented Generation) 파이프라인 작업 내역을 관리하는 저장소입니다.

## 폴더 구조

각 회차 폴더 하위는 팀원 계정명으로 구분되어 있으며, 팀원별로 자신의 작업물을 해당 폴더에 올립니다.

```
1stEDA/  ~  4thEDA/   # 회차별 EDA 작업 (fastsloth226, hewonjin, hyc6028, jiye1211, minjukim22)
1stRAG/               # 채점용 RAG 파이프라인 작업 (문서, 인덱싱, 스코어링 모델 등)
Docs/                 # 기획서, WBS 등 팀 공용 문서 (+ 팀원별 개인 문서 하위폴더)
```

- `1stEDA` ~ `4thEDA`: 회차별 EDA(탐색적 데이터 분석) 결과물. 3rd/4thEDA는 향후 작업이 채워질 폴더입니다.
- `1stRAG`: ESG 채점을 위한 RAG 파이프라인 관련 작업(파싱, 인덱싱, 채점 모델 등).
- `Docs`: 기획서, WBS, 등급표 등 팀 공용 문서.

추후 회차가 진행되며 각 폴더에 작업물이 계속 추가될 예정입니다.
