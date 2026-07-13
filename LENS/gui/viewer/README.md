# gui/viewer/

LEAF type 별 **표현·편집 레지스트리** — core 의 `HANDLER_REGISTRY` 와 **짝**이다. handler 가 "이 값을
어떻게 디스크에 담나"를 정하면, 뷰어는 "이 값을 어떻게 화면에 그리고 고치나"를 정한다. 그래서 **새
handler 를 떨구면 뷰어 하나만 더하면 UI 가 따라온다** — 소비처(트리·캔버스)는 안 고친다.

예전엔 frame leaf·객체·params 를 각각 다른 패널이 **하드코딩해** 그렸다(같은 재귀 타입인데). 순서도
확장성도 없었고, class_id·bbox 는 객체 폼에 박혀 있었다. 여기서 그 물음을 **type 하나당 한 뷰어**로 모은다.

---

## 계약 — 한 노드는 두 가지로 보인다 (`_base.py`)

`Node_viewer`(상태 없는 `classmethod`)는 **payload 만 본다** — 이미 디코드된 값을 받고, 경로도 store 도
모른다. 해당되는 것만 구현한다:

- **layer** — 캔버스에 겹쳐 그릴 raster. 노드 트리의 **체크박스가 표시 여부**다. (`RASTER=True`)
- **panel** — 선택 시 뜨는 값 편집/표시 위젯. 인라인은 `format` 이 위젯을 가른다 — **개념 → 없으면
  파이썬 타입** (`("bbox","list")`→스핀 4개, `("","int")`→스핀, `("","str")`→콤보/입력).
- **summary** — 트리 한 줄 요약.

등록은 handler type 키로(`@Register("image","segmap")`), BRANCH(객체)는 `BRANCH` 키로. `Viewer_for(ref)`
가 조회한다.

## 편집기는 여기 없다 — **자기 계층에 산다** ([`gui/editor`](../editor/README.md))

한때 뷰어가 편집 툴바를 만들었는데, 그건 편집이 타입마다 다른 일인 척한 것이다. 실제 편집 대상은 언제나
**라스터**고 객체는 그 안의 **라벨**이라, 편집은 타입별이 아니라 **구조적**이다.

그 결론이 한동안 "뷰어 패키지가 편집기를 든다"였는데(`_raster_edit.py` 가 여기 있었다), 그건 이 README 가
스스로 부정하는 배치였다. 편집기는 [`gui/editor`](../editor/README.md) 로 나갔다 — 골격(도구·이력·잠금·
조준)과 대상별 편집기(`image/`)로 갈려서, 3d·시퀀스가 들어올 자리가 생겼다.

뷰어가 편집에 대해 말하는 것은 `EDITABLE` **하나뿐**이다 — "이 노드를 조준할 수 있다". **무엇을 어떻게
겨누는지는 트리 구조**(객체 ↔ 프레임의 라벨맵)가 정하고, 그건 [`Data_view`](../meta_page/view/_data_view.py)
가 소유한다 — 뷰어는 트리를 모르고, 편집기는 store 도 트리도 모른다.

---

## 파일

| 파일 | 역할 |
|---|---|
| `_base.py` | 뷰어 계약(`Node_viewer`) + 레지스트리(`Register`/`Viewer_for`/`VIEWERS`/`BRANCH`) |
| `raster.py` | 캔버스에 겹칠 것 — `image`·`segmap`·`rle` (배경/라벨맵/이진 mask) |
| `attr.py` | 인라인 값 — 개념(`bbox`→스핀 4개) → 없으면 파이썬 타입(`int`→스핀, `str`→콤보/입력) |
| `data.py` | 캔버스에 안 그려지는 값 — `array`(요약)·`docs`(중첩 트리) |
| `obj.py` | 객체(BRANCH) — payload 없지만 **편집 주체**(그 mask·bbox). 라벨 = obj_id+1 |
| `_compose.py` | layer 합성 — BGR=배경, segmap=라벨색, 이진=반투명. bbox·라벨 텍스트는 인라인 값이라 따로 온다 |

합성은 **데이터가 무엇인가**만 그린다. 그리는 중인 도형·브러시 커서·bbox 핸들처럼 **아직 데이터가 아닌
것**은 편집기가 그 위에 얹는다(`Image_editor.decorate`) — 그게 두 계층의 경계다.
