# gui/widgets/

공용 저수준 위젯 — 도메인 비의존(core 의존 0), PySide6 + OpenCV/numpy 만으로 동작.

상위 패널이 조립해 쓰는 재사용 단위. 도메인 행/에디터는 각 패널이 `List_row`/`List_editor` 를
상속해 만든다. 값→트리아이템처럼 도메인을 아는 헬퍼는 `gui/_meta_tree.py` 에 둔다.

---

평평하게 쌓이던 파일을 기능별 서브패키지로 접었다 — 다중객체 파일은 하위 기능으로 쪼갠다. 단일 관심사
파일(`_dialog`/`_tree`/`_layout`/`_collapsible`)만 최상위에 flat 으로 남긴다. 공개 API 는 파사드(`__init__`)
로만 노출 — 소비처는 `from gui.widgets import X` 하나만 안다(서브패키지 경로 비의존).

- `_collapsible` · `Collapsible` — 제목 헤더로 접히는 섹션 (splitter 안에서 접으면 형제가 공간을 가져간다).

## `list_editor/` — 동적 list editor

세 곳(converter glob · run/sampler outputs · key/value)이 복붙하던 "행 추가/삭제 + 직렬화" 골격을 모은다.
메커니즘만 베이스가 갖고, 행의 내용(필드·검증·직렬화)은 서브클래스가 `_make_row`/`to_config` 로 채운다.

| 파일 · 클래스 | 역할 |
|---|---|
| `_base` · `List_row` | `changed`+`remove_requested(self)` 시그널 + ✕ 버튼. `to_config` 는 서브클래스 |
| `_base` · `List_editor` | 행 목록 + 추가 버튼. 기본 dict 직렬화(key→spec), 행 수명 관리 |
| `_pair` · `Pair_list_editor` | list 직렬화(`pairs`/`set_pairs`) key/value 편집기 (중복 key·순서 허용) |

## `image/` · `rows/` — 표시·입력 위젯

| 파일 · 심볼 | 역할 |
|---|---|
| `image/_label` (`Image_label`) | 줌·스크롤 이미지 라벨 |
| `image/_convert` | numpy(BGR/gray) → `QPixmap` (패키지 내부 전용, `_label` 만 사용) |
| `rows/_path` (`Path_row`) | 라벨 + 경로 입력 + 탐색(📁) 행 |
| `rows/_slider` (`Float_slider_row`·`Int_slider_row`) | 슬라이더 ↔ 스핀박스 동기화 입력 행 |

## 최상위 (단일 관심사, flat)

| 파일 | 역할 |
|---|---|
| `_dialog` (`Pop_dialog`) | 팝아웃 다이얼로그 베이스 — 제목·크기·본문·하단 버튼바 (Converter·flow·stem 공용) |
| `_tree` | `QTreeWidget` 설정 헬퍼 (컬럼/헤더/resize) |
| `_layout` | 위젯 수명(`drop`) · 레이아웃 재배치(`reorder`) · 이동 툴버튼(`move_buttons` ▲▼✕) |
