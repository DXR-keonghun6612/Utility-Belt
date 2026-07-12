# TODO — gui/

dataset_meta 중심 — 보유 `Pipeline` 하나(meta 단일 소스), 본문은 stem 목록(3-상태 뱃지 작업/검수/보류)과
임베드 `Stem_editor`, id_map/params. Converter·flow·Sampler 는 비모달 창. 전이/삭제는 백그라운드.
구조는 [`README.md`](README.md).

완료 이력은 git. 여기엔 남은 것만 — **A. 구조 리팩**(north-star 로의 이주) → **B. UI 확장**(제품 방향).
전체가 향하는 목적지는 아래 **north-star**.

---

## 목적지 아키텍처 — 구성(page) ↔ 연결(app) 2축 (north-star, 지금 적용 아님)

gui 는 **상호작용 계층**(핵심 기능은 `core/`). 상호작용을 두 축으로 가른다:

- **구성 (page)** — `widgets/` 를 바탕으로 조립한 **독립 창/레이아웃 하나** = `*_page/`. 자기 완결
  표현 단위. 전역 상태·core 소유 없이, 필요한 핸들은 주입받는다.
- **연결 (app)** — `app/` 이 각 page 의 dialog/layout 을 **가져다 배선**하고 보유 `Pipeline`(정본 단일
  소스)을 소유·주입한다. 총괄만 하고 표현은 안 가짐.

즉 **총괄=소유(place), 부분=주입(contract)** — tooling.md 의 *"라이프사이클은 store 소유, 바인더는
조율"* 을 UI 에 적용. `get_pipeline` 주입이 이미 이 계약을 런타임에서 실현 중(다이얼로그 다수가
core-free)이니, 그걸 **디렉터리 구성 원리로 승격**한다.

### 도메인 미러링 — Pipeline 객체 그래프를 따른다
core 모듈트리가 아니라 **Pipeline 인스턴스**(`core/_base.py`: `root` + 정본 `meta` 1 + named tasker N)를
미러링한다. `Convert()`/`Run()` 은 `self.meta` 를 생성·enrich, `Sample`/`Export`/`Delete` 는 name-keyed tasker.

```
gui/
  widgets/  form/  steps/        # 표현 프리미티브 (core 무의존 / registry 반영)
  _worker.py  _io.py             # 중립 인프라 (async · recipe I/O)
  app/                           # 연결: Pipeline 소유 + page 창·다이얼로그 배선·주입
  meta_page/                     # 구성: 정본 편집 창 하나 (주입 수신, 싱글턴)
    view/ (今 meta_view) · edit/ (今 verify) · convert/ (今 converter) · run/
    _adapter.py                  # core.schema ↔ 위젯 seam (갈래 소유)
    sample/ (今 sampler)         # 파생 갈래 (meta 입력 → 1:N tasker)
```

- **converter·run 은 "빌더 3형제"가 아니라 정본 생성·enrich 연산** → `meta_page` 소속. sampler 는
  파생 → `meta_page/sample/`. 셋의 recipe-dialog 유사성은 표현 축 착시(W2 베이스는 위젯 레벨만).
- **edit 는 Pipeline peer 아님** — `meta_page` 의 깊은 주석-편집 surface(view 와 `_adapter` 공유).
- **1:1(meta, 싱글턴) vs 1:N(sample, 컬렉션 매니저) 비대칭**은 구조로 드러낸다.

### steps 미래 — card(1D) → block/node-graph (Simulink 형)
현재 `steps/` 는 선형 카드 체인. 목표는 **block 기반 인터랙티브 연결 편집기**. 도메인 모델은 이미 그래프 —
`Process_step` 의 inputs 배선·slots 재배선·outputs 라우팅이 곧 포트/엣지고, 카드는 그 그래프의 *선형
표현*일 뿐. `to_config()`/`load()` config-dict 이 **고정 계약**이라 표현을 card→node-graph 로 갈아끼워도
run/sample 소비처는 무변경. steps/ 를 지금 중립 패키지로 떼는 게 그 준비(W1).

---

## ❓ 논의 대상 — **seam 이 없다** (이념과 실제의 괴리)

[`README.md`](README.md) 는 *"core 접점은 갈래 내부, `_adapter.py` 가 seam"* 이라고 말한다. **실제는
아니다** — `Data_Ref` 가 7개 파일, `Dataset_Meta` 가 7개 파일에 흩어져 있다(`edit/`·`view/`·`sample/`).
`_adapter` 는 seam 이 아니라 그중 하나일 뿐이다.

**이게 실해로 나타났다.** core 4분할 후 gui sweep 을 grep 패턴으로 돌렸는데, **패턴에 없던 `meta.params`**
가 살아남아 root 를 여는 순간 죽었다. 접점이 한 곳에 모였다면 거기만 보면 됐다 — 흩어져 있으니 "무엇을
빠뜨렸는지" 알 방법이 없었다.

**당장의 방어는 검사다** — [`test_surfaces.py`](test_surfaces.py) 가 offscreen 으로 **모든 surface 를 실제로
띄운다**. 죽은 API 는 그 줄이 *실행될 때* 터지므로 compile·import 로는 못 잡고, 이 검사만이 잡는다.

**구조적 답은 아직 없다.** 두 갈래:
- **(a) 진짜 seam 을 만든다** — 위젯이 `Data_Ref`/`Dataset_Meta` 를 아예 못 보게 view-model 을 세운다.
  파급이 한 곳에 모이지만, 도구 규모에 비해 무겁고 seam 이 core 타입을 그대로 베낀 껍데기가 되기 쉽다.
- **(b) 도메인 타입을 gui 의 어휘로 인정한다** — `Data_Ref` 는 도메인 언어이지 core 의 사물이 아니라고
  보고, README 의 거짓 주장을 지운다. 대신 검사(위)로 지킨다.

지금은 **(b) + 검사**로 서 있다. (a) 가 필요해지는 신호는 "core API 가 바뀔 때마다 위젯 N개를 고친다"가
**반복될 때**다. 한 번으로는 근거가 약하다.

---

## A. 구조 리팩 — north-star 로의 이주 (W1–W4 완료, W5 잔여)

**W1–W4 실행 완료 — 위 north-star 구조가 이제 실제 구조다.** W1(process-chain → `gui/steps`,
`_flow_card` 807→213) · `widgets/` 서브패키지화(`image`/`rows`/`list_editor`) · **W2**(정본 도메인 →
`meta_page/{view,edit,convert,run,sample,_adapter}` git mv) · **W3**(`page/`→`app/`, `Main_page` 의 워커·
전이·삭제를 `Meta_ops` 로 분리, `_converter_dialog`→`meta_page/convert/_dialog`). **W4**(recipe-dialog 공통
베이스)는 payoff 얇아 **보류**(아래 근거). 상세 이력은 git.

### W5 — 잔여 (낮은 우선순위)
- [x] store_io 표기 정정 + 이동 반영 문서(README 헤더·상대링크·gui 구조표) — 완료.
- [ ] `app/_main.py`: meta 가져오기·비우기(`_on_import_meta`·`_on_clear_all`)는 아직 셸에 남음 —
      필요 시 `_session` helper 로 추가 분리(당장은 응집 OK).
- [ ] `edit/_editor.py`(598): undo/redo/snapshot 를 `_history` 로 더 축소. 응집 높아 **낮은 우선순위**.

> **W4 보류 근거.** 진짜 공유분(`Pop_dialog`·`save_dict`/`load_dict`)은 이미 `widgets`·`_io` 로 팩터됨.
> 남는 공통은 save/load 버튼 배선(~4줄)뿐인데 본문·수명이 이질적(Run=edit-only · Converter=임베드 패널
> self-run · Sampler=목록+빌더+self-run+export+뷰어) → 최소 추상화상 보류. **dialog 계층 정리는 이후 도메인
> 기준 재편 때 한번에**(현재 구조 그대로 두고 진행).

---

## B. UI 확장 — sample 갈래 격상 · steps 그래프화 (제품 방향, 설계 단계)

**동기.** north-star 로 Pipeline 객체 그래프(정본 `meta` 1 + tasker N)를 미러링하면, sample 은
`meta_page/sample/` 의 **파생 갈래**다 — 정본 싱글턴과 비대칭인 **1:N 컬렉션 매니저**. 지금은 display-only
(`_viewer`)에 그친다. → 파생 갈래를 **제1 편집 surface** 로 격상하고, 편집 표현(steps)을 그래프로 끌어올린다.
(A 의 이주가 선행 — 아래는 그 위의 제품 방향.)

### B1. sample 편집 surface (display-only → editable)
- [ ] `meta_page/sample/_viewer` 를 뷰어 → **편집 surface** 로 확장. 현재 유일 편집인 class 재배정(정본
      write-back)을 넘어 sample 산출물 자체 큐레이션.
- [ ] sample-local 큐레이션(정본 write-back 아님) 스코프 — 예: "**학습셋에서 빼기(exclude)**"(미구현).
      정본 편집 vs sample-local 편집 경계를 UI 에서 명확히.

### B2. sample 데이터 모델 — 입력(기준) vs 라벨(연동)
- **입력(input)** — 생성 즉시 **baseline**, 불변(crop 픽셀은 class 무관 고정). 재-crop 없이 굳는다.
- **라벨(label)** — 정본에 **연동(sync)**, write-back(`class_id` 인라인 attr → `source_stem`/`source_obj`
      역참조로 정본 obj 갱신).
- [ ] 편집 surface(B1)에서 둘 분리 — 입력은 고정 참조, 라벨은 편집·연동 레이어.
- [ ] 데이터 모델 지지 검토 — 현재 `Data_Ref` 트리서 입력/라벨 성격이 암묵적(crop=payload, class_id=attr).
      **core/sample 스키마에 input/label 명시**할지 판단(연동 방향·write-back 계약 포함) → core 파급, 착수
      전 core 와 함께 설계. cf. [[project_sample_tasker_layer]].

### B3. steps 표현 — card(1D) → block/node-graph (Simulink 형)
- [ ] `gui/steps/` 표현을 선형 카드 → **block 기반 인터랙티브 연결 편집기**로. 도메인 모델은 이미 그래프
      (`Process_step` inputs/slots/outputs = 포트/엣지), `to_config()`/`load()` 계약 고정이라 소비처
      (run·sample) **무변경** — 표현만 교체. north-star "steps 미래" 참조.

### 열린 설계 질문 (B 착수 전 확정)
- [ ] **UI 패러다임** — app 이 meta_page 창들을 어떻게 노출하나? meta 중심 유지 전제(급격한 stepper 아님).
      후보: 상시 패널/사이드바 vs 단계 네비.
- [ ] sample 편집 ↔ 메인 meta 뷰 **동기화 계약** — 라벨 write-back 시 `meta_changed` 전파 확장.
- [ ] 입력/라벨 구분이 classification 외 task(detection 등)에서 매핑 (입력=image · 라벨=bbox/mask).

---

## C. 기존 후속 기능 (소품)

- [ ] Run "중단" 협조적 처리 — `Pipeline.Run` 이 stop flag 를 받도록 core 보강 (현재 없음)
- [ ] `shared` dict 값 타입 보존 (현재 문자열만 입력됨)
- [ ] 새 converter 타입(coco/yolo 등) UI — `_CONVERTER_WIDGETS` 등록
