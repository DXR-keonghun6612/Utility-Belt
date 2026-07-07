# gui/form/

파라미터 폼 자동 생성 — process/모델의 파라미터를 introspect 해 타입별 위젯으로 만든다.

`_spec.py`(spec 추출·타입 판별) → `_form.py`(위젯 생성·값 입출력)로 나뉜다.

---

## spec 추출 — 두 소스를 `_Spec` 으로 정규화

`_Spec(name, type, default, ui)` 리스트를 두 곳에서 뽑는다:

| 소스 | 추출 | UI 메타 |
|---|---|---|
| inner process (callable class) | `inspect.signature(__init__)` + 타입 힌트 | `Annotated[type, UI(...)]` |
| block (Base_Config dataclass) | `dataclasses.fields()` | `field(metadata={"ui": UI(...)})` |

`UI`(label/tip/min/max/step/kind)를 평탄 dict 로 풀어 `_Spec.ui` 에 싣는다. 식별/구조 필드
(`config_type`·`object_type`·`name`·`processes`)는 폼에서 제외한다.

---

## 타입 → 위젯 (`Config_form`)

| 타입 | 위젯 |
|---|---|
| `int` / `float` | 슬라이더 (min/max/step) |
| `bool` | 체크박스 |
| `str` / `list[str]` | 한 줄 입력 (list 는 쉼표 구분) |
| `list[tuple[str,str]]` | pair-list 에디터 |
| `float | None` | 체크박스 + 슬라이더 (해제 시 None) |

값 입출력은 `get()` / `load()`. `load` 는 시그널 차단 후 설정한다.

---

## 모델 주입 (`_Model_form`)

process step 의 nested `model: {type, …}` 편집기. `type` 콤보(빈 값=없음 + `MODEL_BUILDERS`
키)를 고르면 그 빌더의 `__init__` 을 introspect 해 필드를 자동 노출한다 — `MODEL_BUILDERS` 에
타입이 늘면 UI 가 따라온다. pipeline 이 이 스펙을 빌드해 process 에 주입한다.
