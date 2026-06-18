# Label Editing & Navigation System

실제 촬영 세션 데이터에서 세그멘테이션 마스크를 추출·분류·저장하는 데이터셋 빌더.  
Config 하나로 파이프라인 전체를 선언하고, 레지스트리 기반으로 동적 조립한다.  
CLI 단독 실행과 PySide6 GUI(파이프라인 편집 + 검수)를 모두 지원한다.

---

## 전체 구조

```text
Segment_labeling/
├── app.py                        # GUI 진입점 (PySide6)
├── cli.py                        # CLI 진입점
│
├── core/
│   ├── dataloader/               # 세션 데이터 로드
│   │   ├── _base.py              # Frame_Meta, CATEGORIZE_FILE_LIST, Base_Reader
│   │   ├── build.py              # Build_reader
│   │   ├── categorized.py        # 하위 폴더명 → 카테고리
│   │   └── uncategorized.py      # 단일 폴더 → 카테고리 없음
│   │
│   ├── process/                  # 처리 파이프라인
│   │   ├── _base.py              # Base_Process, BBOX, GRAY_IMAGE
│   │   ├── build.py              # Build_process
│   │   ├── utils/
│   │   │   ├── color.py          # HS_stats, Hs_distance, Hue_delta
│   │   │   └── mask.py           # Crop_square, Mask_padding, Make_morph_kernel
│   │   ├── frame/                # 단일 프레임 연산
│   │   │   ├── load_frame.py     # Frame_Meta → {frame, mask, stem, …}
│   │   │   ├── extract_hs.py     # ROI H·S 픽셀 추출
│   │   │   ├── extract_mask_with_hs_stats.py  # HS 통계 → 전경 마스크
│   │   │   ├── extract_mask_sam3.py # SAM3 분할 (mask 앵커 프롬프트 선택)
│   │   │   ├── frame_crop.py     # mask bbox 기준 frame crop
│   │   │   ├── normalize_mask.py # mask → bbox crop → 고정 크기 canvas (target_shape)
│   │   │   └── save_frame.py     # targets(key:ext) 다중 저장, nested 배치 선택
│   │   ├── batch/                # CATEGORIZE_FILE_LIST 단위 연산
│   │   │   ├── frame_batch.py    # Base_frame_batch, Frame_batch_process(is_flatten)
│   │   │   └── aggregate_hs.py   # 전체 프레임 H·S 집계 → HS_stats
│   │   └── init/                 # top-level share 주입
│   │       └── share.py          # images/values → share 채널 주입
│   │
│   └── session/
│       ├── base.py               # Session, Session_config
│       └── checkpoint.py         # Checkpoint, Hash
│
└── gui/
    ├── page.py                   # Pipeline | Editor 탭
    ├── widgets.py
    ├── config_form.py
    ├── pipeline/                 # 파이프라인 편집 + 실행
    └── editor/                   # 결과 검수 (class 재지정/제외)
```

---

## 파이프라인 흐름

```text
reader.Load(source)
  → CATEGORIZE_FILE_LIST: {class_name: [Frame_Meta, …], …}

Session._Run_pipeline(frames, …):
  context = {frames}                             # 데이터 산출물 채널
  share   = {id_map, save_root, debug}           # 공유 상수 채널

  각 top-level process: (ctx_out, share_out) = proc.Run(share=share, **context)
    context.update(ctx_out);  share.update(share_out)

  share.Run(share, …)                            # top-level 주입 (ROI 등)
    → share_out = {bg_roi: mask, …}

  aggregate_hs.Run(share, frames)
    is_flatten=True — 전체 프레임 평탄화 순회:
      load_frame  → {frame, mask, stem}
      extract_hs  → {h, s}          (mask/bg_roi fallback 사용)
    집계: → share_out = {bg_stats: HS_stats(mean_h, mean_s, std_h, std_s)}

  frame_batch.Run(share, frames)
    Frame_batch 내부 — 프레임별 (share 는 읽기 전용 전달):
      load_frame              → {frame, mask, stem}
      extract_mask_with_hs_stats → {mask}        (HS 통계 기반 전경 마스크)
      frame_crop              → {crop}           (mask bbox 기준 frame crop)
      normalize_mask          → {mask}           (고정 크기 canvas 중앙 배치)
      save_frame              → {saved}          (targets 다중 저장)
    → ctx_out = {saved: […], …}                  (share 는 미집계)

[검수] Editor: 결과 폴더 → class 재지정/제외 → 저장
```

---

## 설계 원칙

### 1. Config-First

모든 컴포넌트는 Config 인스턴스 하나로 완전히 재현 가능하다.

- Config는 `@dataclass` — 순수 데이터, yaml 직렬화 가능
- `config_type` / `object_type` 필드로 레지스트리 조회
- GUI `Config_form`은 dataclass 필드 `"ui"` 메타데이터로 위젯 자동 생성

### 2. Registry 기반 동적 바인딩

```python
config_registry   # *_config 클래스
pipeline_registry # process 클래스
```

확장 = 새 클래스 + `@registry.Register_module(key)`. 기존 코드 수정 없음.

### 3. Process 계층 구조

| 계층 | 역할 | 시그니처 |
|------|------|----------|
| **frame process** | 단일 프레임 연산 | `Run(meta, **kwargs) → dict` |
| **batch process** | 전체 프레임 집합 처리 | `Run(frames, **shared) → dict` |
| **Session** | 오케스트레이션 | `proc.Run(**context)` 루프 |

### 4. Blackboard 패턴 (2채널)

블랙보드는 두 채널로 분리된다:

- **context** — 데이터 산출물(frames, 프레임별 결과 리스트). process마다 갱신.
- **share** — 실행 내내 유지되는 공유 상수(save_root, bg_roi, bg_stats). 1회 주입 후 모든 프레임/batch에 동일 전달.

top-level process(`TOP_LEVEL=True`)는 `Run(share, **context) → (context_out, share_out)`로 두 채널을
각각 반환하고, Session이 채널별로 누적한다. frame process(inner)는 `Run(meta, **kwargs) → dict`로
share 값을 kwargs로 투명하게 받는다. 채널을 나눈 덕에 frame_batch가 공유 상수를 프레임별 리스트로
변형시키지 않는다.

`INPUTS`/`OUTPUTS`(context) + `SHARE_IN`/`SHARE_OUT`(share) ClassVar로 소비·생산 key를 명시 선언하고,
GUI는 이를 읽어 `in: … → out: …` / `share in: … → out: …` 로 표시한다(배선 가시화). 실제 연결은
key 일치로 이뤄진다(강제 아님). `share` 프로세스(`init/`)로 임의 key→value(ROI 마스크, 스칼라)를
share에 주입한다.

### 5. O(1) 프레임 메모리

frame process 체인에서 `_prev = _out` 교체로 이전 단계 이미지가 자연 해제됨.  
`load_frame` 출력(frame 이미지)은 `extract_hs` 또는 `extract_mask_hs` 단계에서 `_prev`가 교체되는 순간 GC.
