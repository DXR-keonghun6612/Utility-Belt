# gui/steps/

process-chain 편집 **공통 모듈** — `run`(Flow_card)과 `sampler`(실체화 체인)가 공유한다.

이전엔 `Process_step`·picker·outputs 편집기가 전부 `run/_flow_card.py` 에 살고 `sampler/_dialog` 가
`from gui.run._flow_card import Process_step` 로 **레이어를 위반**했다. 그 편집 단위를 중립 모듈로 승격하고,
step 추가/삭제/이동 관리(양쪽에 중복이던 것)를 `Step_list` 한 곳에 모았다.

소비처는 **`to_config()` / `load()` config-dict 계약**으로만 붙는다 — 카드가 어떤 위젯이든 상관없이
process config dict 리스트만 주고받는다.

---

## 구성

```text
steps/
├── _picker.py   _Process_picker(+_Process_popup) — 분류 트리 팝업 선택기 (QComboBox 호환 API)
├── _output.py   _Outputs_editor(+_Output_row)   — step 의 outputs 라우팅 규칙 편집 (List_editor 베이스)
├── _step.py     Process_step                     — 타입 선택 + 파라미터 폼 + inputs/slots/outputs 배선
└── _list.py     Step_list                        — Process_step 동적 목록 (add/remove/move + min-count 정책)
```

- **`Process_step`** (공개) — `core.process.PROCESS_REGISTRY` 를 반영해 폼을 자동 생성. 좌=파라미터 폼,
  우=입력 배선(inputs)·출력 재배선(slots)·결과 저장(outputs). `model` 필드 process 는 모델 주입 서브폼.
  배선 규칙의 의미는 [`../../core/process/README.md`](../../core/process/README.md).
- **`Step_list`** (공개) — `Process_step` 체인 컨테이너. `min_count`(per-unit·실체화=1, finalize=0) 미만으론
  안 지운다. 하단 "추가" 버튼을 자체 소유하고, 자신이 `QWidget` 이라 `setEnabled(False)` 한 번으로 전체를
  잠근다(lock 캐스케이드). `outputs_block=True` 면 각 step 의 outputs 가 params 레벨(finalize).

## 왜 중립 모듈인가

- `Process_step` 은 `core.process` 레지스트리에 의존한다 → core 무의존인 `widgets/`·`form/` 에 못 넣는다.
  그래서 `form/_step.py` 가 아니라 별도 `gui/steps/`.
- run·sampler 가 **대등 소비처**다. 한쪽(`run/`)에 두면 다른 쪽이 私모듈을 몰래 import 하게 된다(옛 위반).

## 미래 — card → block/node-graph

현재 표현은 선형 카드 체인. `Process_step` 의 inputs·slots·outputs 배선은 이미 dataflow 그래프의 포트/엣지고,
카드는 그 그래프의 *선형 표현*일 뿐이다. `to_config()`/`load()` 가 고정 계약이라, 표현을 node-graph(Simulink
형)로 갈아끼워도 run·sampler 소비처는 무변경. 이 모듈 경계가 그 교체의 seam 이다. (설계 목표는 `gui/TODO.md`.)
