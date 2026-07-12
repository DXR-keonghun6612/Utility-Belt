# gui/meta_page/view/

Dataset_Meta 뷰어 = 메인 본문. 3-pane — 좌 stem 목록 · 가운데 임베드 편집기 · 우 id_map/params.

---

## 구성

- 좌 `Stem_list` — **3-버킷 상태 뱃지(작업/검수/보류)**. 우클릭 = 현재 상태가 아닌 **각 상태로 보내기**·삭제,
  더블클릭 = 팝아웃. 뱃지·카운트·메뉴는 `Dataset_Meta.CATEGORIES` 기준 제네릭이라 상태가 늘어도(예: skipped)
  `_BADGE` 한 줄만 더하면 된다. 목록 자체는 meta 를 모른다 (표시·신호·갱신만). 채울 때 **카테고리
  순서(`CATEGORIES`)는 유지하되 카테고리 안은 stem 이름 오름차순**으로 정렬한다(전이로 순서가 안 뒤섞이게).
- **전이/삭제 후 포커스**(`_next_focus`) — 포커스는 대상을 따라가지 않고 소스 카테고리에 남는다: ① 선택
  중 가장 작은 순번의 한 칸 앞, 없으면 ② 가장 큰 순번 +1(한 칸 뒤). 둘 다 없으면(그 카테고리가 통째로
  비면) ③ **전이**는 이동한 곳으로 따라가고, **삭제**는 목적지가 없으니 다음 카테고리(뒤 우선, 없으면
  앞)로 옮긴다(목록이 통째로 비면 포커스 없음). 작업 **전** 목록에서 대상 stem 을 잡아 `_focus_after` 에
  담고 다음 `load` 가 일회성으로 소비한다(`keep` 덮어씀).
- 가운데 `Stem_editor`(edit/) — 선택 stem 임베드 편집기.
- 우 `Params_panel` — params 트리. id_map 은 별도 패널 없이 params 의 일반 데이터로 함께 표시된다
  (`Data_Ref` 값은 `_adapter.value_node` 가 한 줄 요약으로 편다).

## 상태 전이 = 백그라운드 (Move/Delete)

상태 전이·삭제는 **대량 여부와 무관하게 항상 백그라운드**로 돈다 — `Meta_view` 는 요청만 올리고
(`transition_requested`/`remove_requested`), 상위(app `Meta_ops`)가 워커로 `meta.Move`/`meta.Delete` 를 돌리며
진행바에 표시하고 **그동안 `Meta_view.set_editable(False)` 로 편집만 잠근다**(워커가 데이터를 변형하는
동안 편집 끼어들기 방지). 뷰 전체를 얼리지 않으므로 stem 목록 클릭·이미지 보기·줌·팝아웃은 그대로
되고, 잠기는 건 수정 경로뿐이다 — 전이/삭제 우클릭 메뉴, 편집기의 mask/bbox/object 편집·저장,
id_map 추가/삭제. `set_editable` 은 `Stem_list`·`Stem_editor`(→`Draw_controller`·`_Annotation_panel`)·
열린 팝아웃으로 전파하고, 작업 중 새로 뜬 편집기/팝아웃에도 현재 잠금을 적용한다.

완료 후 목록 재동기화는 **한 번의 `refresh()`(O(n))** 로 한다 — stem 마다 증분 갱신(`update_state`)은
리스트 전체 재스캔 + 재번호라 O(n²)라서 2만 건이면 폭발했다(과거 "응답 없음"의 실체 = 파일 이동이 아니라
이 목록 재그리기였음). `update_state`/`remove` 는 단일 항목 편집(편집 저장 등)에만 쓴다.

## Pipeline 경유

데이터 라이프사이클은 store 가 소유한다 — 상태 전이 = `meta.Move(…)`, 삭제 = `meta.Delete(…)`,
편집 저장 = `meta.Save(stem)` (호출 측이 `meta.*` 직접). meta 정체성이 바뀌면(`set_pipeline`) 편집기를 폐기·재바인딩한다.
같은 stem 을 보는 팝아웃 창은 저장/이동 시 재로드해 일관성을 맞춘다.
