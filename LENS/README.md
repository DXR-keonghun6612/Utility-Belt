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

Run·Sample 은 `process` 의 **`Stage` 엔진**(source→체인→sink)이고 양 끝(source/sink)만 다르다 —
Run=정본 순회/정본 라우팅, Sample=정본 순회/파생 배치. **Convert 는 Stage 가 아니다** — 체인이 비어
엔진을 안 쓰고 `store.Import` 를 부를 뿐이다(들이기는 라이프사이클이라 store 소유).

- 모든 데이터는 **단일 재귀 노드 `Data_Ref(format, info)`** 로 기술된다 — `bool(format)` 이
  BRANCH(컨테이너, `info` = 자식 `Data_Ref` 들)/LEAF(payload 서술자, `format` = `(도메인, 포맷)`)를 가른다.
  로드/저장·경로 파생은 `port` 가 맡는다 (계산 계층은 위치·타입만 정함).
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

flow 작성 템플릿은 [`config/flows.yaml`](config/flows.yaml) (전체 세션 예시는 [`config/example_session.yaml`](config/example_session.yaml)).

## 모듈 구성

계층은 **아는 타입**으로 갈린다(상세 지도는 [`core/README.md`](core/README.md)):

```text
core/           ← pipeline binder
├── schema.py   Data_Ref (재귀 트리 노드 — cv2-free 코어)
├── func/       배열↔배열 순수 계산 (cv·chroma·mask) — core 를 모른다
├── format/     데이터 구조 + 그 연산 (bbox·polygon·rle)
├── codec/      포맷 단위 직렬화 (raster·npy·inline·docs)
├── port/       domain — 무엇으로 읽나 + 검증·정책 + 디스패치 + 발견(scan)
├── store/      Bucket_Store · Dataset_Meta(정본) · Sample_Set(파생) + 라이프사이클
├── process/    Base_Process 유닛 + Stage 엔진(source→체인→sink) — 계산 계층
├── export/     정본·파생 → 외부 레이아웃(coco/yolo/mask) 내보내기 (binder)
└── _base.py    Pipeline (Convert→Run→Sample→Verify + 모델 풀) · __init__.py = Load_pipeline 진입점
cli.py          CLI 진입점
gui/            dataset_meta 중심 GUI — core Pipeline 구동 (gui/README.md)
analysis/       크로마 진단 (core 로 흡수 예정 — analysis→flow)
```

Run·Sample 은 단위 계약(`Base_Process`)이 같고 source/sink 만 달라 `process` 의 `Stage` 엔진을 공유한다
(Convert 는 엔진을 안 쓴다). **경계는 산문이 아니라 [`core/test_layering.py`](core/test_layering.py) 가 강제**.

남은 작업은 [`core/TODO.md`](core/TODO.md).

1. 7월 중 무영조명 적용
2. classification 100% -> 안되는 객체를 중심으로 정리해서 보여줄것.  -> 실루엣 형태가 동일학나? 입력 데이터 자체가 문제인가?