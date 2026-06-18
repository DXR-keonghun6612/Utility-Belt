# Segment Labeling

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
│   │   │   ├── frame_crop.py     # mask bbox 기준 frame crop
│   │   │   ├── normalize_mask.py # mask → bbox crop → 고정 크기 canvas (target_shape)
│   │   │   └── save_frame.py     # targets(key:ext) 다중 저장, nested 배치 선택
│   │   └── batch/                # CATEGORIZE_FILE_LIST 단위 연산
│   │       ├── frame_batch.py    # Base_frame_batch, Frame_batch_process(is_flatten)
│   │       └── aggregate_hs.py   # 전체 프레임 H·S 집계 → HS_stats
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
  context = {frames, id_map, save_root, debug}

  (share.Run(**context)                        # [계획] shared 값 주입 (ROI 등)
    → context["bg_roi"] = mask, …)

  aggregate_hs.Run(**context)
    is_flatten=True — 전체 프레임 평탄화 순회:
      load_frame  → {frame, mask, stem}
      extract_hs  → {h, s}          (mask/bg_roi fallback 사용)
    집계: → context["bg_stats"] = HS_stats(mean_h, mean_s, std_h, std_s)

  frame_batch.Run(**context)
    Frame_batch 내부 — 프레임별:
      load_frame              → {frame, mask, stem}
      extract_mask_with_hs_stats → {mask}        (HS 통계 기반 전경 마스크)
      frame_crop              → {crop}           (mask bbox 기준 frame crop)
      normalize_mask          → {mask}           (고정 크기 canvas 중앙 배치)
      save_frame              → {saved}          (targets 다중 저장)

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

### 4. Blackboard 패턴

Session context가 블랙보드. 각 batch process 출력이 context에 누적되어 다음 process로 전달.  
각 process는 `INPUTS` / `OUTPUTS` ClassVar로 소비·생산 key를 명시 선언하고, GUI는 이를 읽어
`in: … → out: …` 로 표시한다(배선 가시화). 실제 연결은 key 일치로 이뤄진다(강제 아님).  
`[계획]` `share` 프로세스(`TOP_LEVEL`)로 임의 key→value(ROI 마스크 등)를 context에 주입 가능.

### 5. O(1) 프레임 메모리

frame process 체인에서 `_prev = _out` 교체로 이전 단계 이미지가 자연 해제됨.  
`load_frame` 출력(frame 이미지)은 `extract_hs` 또는 `extract_mask_hs` 단계에서 `_prev`가 교체되는 순간 GC.
