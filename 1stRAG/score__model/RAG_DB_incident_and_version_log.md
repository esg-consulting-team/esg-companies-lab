# RAG DB 구축 히스토리 & 장애 대응 기록

> 대상 문서: `build_rag_index_v6_production.ipynb`, `llamaparse_rescue.ipynb`, `esg_query_interface.ipynb`
> 이전 버전 이력(v1~v4)은 `RAG_pipeline_history.md` 참고. 이 문서는 그 이후(v5~) + 오늘 발생한 사고를 다룸.

---

## 1부. DB 구축 파일 버전 히스토리

### 1-1. build_rag_index (인덱싱 파이프라인)

| 버전 | 변경 내용 |
|---|---|
| v4 | PyMuPDF 캐스케이딩 2단계 폴백 구조 도입 (LlamaParse 3단계는 주석 처리 상태로 대기) |
| v5 | 텍스트 추출 실패 진단 로깅(`extraction_diagnostics.csv`) 추가. "로컬에서 작업 → 완료 후 Drive 백업" 패턴 도입 (Drive 직접 쓰기 손상 이력 대응) |
| v5.1 | PyMuPDF 캐스케이딩 실제 버그 수정 — `target_pages`를 `.parse()` 호출부가 아니라 LlamaParse 생성자 파라미터로 이동, `mode`→`parse_mode`로 파라미터명 수정 |
| v5.2 | LlamaParse(3단계)를 속도 문제로 제외, pdfplumber+PyMuPDF 2단계 전용 검증판. 10개사 필터 + 진단 전용 실행 셀(Cell 6b/6c) 추가 |
| v6 | 프로덕션판. 검증용 셀(Cell Q/Q2/6b/6c) 전부 제거. **SK하이닉스로 하드코딩된 필터가 주석이 아니라 실행 코드로 남아있던 버그 발견 및 제거** (100개사 자동 인식이 안 되고 있었음) |
| v6.1 | 정합성 자동 확인 로직 추가 — checkpoint엔 완료로 찍혀있지만 실제 Chroma엔 데이터가 없는 문서를 자동 감지해 재처리 대상으로 되돌림. **자동 백업 코드가 실제로는 빠져있던 버그 발견 및 수정** (변수 선언만 있고 호출부가 없었음). `backup_every_n_docs` 10 → 3으로 하향 |
| v6.2 | 재시작 시 매번 PDF 전체를 다시 읽어 해시 계산하던 것을, `os.stat()`(크기·수정시각) 우선 비교로 변경. 재시작 후 스킵 판단 속도 대폭 개선 |

### 1-2. llamaparse_rescue.ipynb (LlamaParse 재처리, 독립 노트북)

| 버전 | 변경 내용 |
|---|---|
| 최초 생성 | pdfplumber+PyMuPDF 2단계로도 실패한 페이지만 LlamaParse로 재처리. 문서당 API 호출 1번으로 실패 페이지 전체 일괄 처리 (속도 최적화) |
| 리뷰 반영 1 | LlamaParse SDK 파라미터 버그 수정 (`target_pages` 생성자 이동, `parse_mode` 수정) |
| 리뷰 반영 2 | 표-텍스트 중복 적재 방지(삭제 후 교체) 로직 추가. Chroma add 시 배치+429 재시도 로직 추가. `still_failed_pages` NaN 안전 파싱 추가. ("$and" 최상위 필터가 Chroma에서 지원 안 된다는 리뷰 지적은 검증 결과 사실이 아니어서 반려) |
| 장애 대응판 (오늘) | 문서 단위 자체 체크포인트(`llamaparse_rescue_checkpoint.json`) 추가 — 문서 하나가 완전히 성공해야만 기록, 중단 후 재개 시 정확히 그 지점부터 이어감. delete/add 각각 재시도(최대 8회) 로직 추가. Drive 백업 전 쓰기 검증(`save_verified_backup`) 추가 — 검증 통과해야만 백업 반영. `drive_backup_dir`을 `chroma_db_migrated`로 재지정 |

### 1-3. esg_query_interface.ipynb (팀원용 조회 인터페이스)

| 버전 | 변경 내용 |
|---|---|
| v1 | `get_evidence`, `get_evidence_batch`, `build_scoring_prompt` 정의. 회사별 위험도(추출 실패율) 경고 |
| v2 | `list_available_companies()`, `sync_latest_from_drive()` 추가 — DB 구축 중에도 진행 상황 확인 + 최신화 가능하게 |
| v3 | `load_rubric()`에 header 자동 감지 추가 — 채점기준표 전체본/분리본(E/S/G) 파일 형식 상관없이 자동 인식 |
| v4 | **버그 수정**: `list_available_companies()`가 연도를 무시하고 판정하던 문제 수정 (연도별 3종 완비 여부로 정확히 재계산). **`get_evidence`/`get_evidence_batch`/`build_scoring_prompt`에 `year` 필수 인자 추가** (하위 호환 깨짐) — 연도 안 넣으면 여러 연도 근거가 섞여 검색되던 구조적 결함 해결 |
| v5 | GPT 리뷰 반영 5건: ① `company_code` zfill 정규화 누락 수정 ② BM25 캐시 FIFO 크기 제한(무제한 증가 방지) ③ 후보군(candidate_k=30)과 최종 반환개수(top_n) 분리 ④ 동일 항목 쿼리 임베딩 캐싱(API 중복 호출 제거) ⑤ 위험도 체크를 회사 단위 → (회사,연도,문서유형) 단위로 세분화. year 필드 의미(발행연도=평가년도)는 팀 컨벤션으로 확인 완료, 별도 조치 불필요 |
| v6 (오늘) | `drive_backup_dir`을 `chroma_db_migrated`로 재지정 (Chroma 손상 사고 이후) |

---

## 2부. Chroma DB 손상 · 재구축 사고 기록

### 사고 개요

| 항목 | 내용 |
|---|---|
| 발생 원인(추정) | LlamaParse 재처리(Cell 7) 청크 적재 도중 수동으로 중지 → 미완료 상태에서 `tar` 명령으로 직접 Drive에 백업하며 손상된 상태가 그대로 공식 백업 경로에 반영됨 |
| 증상 | `InternalError: attempt to write a readonly database` — 읽기(조회)는 정상, 쓰기(add/delete)만 거부됨 |
| 영향 범위 | 공용 Chroma DB (`인덱스 결과/chroma_db`) — v6·llamaparse_rescue·esg_query_interface 세 파일 모두 참조하던 경로 |
| 최종 결과 | 데이터 손실 없이 복구 완료 (237,705개 청크 중 216,562개 직접 이전 + 이후 v6·LlamaParse 재처리로 잔여분 보충) |

### 타임라인

**1. 최초 발견**
- LlamaParse 재처리 중 `vectorstore.delete()` 호출 시 `readonly database` 에러 최초 발생

**2. 원인 진단 시도 (대부분 기각됨)**
- OS 파일 권한(`chmod`) 문제 — 확인 결과 권한은 이미 정상(600, 쓰기 가능)이었음 → **기각**
- Chroma 폴더 안에 무관한 파일(팀원이 저장한 채점 결과 CSV, `SK하이닉스(000660)` 폴더) 혼입 — 제거했으나 에러 재발 → **원인 아님으로 판정**
- SQLite WAL/SHM 보조파일 불일치 — 제거 시도했으나 에러 재발 → **기각**
- 낡은 커널의 SQLite 연결 잔재(락) — 세션 완전 재시작으로 일시적으로 통과했으나, 바로 다음 문서 처리에서 재발 → **부분적 원인일 수 있으나 근본 원인 아님**
- 디스크 용량 부족 — 확인 결과 여유 충분 → **기각**

**3. 근본 대응 전환 — 새 DB로 데이터 이전(마이그레이션)**
- 원본은 읽기가 되는 상태였으므로, 원본에서 데이터를 읽어 완전히 새로운 Chroma 파일(`chroma_db_fresh` 계열)에 이전하는 방식으로 전환
- 1차 시도: `too many SQL variables` 에러 → 페이징(배치 단위 조회)으로 해결
- 진행 중 일부 배치에서 `Error getting embedding` 반복 실패 → 해당 구간만 embeddings 재계산(fallback)으로 우회
- 끝까지 복구 안 되는 배치(105개, 약 21,000개 청크, offset 213,800~237,000대)는 **skip 처리하고 진행 우선** — 이후 v6/LlamaParse로 별도 보충하기로 결정
- 최종 이전 완료: **216,562개 청크 확보** (원본 237,705개 대비 약 91%)

**4. 백업 및 검증**
- 이전된 새 DB를 `인덱스 결과/chroma_db_migrated` 경로로 Drive 백업
- 기존 손상 경로(`chroma_db`)로 "승격"(덮어쓰기) 시도했으나 동일한 readonly 에러 재발 → **승격 자체가 위험 요소로 판단, 포기**. 이후 모든 파일이 `chroma_db_migrated`를 직접 참조하도록 전환
- 개인 Drive 폴더 + 로컬 PC에도 이중 백업

**5. 검증 과정에서 발견된 2차 버그**
- 자체 제작한 `verify_writable()` 검증 함수가, 재적재 시 `embeddings`를 누락하고 있어 Chroma가 기본 임베딩 함수(384차원)로 자동 재계산 → 원래 컬렉션(Gemini, 3072차원)과 차원 불일치로 `readonly`와 유사한 에러 발생
- **DB 자체는 처음부터 정상이었고, 검증 코드의 결함이었음이 확인됨** (embeddings까지 포함해서 재적재하도록 수정 후 정상 통과 확인)

**6. LlamaParse 재처리 재개**
- 74개 문서, 377페이지 대상, 예상 비용 $1.41
- 진행 중 Gemini API 429(`prepayment credits are depleted`) 발생 — 결제 크레딧 소진 문제로 확인, 다른 API 키로 교체 후 재개
- 문서 단위 자체 체크포인트 덕분에 이미 완료된 건 자동 스킵, 중단 지점부터 재개
- 최종 68/69건 성공, 1건(`361610_2023_sustainability_report`)은 과거 임시 경로 참조 문제로 실패 → 추후 재처리 필요

**7. v6 유실 문서 확인 및 보충**
- checkpoint 대비 실제 Chroma 데이터 비교 결과, **지배구조보고서 13건(5개 회사)**이 완전히 유실된 것으로 확인
- 패턴: 전부 governance_report만 유실 — 사고 발생 시점에 특정 회사의 지배구조보고서 재업로드(오탈로 인한 파일 교체) → 삭제 후 재인덱싱 도중 사고 시점과 겹쳤을 가능성 있음 (확정 원인은 아님)
- v6 Cell 7로 해당 13건만 재처리 진행 (지배구조보고서는 텍스트 네이티브 PDF라 빠르게 처리됨)

**8. 최종 정리**
- 세 파일(v6, llamaparse_rescue, esg_query_interface) 모두 `drive_backup_dir`을 `chroma_db_migrated`로 통일
- 팀 슬랙에 경로 변경 공지 + 경로 수정 완료된 최신 파일 3종을 `인덱스파이프라인최종` 폴더에 배포

### 재발 방지 조치

| 조치 | 상태 |
|---|---|
| 쓰기 작업 셀에 재시도 로직(delete/add 각 최대 8회) | 적용 완료 |
| 문서 단위 자체 체크포인트 (중단 시 손실 범위를 "문서 1개"로 제한) | 적용 완료 |
| 백업 전 쓰기 검증 → 손상 상태가 Drive를 덮어쓰는 것 방지 | 적용 완료 |
| stat 기반 빠른 스킵으로 재시작 시 불필요한 파일 재읽기 감소 | 적용 완료 |
| `chroma_db_migrated` 폴더 쓰기 권한 제한 (팀원 실수 방지) | **미해결 — 공유 드라이브 구조상 상위 폴더 권한과 분리 안 됨, 개인 드라이브 이동 검토 필요 (내일 회의 안건)** |
| "쓰기 작업 중 세션 끊김(수동 중지·절전·네트워크 단절)" 자체를 막는 방법 | **근본적으로 코드로 100% 방지 불가 — 작업 중 세션 유지에 대한 팀 내 공유 필요** |

### 교훈

- Chroma/SQLite 계열 로컬 DB는 **쓰기 도중 강제 종료**에 취약함 — 인덱싱/재처리 셀 실행 중에는 컴퓨터 절전·네트워크 끊김·수동 중지를 피해야 함
- 수동으로 만든 백업 스크립트(`tar` 등 임시 명령)를 정식 백업 함수 대신 사용하면, 검증 없이 손상된 상태가 그대로 저장될 위험이 있음 — **백업은 반드시 "쓰기 검증 → 통과 시에만 반영"하는 절차를 거쳐야 함**
- 자동 백업처럼 "당연히 되고 있을 것"이라 여긴 로직이 실제로는 빠져있던 사례가 v6과 llamaparse_rescue 양쪽에서 각각 발견됨 — **안전장치 코드는 반드시 실제 실행 로그로 검증할 것, 존재 여부를 추정하지 말 것**
