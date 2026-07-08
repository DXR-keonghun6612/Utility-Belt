# LENS — Label Editing & Navigation System

raw 데이터에서 세그멘테이션 학습 데이터를 생성·검증하는 파이프라인.

**`core`** 가 곧 pipeline(최상위 binder)이다 — dataset(`Dataset_Meta`)을 중심으로
converter→run→verify 를 조율하고, flow 시퀀스를 조립·실행한다. 설계는
[`core/README.md`](core/README.md).

---

## CLI

```bash
python cli.py --config config.yaml --stages converter   # raw 파일 → Dataset_Meta 초기화
python cli.py --config config.yaml --stages run         # flow 시퀀스 실행 → mask/통계 생성
python cli.py --config config.yaml --stages verify      # 생성 결과 검수 (미구현)
python cli.py --config config.yaml --stages converter run verify  # 전체
```

## 데이터 흐름

```text
raw 파일
  └─ Convert ─→ Dataset_Meta          (stem = 컨테이너 Data_Ref, 객체 없이 시작)
                  └─ Run(flows) ─→ Dataset_Meta     (mask·bbox·통계 채움 → 검수 후 staged)
                                     └─ Sample ─→ Sample_Set   (staged → train/val/test, task별 트리)
                                                    └─ Verify ─→ 검수 (미구현)
```

세 스테이지(Convert/Run/Sample)는 모두 `process` 의 **`Stage` 엔진**(source→체인→sink)이고, source/sink 만
다르다 — Convert=raw 발견/정본 등록, Run=정본 순회/정본 라우팅, Sample=정본 순회/파생 배치.

- 모든 데이터는 **단일 재귀 노드 `Data_Ref(type, format, info)`** 로 기술된다 — `type="stem"` 이면
  컨테이너(`info` = 자식 `Data_Ref` 들), 아니면 leaf(payload). 로드/저장은 dataset 핸들러가 담당한다
  (계산 계층은 위치·타입만 정함).
- **flow 간 데이터는 오직 `dataset_meta` 만 경유** — 앞 flow 가 남긴 키 = 뒤 flow 의 입력.
- 무거운 prediction 모델(SAM3 등)은 config 에 nested 된 스펙(`model: {type: sam3, …}`)을 pipeline 이
  빌드해 process 에 주입한다 (같은 스펙은 한 번만 빌드해 공유).

## Config

```yaml
dataset_root: /data/output/my_dataset

converter:
  object_type: glob
  sources: [/data/raw/session1]
  globs:
    frame:    {pattern: "*_pose.png"}                # type 생략 → 확장자로 핸들러 추론
    class_id: {pattern: "*_pose.txt", type: attr}    # 추론 안 되는 확장자 → type 명시

flows:                                               # flow 엔트리 시퀀스
  - object_type: chroma_bg                           # 배경 크로마 모델 → meta.params
    processes:
      - {object_type: convert_to_chroma}
      - {object_type: accumulate_chroma_histogram, per_pixel: true}
    finalize_processes:
      - object_type: robust_chroma_stats
        outputs: {mean_c0: {to: meta}, mean_c1: {to: meta},
                  std_c0: {to: meta}, std_c1: {to: meta}}
    carry: [c0_acc, c1_acc]
    cacheable: true
  - object_type: segment                             # 객체별 mask/bbox 프롬프트를 SAM3 로 정제
    unit: object                                     # 프레임의 객체마다 1회
    processes:
      - object_type: extract_mask_sam3_with_mask     # 기존 mask/bbox 를 받아 정제 → mask·bbox 출력
        text: "solid plastic body only"             # config 필드 — 모든 입력에 함께 쓰는 concept 토큰
        n_points: 5
        model: {type: sam3, checkpoint: "", device: cuda}   # 모델 nested → pipeline 이 주입
        outputs: {mask: {to: storage, dir: sam3_mask, format: .png}}   # bbox 는 미선언 → ctx 잔류

verify: {}
```

flow 작성 템플릿은 [`core/process/presets.example.yaml`](core/process/presets.example.yaml).

## 모듈 구성

```text
core/           ← pipeline binder
├── _base.py    Pipeline (Convert→Run→Sample→Verify + 모델 풀) · __init__.py = Load_pipeline 진입점
├── data/       Data_Ref(재귀 노드) · Bucket_Store · handler · meta(정본 store) · sample(파생 store)
├── process/    Base_Process 유닛 + Stage 엔진(source→체인→sink) + Run(Flow) — 계산 계층
├── converter/  Convert 스테이지 — Raw_source(raw 발견) → Register_sink(정본 등록)
└── sampler/    Sample 스테이지 — Staged_source(정본 순회) → Sample_sink[task](파생 배치)
cli.py          CLI 진입점
gui/            dataset_meta 중심 GUI — core Pipeline 구동 (converter/run/meta_view/verify, gui/README.md)
analysis/       크로마 진단 (core 로 흡수 예정 — Verify 연계)
```

세 스테이지는 단위 계약(`Base_Process`)이 같고 source/sink 만 다르다 — `process` 의 `Stage` 엔진을 공유한다.

남은 작업은 [`core/TODO.md`](core/TODO.md).

1. 7월 중 무영조명 적용
2. classification 100% -> 안되는 객체를 중심으로 정리해서 보여줄것.  -> 실루엣 형태가 동일학나? 입력 데이터 자체가 문제인가?