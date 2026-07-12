# model — 무거운 모델에 기대는 유닛

각 유닛의 인자·동작은 그 유닛의 docstring 에 있다. 이 문서는 **backend 와 정책이 왜 갈렸는지**만 다룬다.

---

## backend / 정책 분리

- **backend** (`_sam3.py::Sam3_runner`) — 모델 고유 저수준 프리미티브만: `infer_ctx`(autocast 엔벨로프) ·
  `encode`(프레임 → state) · `run`(state + box → mask·score 를 numpy 로 정규화). **정책은 여기 없다** —
  best mask 선택·이진화·구멍 보존 같은 판단이 들어오는 순간 backend 교체가 불가능해진다.
- **정책** (`segment/`) — backend 위에서 조립하는 **모델-무관** 층. 유닛이 backend 종류를 모른다.
  config 의 `model:` 한 줄로 backend 를 갈아끼우고 정책은 그대로 둔다.

다른 promptable segmenter 로 옮기려면 `infer_ctx`/`encode`/`run` **이 계약만** 구현하면 된다.

**backend 는 검출·분류기가 아니라 promptable segmenter 다** — 이미 찾아둔 영역(`Split_objects` 가 만든
객체 bbox)을 box 프롬프트로 줘 깨끗한 실루엣을 얻는 게 목적이다. 그래서 `class_id` 는 backend 가 정하지
않고 **기존 객체 값을 그대로 유지**한다.

**비싼 인코딩은 프레임당 1회** — 이미지 backbone 을 한 번 돌리고 객체 box 마다 가벼운 디코드만 한다
(객체 수만큼 인코딩을 반복하지 않는다). 이게 `unit: frame` 인 이유다.

**영역 제거(구멍·슬릿 carve)는 여기 넣지 않는다** — backend 는 순수 분할만 하고, carve 는 downstream
유닛(edge·fill·combine)으로 **flow 에서 조합**한다. 여러 도메인을 엮는 일은 유닛이 아니라 config 의 몫이다.

---

무거운 모델은 유닛이 **소유하지 않는다** — pipeline 이 스펙당 1회 빌드해 주입하고 유닛은 핸들만 든다.
모델 type→빌더는 `core/_base.py` 의 `MODEL_BUILDERS`.

> `_sam3.py` 는 **상태를 든 런타임**이라 스트리밍 유닛도 자유함수도 아니다 — 이 층에 있을 것이 아니라는
> 신호다. 열린 논의는 [`../../TODO.md`](../../TODO.md).
