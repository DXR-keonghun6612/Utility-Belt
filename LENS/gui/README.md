# gui/

dataset_meta 중심 GUI. dataset_root 를 열어 `Dataset_Meta` 를 로드하고, 보기/편집(Meta 뷰어) +
flow 실행(run)으로 가공한 뒤 학습 annotation 을 내보낸다. core 의 `Pipeline`(= core 자체)을
구동한다 — 설계는 [`../core/README.md`](../core/README.md).

메인은 영속 `Pipeline` 을 하나 보유한다(`meta = pipeline.meta` 단일 소스). Convert·Run·
staging(`Move`)·편집 저장(`Save`)·meta 가져오기(`Merge`)·annotation 내보내기(`Export`)가 모두 이
하나의 Pipeline 을 거친다.

---

## 레이아웃

```
Main_page
  ├── dataset_root [뷰어 ▸ Converter 창에서 설정] [↺]        [Converter…]
  ├── [flow_profile 가져오기] [▶ run]   현재 프로필: 3 flow — …
  ├── ── 진행바 ──
  ├── 본문 = Meta_view   (stem 목록 상태 뱃지 + 임베드 Stem_editor + id_map/params)
  └── [meta 가져오기] [전부 비우기]                     [annotation 생성]
```

- dataset_root 는 읽기전용 뷰어 — 값 편집은 Converter 창에서만.
- Converter·flow 창은 비모달(메인과 독립). config 는 통째로 묶지 않고 섹션별로 Pipeline 에
  주입한다(`set_converter` / `Run(flows=…)`).
- `전부 비우기` 는 보유 세션(root·converter·flows·뷰)만 초기화 — 디스크는 건드리지 않는다.

---

## 영속 — 레시피(config) ↔ 산출물(data)

| 대상 | 정체 | 다루는 곳 |
|---|---|---|
| dataset_meta | 산출물(데이터) | dataset_root 열기로 자동 로드 · 편집/run/이동 시 자동 저장 |
| converter 설정 | 레시피(raw→meta) | Converter 창 저장/불러오기 · 실행 시 `set_converter` 주입 |
| flow 프로필 | 레시피(meta 가공, `flows:`) | flow 빌더 창 저장/불러오기 · 실행 시 `Run(flows=…)` 주입 |

메타 파일 자체는 core `store` 가 소유(`{root}/dataset_meta.json` + 사이드카, 내보내기 =
`{root}/annotation.json`). root 는 저장하지 않고 로드 위치에서 잡는다.

---

## 데이터 흐름

```
[Converter 창]  raw → 초기 dataset_meta          Pipeline.Convert (보유 Pipeline)
      │ 완료 → meta 뷰 갱신
      ▼
dataset_root 열기 → Dataset_Meta 로드
  → [flow 빌더 + ▶ run]  flow 실행 → modified 채움     Pipeline.Run(flows)
  → [Meta 뷰어]          검수·편집 → staged 전이         Pipeline.Move
  → [meta 가져오기]      다른 결과 병합(상태 보존)        Pipeline.Merge
  → [annotation 생성]    staged → {root}/annotation.json   Pipeline.Export
```

flow 한 장(카드) = `flows:` 리스트의 1 엔트리 — `object_type`·`unit`·`shared`·`processes`/
`finalize_processes`·`carry`·`cacheable`. `model` 필드를 가진 process 는 모델 주입 서브폼을 연다.

- Convert·Run 은 `Pipeline_worker` 하나로 백그라운드 실행 — 무엇을 돌릴지는 task 콜러블이 정하고,
  보유 Pipeline 을 그대로 돌린다. meta 가 in-place 갱신돼 화면과 일치한다.
- meta 가져오기 — 파일을 고르면 root = 그 파일 폴더(자기완결 폴더 전제). 열린 root 없으면 그 폴더를
  그대로 열고, 있으면 충돌 질의 후 현재 root 로 복사 병합. 어느 쪽이든 meta 는 in-place 로 갱신
  한다(객체 교체 아님 — 편집기가 같은 meta 객체를 봐 stale 을 막는다).

---

## 폴더

| 폴더/파일 | 역할 |
|---|---|
| `page/` | 메인 조립(`_main.py`) + Converter 다이얼로그(`_converter_dialog.py`) |
| `converter/` | Converter 패널 — raw 소스 탐색 설정 (`Pipeline.Convert`) |
| `run/` | flow 시퀀스 빌더(`Flow_card`/`Flow_sequence`) + 실행 다이얼로그 |
| `meta_view/` | Dataset_Meta 뷰어 — stem 목록 + 임베드 편집기 + id_map/params |
| `verify/` | `Stem_editor` — base 이미지 + mask/bbox 오버레이 편집 |
| `form/` | process/모델 파라미터 폼 자동 생성 (`Annotated[UI]` 기반) |
| `widgets/` | 슬라이더·줌 이미지뷰·경로행 등 공통 위젯 (core 의존 0) |
| `_worker.py` | `Pipeline_worker` — 보유 Pipeline 의 한 단계 백그라운드 실행 (Convert/Run 공용) |
| `_io.py` | 파일 선택 + dict 직렬화 (converter/flow 저장·불러오기) |

잔여 작업: [`TODO.md`](TODO.md).
