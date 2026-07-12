# gui/form/

파라미터 폼 자동 생성 — process/모델의 `__init__` 을 introspect 해 타입별 위젯으로 만든다.

`_spec.py`(spec 추출·타입 판별) → `_form.py`(위젯 생성·값 입출력)로 나뉜다.

---

## spec 추출

`inspect.signature(__init__)` + 타입 힌트에서 `_Spec(name, type, default, ui)` 를 뽑는다. UI 메타는
`Annotated[type, UI(label/tip/min/max/step/kind)]` 에서 읽어 평탄 dict 로 싣는다 — 그래서 **process 에
필드를 더하면 UI 가 따라온다**(폼을 손대지 않는다). 식별/구조 필드(`config_type`·`object_type`·`name`·
`processes`)는 제외한다.

> **flow(Stage) 필드는 여기서 안 만든다** — `run/_flow_card` 가 손으로 짓는다(그룹 박스 배치가 의도적).
> 그래서 `Stage` 에 필드가 늘면 카드도 손으로 따라가야 한다(예: `category` 는 아직 UI 에 없다).
> 드리프트 위험은 [`../TODO.md`](../TODO.md).

---

## 타입 → 위젯 (`Config_form`)

| 타입 | 위젯 |
|---|---|
| `int` / `float` | 슬라이더 (min/max/step) |
| `bool` | 체크박스 |
| `str` / `list[str]` | 한 줄 입력 (list 는 쉼표 구분) |
| `list[tuple[str,str]]` | pair-list 에디터 |
| `float \| None` | 체크박스 + 슬라이더 (해제 시 None) |

**모르는 타입은 조용히 넘기지 않고 실패한다.** 위젯이 안 생기면 그 파라미터는 `get()` 에서 빠져 config 에
안 실리고, process 는 **기본값으로 돌아버린다** — 사용자는 값을 넣었다고 믿는데. (실제로 gate 의 `keep` 이
그렇게 샜다.) 그래서 렌더 못 하는 타입은 `TypeError` 로 드러낸다: 위젯을 추가하든지, 다른 위젯이 소유하는
파라미터면 `_DELEGATED` 로 위임하든지 둘 중 하나를 하게 한다.

값 입출력은 `get()` / `load()`. **`load` 는 시그널을 안 낸다** — 복원은 사용자의 편집과 구별되어야 하므로
슬라이더도 `set_value`(시그널 없는 설정)를 쓴다.

---

## 모델 주입 (`_Model_form`)

process step 의 nested `model: {type, …}` 편집기 — `Config_form` 이 **일부러 안 그리는** 유일한 파라미터다
(`_DELEGATED`). `type` 콤보(빈 값=없음 + `MODEL_BUILDERS` 키)를 고르면 그 빌더의 `__init__` 을 introspect
해 필드를 자동 노출한다 — `MODEL_BUILDERS` 에 타입이 늘면 UI 가 따라온다. pipeline 이 이 스펙을 빌드해
process 에 주입한다.
