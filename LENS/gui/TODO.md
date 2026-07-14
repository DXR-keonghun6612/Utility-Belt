# TODO — gui/

dataset_meta 중심 — 보유 `Pipeline` 하나(meta 단일 소스), 본문은 stem 목록(3-상태 뱃지 작업/검수/보류)과
데이터/객체 트리 + `Data_view`(편집기 조준), id_map/params. Converter·flow·Sampler 는 비모달 창.
전이/삭제는 백그라운드. 구조는 [`README.md`](README.md).

완료 이력은 git. 여기엔 남은 것만 — **A. 구조 재편**(3티어로) → **B. UI 확장**(제품 방향).
전체가 향하는 목적지는 아래 **north-star**.

---

## 목적지 아키텍처 — "무엇을 아는가"로 가른 3티어 (north-star, 아직 적용 아님)

gui 는 **상호작용 계층** — core 기능을 포장해 상호작용 도구로 만든다(핵심 기능은 `core/`). 계층을 가르는
기준은 하는 일이 아니라 **core 에서 무엇을 아는가**다(general.md). 그 축으로 재면 gui 는 3티어다:

| 티어 | core 에서 아는 것 | 검사 (import 방향) |
|---|---|---|
| `widgets/` | (없음) — Qt 만, 도메인 무지 | `widgets/ 는 core 를 import 하지 않는다` |
| `<representation>/` | core **값·정의**(`Data_Ref`·`PROCESS_REGISTRY`·`Arg_Info`·순수함수) — **세션은 모름** | `representation 은 Pipeline/Dataset_Meta 를 import 하지 않는다` |
| `app/` | core **런타임**(`Pipeline`·`Dataset_Meta` 인스턴스 + 라이프사이클) 소유·조율 + 페이지 | (최상위) |

- **widgets** = 기능과 연결하기 위한 상호작용 프리미티브(core 무지). **app** = 그 widgets 로 짓는 상호작용
  공간(페이지) + core 소유·배선. **representation** = 그 사이 — core 값을 화면 표현·편집으로 옮기되
  세션은 모르는, 페이지를 넘나들며 공유되는 재사용 층(`steps` 는 run·sample 공유, `viewer` 는 트리 전체,
  `editor` 는 앱 싱글턴, `form` 은 파라미터 폼 공용).
- 의존은 한 방향 — `widgets ← representation ← app`. 산문이 아니라 `core/test_layering.py` 처럼
  **import 검사**로 못박는다(위 표의 두 검사).

```
gui/
  widgets/                 # core 무지 (Qt). image/ · rows/ · list_editor/ + Collapsible·Tree·Dialog
  <representation>/        # core 값·정의는 알되 세션(Pipeline/store)은 모름
    viewer/  editor/  steps/  form/
    + meta_page/view 에서 뽑아낸 표현 (node_tree · data_view)
  app/                     # core 런타임 소유·조율 + 페이지
    _main.py  _meta_ops.py   (Main_page · Meta_ops)
    meta_page/             # 유일 페이지 = 세션에 표현을 배선 (view/convert/run/sample)
  _io.py  _worker.py       # 중립 인프라 (recipe I/O · async 워커)
```

- **왜 지금 구조가 "나누다 만" 인가.** 옛 north-star 는 "구성(page) ↔ 연결(app) 2축" 이었는데, ①페이지가
  `meta_page` **하나뿐**이라 `*_page/` 티어가 무의미하고, ②`viewer/editor/steps/form` 이 core 를 알면서도
  `widgets/` 와 나란히 flat 하게 떠 있어 세 번째 티어(표현)가 디렉터리로 안 드러났다. 실측으로 확정 —
  `widgets/` 만 core 의존 0, 나머지 넷은 core 값·정의를 알되 Pipeline/store 는 안 씀.
- **app 내부는 Pipeline 객체 그래프(정본 meta 1 + named tasker N)를 미러링한다.** `meta_page` = 정본 싱글턴,
  `meta_page/sample` = 파생 1:N tasker. 이 비대칭은 페이지 하위 구조로 드러난다.

---

## ✅ 합의됨 — 3티어로의 재편 (재작성 선행 → mv + 검사)

경계가 바뀌는 **재분해**라 폴더 `mv` 로는 표현 안 된다(general.md: `mv` 는 집합 보존 — 소속이 바뀌면
재작성). 순서 — ①재작성으로 경계 확정(파일 제자리) → ②`mv` + 검사.

- [ ] **① `meta_page/view` 티어 분리 (재작성).** 경계가 `view/` **한가운데**를 지난다 — 세션에서 실측 확정
      (`grep -hoE 'core\.[a-z_]+' view/*.py`):
      - **표현으로 뺀다** (schema-only, store·port 안 봄): `_data_view.py` · `_node_tree.py`. `viewer`·`editor`
        의 형제(`_data_view` = README 가 "두 계층의 통역"이라 부르는 접합부).
      - **app 에 남는다** (세션/IO): `_view.py`(Pipeline 소유 — **import 없이** 주입으로 든다) ·
        `_node_panel.py`·`_params_panel.py`(`core.port` — payload I/O·`port.Blank`) · `_stem_list.py`
        (`core.store` — Bucket 읽기).
      - **`_node_panel`·`_params_panel` 은 안 가른다.** 툴바(표현)와 port I/O(런타임)를 겸하지만, 툴바는
        `Node_tree`(표현)를 **호스트**할 뿐이라 app 이 표현 위젯을 조립하는 정상 방향이다(app→representation).
        세션에서 이 둘이 `port.Blank`·`store.Add_leaf` 를 직접 부르는 걸로 app-측이 확증됐다.
- [ ] **② 경계 확정 후 폴더 이동 (`mv`, 집합 보존) + 검사 도입.** `viewer/editor/steps/form`(+ ①에서 뺀
      `_data_view`·`_node_tree`) → 표현 티어, `meta_page` → `app/`. 검사 2개를 **같은 커밋에**:
      - **widgets ↛ core** — `grep -rE '(^|[^.])\bcore\b' widgets/` 비어야 함.
      - **representation ↛ 세션·IO** — `grep -rE 'core\.(store|port)|Dataset_Meta|Pipeline' <representation>/`
        비어야 함. (표현은 `core.schema`·`core.process`·`core.typing`·`core.constant` 는 알아도 되지만
        `core.store`·`core.port` 는 모른다 — 세션·IO 라. viewer/editor/steps/form 은 이미 0 으로 측정됨.)
      - **주의: `_view.py` 는 import 검사에 안 걸린다** — Pipeline 을 import 없이 **주입**으로 들기 때문.
        페이지라 app 인 건 소속으로 정하지 검사로 정하지 않는다(검사는 표현이 세션을 안 당기는 것만 막는다).
- [ ] **app 셸 응집.** `_main.py` 의 `_on_import_meta`·`_on_clear_all` 은 아직 셸에 남음 — 필요 시
      `_session` helper 로 분리(당장은 응집 OK, 재편과 함께 판단).

### 착수 기준 — 표현 티어 공개 계약 (세션에서 드러난 seam)

app 이 표현을 **아래로 부르는** 지점이 곧 표현 티어의 공개 API 다. 추출할 때 이것만 public 으로 남기고
내부(`_resolve`·`_aim`·`_redraw`…)는 감춘다. 역방향(표현→세션) 호출이 하나도 없다는 게 티어가 서는 근거:

- **`Data_view`** ← Meta_view·Node_panel 이 부른다: `show_node(node, *, candidates, aim, editable)` ·
  `show_layers` · `set_objects` · `segment_node` · `canvas_size` · `focus_editor` · `set_editable` · `set_context`;
  시그널 `edited` / `raster_edited` / `object_picked`.
- **`Node_tree`** ← 세 패널이 부른다: `load` · `checked_layers` · `top_nodes` · `current_node` ·
  `selected_nodes` · `select_node`/`select_index`/`select_name` · `check_node` · `set_editable`;
  시그널 `selected` / `layers_changed`.
- **정방향 배선은 그대로 둔다** (app→representation, 검사 통과): `set_editable`→`Data_view`→`editor.set_locked` ·
  Tab eventFilter(Meta_view)→`Data_view.focus_editor`+`Stem_list.focus_list` · `edit_requested`(params)→
  `Data_view.show_node`. 이건 티어 위반이 아니라 소유자가 부품을 구동하는 정상 흐름이다.

## ❓ 논의 대상 — 재편의 열린 질문

- **표현 티어의 이름** — `representation`? `render`? 아직 미정.
- **`_stem_list` — app 유지 vs plain-list 로 표현화.** 지금은 `Dataset_Meta.CATEGORIES`(상수)+`.Bucket`
  (읽기)만 아는 read-only 라 app 에 둬도 되지만, 버킷을 plain list 로 받으면 표현 티어로 뺄 수 있다
  (뱃지·순번·포커스 로직은 이미 meta 무지). 당장은 app(store 읽기)로 두는 게 최소 변경 — 착수 시 판단.

> **결정 — top-level 3티어** (`app/` 안에 접지 않음). 셋(widgets ← representation ← app)이 서로를 안 아는
> 관계가 디렉터리로 그대로 드러난다. `app/components/` 로 접는 안은 폐기 — 재편 완료 시 이 결정을 README 로.

---

## ✅ 합의됨 — Tab 포커스는 단방향(목록→편집기), 복귀는 저장

지금은 `Meta_view._toggle_focus` 가 stem 목록 ↔ 편집기를 **양방향 토글**한다. 이걸 **한 방향 + 저장 복귀**로
바꾼다 — 동선이 "목록에서 고르다가 → 작업 → 저장 → 목록으로" 로 선형이라 깔끔하다(돌아가 다시 고를 땐
어차피 클릭한다).

- [ ] **Tab = 목록 → 편집기 (작업 들어가기)만.** 편집기에서 Tab 은 목록으로 안 돌아간다(no-op).
      `_toggle_focus` 를 `if self._stem_list.list_has_focus(): self._data.focus_editor()` 한 방향으로.
- [ ] **저장이 복귀를 든다.** `_on_save`(`Ctrl+S`·[저장]) 끝에 `self._stem_list.focus_list()` — 저장하면
      포커스가 목록으로 돌아가 바로 화살표로 다음 stem 을 고른다. (`_on_save` 는 이미 `refresh(keep=)` 로
      목록을 다시 그리지만 포커스는 안 옮기니, 명시적으로 준다.)
- 편집기 → 목록의 **다른** 경로(클릭)는 그대로 — 필요하면 stem 을 다시 클릭해 고른다.
- **재편 ①과 함께 한다.** `_view.py`(Meta_view)는 재편 후 app 티어에 남고 ①에서 어차피 재작성되니
  (`_data_view`·`_node_tree` 추출 + seam 배선), 이 Tab 변경(`_toggle_focus`·`_on_save` 2줄)을 그때 같이
  얹는다 — 따로 착수 안 함. (mv 는 로직과 가르지만 ①은 이미 재작성이라 이 로직이 거기 산다.)

## ✅ 합의됨 — stem 팝아웃이 죽어 있다

`Stem_list` 는 더블클릭에 `popout_requested` 를 쏘지만 **받는 데가 없다**. 새 구조에서 팝아웃은
**(데이터·객체 트리 + `Data_view`) 묶음을 stem 하나로 띄우는 것**이라, 그 묶음을 `Meta_view` 에서
떼어내야 한다(stem 목록·저장 버튼은 안 따라간다). — 이 분리는 위 **재편 ①**(표현 티어 분리)과 같은
작업이다: 표현 묶음이 티어로 떨어져 나오면 임베드/팝아웃이 같은 위젯을 쓴다.

- [ ] `Meta_view` 에서 stem 편집 surface 분리 → 본문 임베드 / 팝아웃 창이 같은 위젯을 쓴다.
      떼기 전까지 `popout_requested` 는 연결 없이 남는다(지우지 않는다 — 요구는 살아 있다).

## ✅ 합의됨 — flow 카드가 `Stage` 필드를 손으로 복제한다 (드리프트)

`run/_flow_card` 는 `object_type`·`name`·`unit`·`cacheable`·`shared`·`carry` 를 손으로 짓는다(그룹 박스
배치가 의도적이라 그 자체는 타당). 문제는 **`Stage` 에 필드가 늘면 카드가 조용히 뒤처진다**는 것.

- [ ] `Stage.category`(`str | list[str]`)가 UI 에 없다 — 학습셋 전 split 을 도는 분석 flow 를 GUI 로
      만들 수 없다. `analysis` 를 flow 로 옮기면(→ [`../core/process/TODO.md`](../core/process/TODO.md)) 필요.
- [ ] 드리프트를 검사로 잡을지 — "`Stage` 의 폼 대상 필드 ⊆ 카드가 짓는 위젯" 한 줄이면 다음 필드
      추가 때 조용히 안 뒤처진다.

## ❓ 논의 대상 — seam (store-API 는 아직 흩어져 있다)

접점은 두 축 — (1) LEAF 값 → 표현·편집, (2) `Dataset_Meta` store-API(Load/Save/Move/…) 사용.

- **(1) 값→표현 — 위 재편이 이 축을 티어로 승격한다.** [`viewer/`](viewer/README.md) 레지스트리(core
  `HANDLER_REGISTRY` 짝)가 그 자리 — 새 handler 를 떨구면 UI 가 따라온다. 재편 후엔 이 축이 **표현 티어**
  전체로 명시된다.
- **(2) store-API — 여전히 흩어져 있다**(`view/`·`sample/` 가 `Data_Ref`/`Dataset_Meta` 직접 사용). 방어는
  검사 — [`test_surfaces.py`](test_surfaces.py) 가 offscreen 으로 **모든 surface 를 실제로 띄운다**(죽은
  API 는 실행돼야 터져 compile·import 로 못 잡는다). 진짜 seam(뷰모델 껍데기)이 필요해지는 신호는
  "core API 가 바뀔 때마다 위젯 N개를 고친다"가 **반복될 때**다 — 지금은 (b)+검사로 선다.

---

## B. UI 확장 — sample 갈래 격상 · steps 그래프화 (제품 방향, 설계 단계)

**동기.** app 이 Pipeline 객체 그래프(정본 `meta` 1 + tasker N)를 미러링하면, sample 은 `meta_page/sample/`
의 **파생 갈래** = 1:N 컬렉션 매니저. 지금은 display-only(`_sample_view`)에 그친다. → 파생 갈래를 **제1
편집 surface** 로 격상하고, 편집 표현(steps)을 그래프로 끌어올린다. (A 의 재편이 선행.)

> **뷰어를 붙이나 마나는 파생이 도메인을 바꾸나로 갈린다** — 새 도메인 생성(classification=per-object crop)은
> 전용 뷰어, 정본 도메인 재표현(detection·instance-seg 는 정본 geometry 참조)은 정본 stem 뷰어 재사용
> (class-그룹 트리는 생성형 전용이라 frame 마다 객체가 다른 재표현형엔 안 맞음). 축·모델은
> [`../core/store/TODO.md`](../core/store/TODO.md) "결정됨 — 파생이 도메인을 바꾸나(새 데이터냐)가
> 뷰어·복제·export 를 가른다" 가 소유한다. **결론 남** — detection·instance-seg frame 뷰 = split→stem
> 목록(정본 뷰어 재사용, class-트리 아님). ★ port 전면 재구성 ④ 로 실행: [`../core/TODO.md`](../core/TODO.md).

### B1. sample 편집 surface (display-only → editable)
- [ ] `meta_page/sample/_sample_view` 를 뷰어 → **편집 surface** 로 확장. 현재 유일 편집인 class 재배정(정본
      write-back)을 넘어 sample 산출물 자체 큐레이션.
- [ ] sample-local 큐레이션(정본 write-back 아님) 스코프 — 예: "**학습셋에서 빼기(exclude)**"(미구현).
      정본 편집 vs sample-local 편집 경계를 UI 에서 명확히.

### B2. sample 데이터 모델 — 입력(기준) vs 라벨(연동)
- **입력(input)** — 생성 즉시 baseline, 불변(crop 픽셀은 class 무관 고정). 재-crop 없이 굳는다.
- **라벨(label)** — 정본에 연동(sync), write-back(`class_id` 인라인 attr → `source_stem`/`source_obj`
      역참조로 정본 obj 갱신).
- [ ] 편집 surface(B1)에서 둘 분리 — 입력은 고정 참조, 라벨은 편집·연동 레이어.
- [ ] 데이터 모델 지지 검토 — 현재 `Data_Ref` 트리서 입력/라벨 성격이 암묵적(crop=payload, class_id=attr).
      **core/sample 스키마에 input/label 명시**할지 판단(연동 방향·write-back 계약 포함) → core 파급, 착수
      전 core 와 함께 설계. cf. [[project_sample_tasker_layer]].

### B3. steps 표현 — card(1D) → block/node-graph (Simulink 형)
- [ ] `gui/steps/` 표현을 선형 카드 → **block 기반 인터랙티브 연결 편집기**로. 도메인 모델은 이미 그래프
      (`Process_step` inputs/slots/outputs = 포트/엣지), `to_config()`/`load()` config-dict 이 **고정 계약**
      이라 표현을 갈아끼워도 소비처(run·sample) **무변경** — 표현만 교체.
- **입력은 step 이 아니라 source 노드다.** flow 는 파일 경로 → `store.Resolve` 로 leaf 를 ctx 에 seed 하는데
      (`_block_ctx`), 이 읽기는 체인 **밖** 암묵 입력이라 선형 카드엔 표현이 없다(그래서 dataflow 가 "어디서
      frame 이 오나"를 안 보여준다). 블럭에선 이게 첫 클래스 **source 노드**. resolve 는 `node.Leaves()` 를
      `port.Load` **타입 디스패치**로 푸는지라 **타입-제네릭**(이미지 전용 아님) — source 노드도 leaf 타입
      불문 제네릭이라야 하고, `IMREAD_UNCHANGED` 같은 **포맷 전용 flag 를 flow config 에 박지 않는다**
      (이후 이질 데이터가 들어와도 안 깨지게).
- **착수 방아쇠 — 비선형 토폴로지가 상수가 될 때.** source 노드 하나는 미학이라 선형 카드로도 (고정 헤더로)
      처리된다 → 그것만으론 블럭 전환을 **강제하지 않는다**. 블럭이 값을 하는 건 슬롯 이름 매칭을 눈으로
      따라가야 하는 **분기·병합·다중 이질 입력**이 흔해질 때다 (`fill_edge`×2 → `other` → `combine_mask` 두
      입력, gate 분기, image+타 타입 동시 입력). 그 전엔 카드가 최소. → 입력 노드를 지금 선형 카드에
      볼트온하지 않는다(블럭 전환 시 버려질 작업).

### 열린 설계 질문 (B 착수 전 확정)
- [ ] **UI 패러다임** — app 이 페이지·창들을 어떻게 노출하나? meta 중심 유지 전제(급격한 stepper 아님).
      후보: 상시 패널/사이드바 vs 단계 네비.
- [ ] sample 편집 ↔ 메인 meta 뷰 **동기화 계약** — 라벨 write-back 시 `meta_changed` 전파 확장.
- [ ] 입력/라벨 구분이 classification 외 task(detection 등)에서 매핑(입력=image · 라벨=bbox/mask).

---

## C. 기존 후속 기능 (소품)

- [ ] Run "중단" 협조적 처리 — `Pipeline.Run` 이 stop flag 를 받도록 core 보강 (현재 없음)
- [ ] `shared` dict 값 타입 보존 (현재 문자열만 입력됨)
- [ ] 새 converter 타입(coco/yolo 등) UI — `_CONVERTER_WIDGETS` 등록
