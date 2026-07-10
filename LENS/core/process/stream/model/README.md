# model — 모델

무거운 prediction 모델(backend)에 기대는 process 들. backend 는 process 가 소유하지 않고
**pipeline 이 config 의 `model: {type: sam3, …}` 스펙을 빌드해 주입**한다(같은 스펙은 세션당 1회
빌드·공유). 모델 type→빌더는 `core/_base.py` 의 `MODEL_BUILDERS`, 런타임 구현은 이 폴더의
`_sam3.py`(`Sam3_runner`).

## backend / 정책 분리

- **backend (`_sam3.py::Sam3_runner`)** — 모델 고유 저수준 프리미티브만: `infer_ctx`(autocast
  엔벨로프), `encode`(프레임→state, 이미지 backbone 1회 + text concept), `run`(state + box/points
  → mask·score·low-res 를 numpy 로 정규화). best mask 선택·이진화·box 배치·구멍 보존 같은 **정책은
  여기 없다.** 다른 promptable segmenter 로 교체하려면 이 계약(`infer_ctx`/`encode`/`run`)만 구현.
- **정책 (`segment/`)** — backend 위에서 조립하는 **모델-무관** 층. process 가 backend 종류를
  모른다. `model:` 한 줄로 backend 교체, 정책은 그대로.

## 분할 (`segment/`)

프레임의 객체 bbox 들을 backend 로 분할해 인스턴스 `segment` 를 만든다. 여기서 backend 는
**검출·분류기가 아니라 promptable segmenter** — 이미 찾아둔 영역(`Split_objects` 가 만든
frame `info` 의 객체 bbox)을 box 프롬프트로 줘 깨끗한 segmentation mask(학습용 실루엣)를 얻는 게
목적이다. `class_id` 는 backend 가 정하지 않고 기존 객체 값을 **그대로 유지**한다.

- **`_base.py::Segment`** — 등록되는 유일한 분할 프로세스(모델 무관, plain box→best mask).
  `unit: frame` 으로 `meta`/`stem` 을 통해 frame `info` 의 객체(stem) 전체를 읽어, backend 이미지
  인코딩을 **프레임당 1회**(`encode`)만 돌리고 객체 box 마다 가벼운 `run` 디코드로 분할한다(비싼
  인코딩 1회 = batch 이득; 객체 수만큼 인코딩 반복 안 함). best mask 로 (1) 인스턴스 라벨맵
  `segment`(픽셀=obj_id+1) 재칠 (2) bbox 를 mask 기준 재계산. best mask 그대로 채택(`conf=0`;
  우리가 지목한 영역이라 점수로 거르지 않음), `min_area` 미만만 버린다.
  - 출력 `segment` 는 config outputs(`{to: storage, level: frame, type: segmap}`)로 저장, `object`
    는 flow 가 frame `info` 의 객체(stem) entry 를 교체(leaf 는 보존).
  - **영역 제거(구멍/슬릿 carve)는 여기 넣지 않는다** — SAM3 는 순수 분할만 하고, carve 는
    downstream process(edge·fill·combine)로 flow 에서 조합한다. 예: `segment` → `carve_color_holes`
    → `split_objects` (`config/run/extract_sam_hole_by_fill_flows.yaml`).
