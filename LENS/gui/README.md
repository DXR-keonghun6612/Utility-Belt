# gui/

dataset_meta 중심 GUI. dataset_root 를 열어 `Dataset_Meta` 를 로드하고, 보기/편집(Meta 뷰어) +
flow 실행(run)으로 가공한 뒤 학습 annotation 을 내보낸다. core 의 `Pipeline`(= core 자체)을
구동한다 — 설계는 [`../core/README.md`](../core/README.md).

메인은 영속 `Pipeline` 을 하나 보유한다(`meta = pipeline.meta` 단일 소스). Convert·Run·정렬(`Order`)은
Pipeline 을 거치고, staging(`Move`)·편집 저장(`Save`)·meta 가져오기(`Merge`)는 그 `meta` 의
**라이프사이클 메서드**를 직접 부른다 — core 원칙 그대로(라이프사이클은 store 소유, 바인더는 계산 조율만).

---

## 레이아웃

```
Main_page
  ├── dataset_root [뷰어 ▸ Converter 창에서 설정] [↺]        [Converter…]
  ├── [flow_profile 가져오기] [▶ run]   현재 프로필: 3 flow — …
  ├── ── 진행바 ──
  ├── 본문 = Meta_view   (stem 목록 상태 뱃지[작업/검수/보류] + params·데이터·객체 트리 + Data_view · [저장])
  └── [meta 가져오기] [전부 비우기] [Split…] [분석…]
```

- dataset_root 는 읽기전용 뷰어 — 값 편집은 Converter 창에서만.
- Converter·flow 창은 비모달(메인과 독립). config 는 통째로 묶지 않고 섹션별로 Pipeline 에
  주입한다(`set_converter` / `Run(flows=…)`).
- `전부 비우기` 는 보유 세션(root·converter·flows·뷰)만 초기화 — 디스크는 건드리지 않는다.

---

## 영속 — 레시피(config) ↔ 산출물(data)

| 대상 | 정체 | 다루는 곳 |
|---|---|---|
| dataset_meta | 산출물(데이터) | dataset_root 열기로 자동 로드 · 편집은 명시적 `[저장]`(→ obj_id 정렬) · run/이동/추가·삭제는 즉시 |
| converter 설정 | 레시피(raw→meta) | Converter 창 저장/불러오기 · 실행 시 `set_converter` 주입 |
| flow 프로필 | 레시피(meta 가공, `flows:`) | flow 빌더 창 저장/불러오기 · 실행 시 `Run(flows=…)` 주입 |

메타 파일 자체는 core `store` 가 소유한다 — **item 하나 = 사이드카 하나**(`{root}/.meta/{범주}/{key}.json`)
+ kind-major payload. 정본을 뭉쳐 내보내는 기능은 없다(폴더째 옮기면 된다). root 는 저장하지 않고 로드
위치에서 잡는다. 레이아웃은 [`../core/store/README.md`](../core/store/README.md).

---

## 데이터 흐름

```
[Converter 창]  raw → 초기 dataset_meta          Pipeline.Convert (보유 Pipeline)
      │ 완료 → meta 뷰 갱신
      ▼
dataset_root 열기 → Dataset_Meta 로드
  → [flow 빌더 + ▶ run]  flow 실행 → modified 채움     Pipeline.Run(flows)
  → [Meta 뷰어]          검수·편집 → 작업/검수/보류 전이   meta.Move / meta.Delete (백그라운드)
  → [meta 가져오기]      다른 결과 병합(상태 보존)        meta.Merge
  → [Split 창]           staged → 비율대로 폴더 분할 내보내기  Pipeline.Split_export(...)  (gui/meta_page/split)
```

flow 한 장(카드) = `flows:` 리스트의 1 엔트리 — `object_type`·`unit`·`shared`·`processes`/
`finalize_processes`·`carry`·`cacheable`. `model` 필드를 가진 process 는 모델 주입 서브폼을 연다.

- Convert·Run·**전이/삭제**는 `Pipeline_worker` 하나로 백그라운드 실행 — 무엇을 돌릴지는 task 콜러블이
  정하고, 보유 Pipeline 을 그대로 돌린다. 실행 중엔 진행바 표시 + `Meta_view.set_editable(False)`(**편집만
  잠금** — 값 수정·저장·전이/삭제·id_map). 뷰는 얼리지 않아 stem 목록 클릭·이미지 보기·팝아웃은 그대로
  된다(데이터가 워커에서 변형되는 동안 편집만 끼어들지 못하게). 상태 전이는 **대량 아니어도 항상
  백그라운드**이고, 완료 후 목록은 단일 `refresh()`(O(n))로 동기화한다.
- 상태는 **3-버킷(작업=modified / 검수=staged / 보류=skipped)**. 보류는 지우지 않고 치워둔 것(되돌리기
  가능)으로 모든 파이프라인에서 자연히 제외된다.
- meta 가져오기 — **폴더**를 고른다(`Dataset_Meta.Restore` 가 dataset root 디렉터리에서 `.meta/*.json`
  사이드카를 복원 — 파일이 아니라 폴더). 열린 root 없으면 그 폴더를 그대로 열고, 있으면 충돌 질의 후
  현재 root 로 복사 병합. 어느 쪽이든 meta 는 in-place 로 갱신한다(객체 교체 아님 — 편집기가 같은 meta
  객체를 봐 stale 을 막는다).
- [Split 창] — staged 를 비율대로 갈라 폴더별로 내보낸다(coco). 인자만 받는 **모달**이고 실행은 워커다
  ([`meta_page/split/`](meta_page/split/_dialog.py)) — 정본은 안 바뀐다(복사).

---

## 폴더

구성 ↔ 연결 2축으로 나뉜다 — `*_page/`(구성: widgets 기반 독립 창) vs `app/`(연결: Pipeline 소유 +
배선·주입). 도메인은 Pipeline 객체 그래프(정본 1 + tasker N)를 미러링한다. 목적지·근거는 [`TODO.md`](TODO.md).

| 폴더/파일 | 역할 |
|---|---|
| `app/` | **연결층 셸** — `Main_page`(보유 Pipeline 소유 + meta_page 창 배선·주입) + `Meta_ops`(백그라운드 run/전이/삭제) |
| `meta_page/` | **정본 편집 갈래** (아래 하위 surface). `Pipeline` 은 주입받고, 도메인 타입(`Data_Ref`·`Dataset_Meta`)은 위젯이 직접 쓴다 (seam = 타입별 표현 레지스트리 `viewer/`) |
| `meta_page/view/` | Dataset_Meta 뷰어 — stem 목록 + params·데이터·객체 트리 + `Data_view`(합성 캔버스+인스펙터+단일 편집기) |
| `meta_page/convert/` | Converter 패널 + 다이얼로그 — raw 소스 탐색 설정 (`Pipeline.Convert`) |
| `meta_page/run/` | flow 시퀀스 빌더(`Flow_card`/`Flow_sequence`) + 빌더 다이얼로그 |
| `meta_page/split/` | Split 창 — 대상 폴더·몫 비율·salt·공평 배분을 받는다 (`Pipeline.Split_export`) |
| `meta_page/sample/` | *(죽은 기능 — 메인에서 진입점 제거됨. 정리 예정)* 파생 tasker 빌더 창 + sample 뷰어 |
| `meta_page/analysis/` | 형상 적합성 **검증** 창 — 좌: 설정·국면 버튼·[적용] / 우: 판정 표시(구성·분리도·리포트) (`core.analysis`) |
| `viewer/` | **LEAF type 별 표현 레지스트리** — core `HANDLER_REGISTRY` 와 짝. 새 handler → 뷰어 하나 더하면 UI 가 따라온다 (편집기는 안 든다) |
| `editor/` | **편집기 계층** — 골격(`Editor_base`: 도구·이력·잠금·조준) + 대상별(`image/`). 3d·시퀀스가 들어올 자리 |
| `steps/` | process-chain 편집 (`Process_step` + `Step_list`) — run·sample 공유 |
| `form/` | process/모델 파라미터 폼 자동 생성 (`Annotated[UI]` 기반) |
| `widgets/` | 공통 저수준 위젯 (core 의존 0) — `image`/`rows`/`list_editor` 하위 + `Collapsible` |
| `_worker.py` | `Pipeline_worker` — 보유 Pipeline 의 한 단계 백그라운드 실행 (Convert/Run/전이/삭제 공용) |
| `_io.py` | 파일 선택 + dict 직렬화 (converter/flow 저장·불러오기) |

잔여 작업: [`TODO.md`](TODO.md).
