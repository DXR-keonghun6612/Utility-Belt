# gui/widgets/

공용 저수준 위젯 — 도메인 비의존(core 의존 0), PySide6 + OpenCV/numpy 만으로 동작.

상위 패널이 조립해 쓰는 재사용 단위. 도메인 행/에디터는 각 패널이 `List_row`/`List_editor` 를
상속해 만든다. 값→트리아이템처럼 도메인을 아는 헬퍼는 `gui/_meta_tree.py` 에 둔다.

---

## 동적 list editor (베이스)

세 곳(converter glob · run outputs · key/value)이 복붙하던 "행 추가/삭제 + 직렬화" 골격을 모은다.
메커니즘만 베이스가 갖고, 행의 내용(필드·검증·직렬화)은 서브클래스가 `_make_row`/`to_config` 로 채운다.

| 클래스 | 역할 |
|---|---|
| `List_row` | `changed`+`remove_requested(self)` 시그널 + ✕ 버튼. `to_config` 는 서브클래스 |
| `List_editor` | 행 목록 + 추가 버튼. 기본 dict 직렬화(key→spec), 행 수명 관리 |
| `Pair_list_editor` | list 직렬화(`pairs`/`set_pairs`) key/value 편집기 (중복 key·순서 허용) |

## 그 외

| 파일 | 역할 |
|---|---|
| `_dialog` (`Pop_dialog`) | 팝아웃 다이얼로그 베이스 — 제목·크기·본문·하단 버튼바 (Converter·flow·stem 공용) |
| `_image` (`Image_label`) | 줌·스크롤 이미지 라벨 |
| `_rows` | 경로 행 · 실수/정수 슬라이더 행 |
| `_tree` | `QTreeWidget` 설정 헬퍼 (컬럼/헤더/resize) |
| `_layout` | 위젯 수명(`drop`) · 레이아웃 재배치(`reorder`) |
| `_convert` | numpy(BGR/gray) → `QPixmap` (패키지 내부 전용) |
