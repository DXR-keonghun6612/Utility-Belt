# TODO — 구조 재설계 진행 현황

> 데이터 생성(Session) + 사람 검수(Editor) 도구. 세션 데이터 → 라벨링된 이미지 데이터셋.

---

## 이번 세션 (2026-06-18) — 진행/변경

### 완료

- [x] **batch 통일** — `Flat_frame_batch_process` 제거. `Frame_batch_process` 에 `is_flatten: bool` 플래그로 class-aware / flat 일원화. `aggregate_hs` 는 `Frame_batch_process(is_flatten=True)` 상속.
- [x] **`target_shape` 이동** — `Base_Process` 공통 필드에서 제거, 실제 사용처인 `normalize_mask` 로 이동(필요할 때 선언).
- [x] **`save.py` → `save_frame.py`** — 다중 저장 구조. `source_key: str` → `targets: list[tuple[str, str]]`((key, ext) 목록), `nested: bool` 로 배치 선택(`<class>/<key>/<stem>` vs `<class>/<stem>_<key>`). 반환 `{"saved": list[str]}`.
- [x] **`load_frame` key 선택** — `keys: list[str]` config. 비우면 전체, 지정 시 해당 key 만 로드.
- [x] **`config_form` 리스트 지원** — `_ListEdit`(list[str], 쉼표) + `_PairListEdit`(list[tuple[str,str]], `a:b` 쉼표). 공백 strip 은 폼 계층에서.
- [x] **`_block` registry 도출** — 수동 `PROCESS_CONFIG` map 제거. `pipeline_registry` 에서 FRAME/TOP 분류, config 는 `{name}_config` 규칙 + `Get`+try 안전망.
- [x] **`INPUTS`/`OUTPUTS` ClassVar** — 모든 process 에 입출력 key 명시 선언. GUI 가 `inspect` 대신 이 값을 읽어 `in: … → out: …` 표시(콤보 아래 별도 줄).
- [x] **GUI `is_flatten` 토글** — wrapper 블록에 `Frame_batch_config` 폼(평탄화 체크박스) 노출·직렬화.
- [x] **레이아웃 개편** — 3분할 → 상단(dataloader | process 시퀀스, 각각 접기 가능) / 하단(실행·로그) 세로 분할.

### 계획 (설계 확정, 구현 예정)

- [ ] **`share` 탑레벨 프로세스** — context(blackboard)에 임의 key→value 주입. `Base_Process.TOP_LEVEL: ClassVar[bool]` 마커로 시퀀스 최상위 블록 분류(frame_batch 안의 step 아님).
  - `images: list[tuple[str,str]]` (key:path → `cv2.imread` 로 ndarray 주입) + `values: list[tuple[str,str]]` (key:value 스칼라 리터럴) — **주입 범위 사용자 확인 대기**.
  - `OUTPUTS` 동적(주입 key 합집합). 시퀀스 맨 앞에 두면 `bg_roi` 등이 하위 process 로 흐름.
- [ ] **ROI 에디터 다이얼로그** — 첫 dataloader 첫 프레임 자동 샘플(`Build_reader → Scan → data_path["frame"]`) → 다각형 클릭→채우기 마스크 → PNG 저장 → `share.images` 에 `(bg_roi, path)` 주입. 기존 `_bgr_to_pixmap`/`_ImageLabel` 인프라 재사용.

---

## 아키텍처 (현재)

### Process 계층

- **frame process** (`core/process/frame/`) — 단일 프레임 연산. `Run(meta, **kwargs) -> dict`.
- **batch process** (`core/process/batch/`) — `CATEGORIZE_FILE_LIST` 전체에 적용. `Run(frames, **shared) -> dict`.
- **`Base_frame_batch`** — inner frame process 체인을 프레임마다 순차 실행.
  - `_Apply_frame(shared, debug, **context)`: 각 inner에 `{**context, **shared}` 전달, 직전 출력이 다음 입력(`context = _out`). 마지막 출력 반환.
  - `Frame_batch_process` — `is_flatten: bool` 로 class-aware(기본) / flat(평탄화) 선택.
- **`aggregate_hs`** — `Frame_batch_process(is_flatten=True)` 상속. inner: `[load_frame → extract_hs]`. `super().Run()`으로 h/s 수집 후 집계 → `{"bg_stats": HS_stats}`.
- **메모리**: `_prev = _out` 교체로 이전 프레임 이미지 자연 해제 (O(1) 프레임).

### Session 계층

Session은 최소 오케스트레이션만 담당:

```python
context = {"frames": categorization, "id_map": ..., "save_root": ..., "debug": ...}
for proc in processes:
    context.update(proc.Run(**context) or {})
```

- `frames` = `CATEGORIZE_FILE_LIST` (dataloader 출력 그대로).
- process가 `**kwargs`를 받으면 context 전체 전달, 필요한 key만 꺼내 씀.
- **Checkpoint**: batch process 완료 결과(scalar/dataclass)를 저장. 재실행 시 복원 후 해당 process skip.
- Split/Prune은 추후 `process/batch/`로 구현 예정.

### 패키지 구조 (현재)

```text
core/
  __init__.py              config_registry
  dataloader/              _base(Frame_Meta, CATEGORIZE_FILE_LIST), build, categorized, uncategorized
  process/
    __init__.py            pipeline_registry
    _base.py               Base_Process, BBOX, GRAY_IMAGE
    build.py               Build_process
    utils/                 color(HS_stats, Hs_distance), mask(Crop_square, Mask_padding, Make_morph_kernel)
    frame/                 load_frame, extract_hs, extract_mask_with_hs_stats,
                           frame_crop, normalize_mask, save_frame
    batch/                 aggregate_hs, frame_batch(Base_frame_batch,
                           Frame_batch_process[is_flatten])
  session/
    base.py                Session, Session_config
    checkpoint.py          Checkpoint, Hash
gui/
  page.py                  Pipeline | Editor 탭
  pipeline/                _block, _sequence_panel, _dataloader_panel,
                           _run_panel, _worker, _panel
  editor/                  _model, _tree, _grid, _panel
  widgets.py, config_form.py
cli.py
app.py
```

### 파이프라인 흐름 (현재)

```text
reader.Load(source)          → CATEGORIZE_FILE_LIST              (dataloader)
Session._Run_pipeline:
  context = {frames, id_map, save_root, debug}
  (share.Run(**ctx)          → {bg_roi: mask, ...}               (계획: ROI 등 shared 값 주입))
  aggregate_hs.Run(**ctx)    → {bg_stats: HS_stats}              (is_flatten=True 내부: load_frame → extract_hs)
  frame_batch.Run(**ctx)     → {mask: [...], ...}                (load_frame → extract_mask_hs → frame_crop → normalize_mask → save_frame)
  (Checkpoint.Save 가 각 단계 결과 저장)

[검수] Editor → 결과 폴더 로드 → class 재지정/제외 → 저장
```

---

## 완료

### 코어 — Process 재설계

- [x] `Base_frame_batch._Apply_frame` — `(shared, debug, **context)` 시그니처. `{**context, **shared}` 전달, `context = _out` replace 패턴
- [x] `Frame_batch_process` / `Flat_frame_batch_process` 분리 — class-aware / flat
- [x] `load_frame` — frame process. `Frame_Meta` 입력, 확장자 기반 dispatch
- [x] `aggregate_hs` — `Flat_frame_batch_process` 상속, `super().Run()` 활용, `HS_stats` 반환
- [x] `extract_hs` — `roi=None`, `mask`/`bg_roi` fallback
- [x] `extract_mask_with_hs_stats` — HS 통계 기반 전경 마스크 추출 (구 `extract_mask` 대체)
- [x] `frame_crop` — mask bbox 기반 frame crop
- [x] `normalize_mask` — bbox crop → `target_shape` canvas 중앙 배치
- [x] `Stop()`/`_stopped` 제거 — dead code
- [x] `HS_stats` — `process/utils/color.py` 로 위치 확정

### 코어 — Session 재설계

- [x] Session 단순화 — `inspect` 기반 dispatch 제거, `proc.Run(**context)` 단순 루프
- [x] `_Load_frame` 제거 — `load_frame` process가 담당
- [x] `finalize.py` 제거 — Split/Prune 추후 batch process로 이동
- [x] `session/crop_mask.py` 제거 — `normalize_mask` process로 대체
- [x] Checkpoint 단순화 — scalar/dataclass만 저장, image 저장 제거
- [x] `checkpoint.py` import 수정 (`HS_stats` 경로)

### GUI

- [x] `page.py` → Pipeline | Editor 탭
- [x] Pipeline — catalog, 블록 빌더, dataloader 패널, run 패널, config 저장 + Session 실행 worker
- [x] Editor — 트리(class 드래그&드롭 재지정) + 썸네일 그리드, 제외/복원
- [x] Editor 저장 = 적용(파일 이동 + categorization.json)
- [x] `config_form` — int/float/bool/str 위젯 지원

---

## 남은 작업

- [ ]  **GUI 연동** — 재설계된 process/session 구조에 맞게 GUI 업데이트
- [ ] **Split/Prune batch process** — `process/batch/split.py`, `process/batch/prune.py` 구현
- [ ] **Editor mask 페인팅** — `editor/_canvas.py`. 현재는 class 재지정/제외만
- [ ] **process 등록 자동화** — `core/process/__init__.py` side-effect import
