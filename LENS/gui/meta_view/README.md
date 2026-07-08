# gui/meta_view/

Dataset_Meta 뷰어 = 메인 본문. 3-pane — 좌 stem 목록 · 가운데 임베드 편집기 · 우 id_map/params.

---

## 구성

- 좌 `Stem_list` — **3-버킷 상태 뱃지(작업/검수/보류)**. 우클릭 = 현재 상태가 아닌 **각 상태로 보내기**·삭제,
  더블클릭 = 팝아웃. 뱃지·카운트·메뉴는 `Dataset_Meta.STATES` 기준 제네릭이라 상태가 늘어도(예: skipped)
  `_BADGE` 한 줄만 더하면 된다. 목록 자체는 meta 를 모른다 (표시·신호·갱신만).
- 가운데 `Stem_editor`(verify/) — 선택 stem 임베드 편집기.
- 우 `Idmap_panel` / `Params_panel` — id_map·params 트리. 편집은 넘겨받은 dict 를 직접 수정하고
  `changed` emit (디스크 저장은 상위가).

## 상태 전이 = 백그라운드 (Move/Delete)

상태 전이·삭제는 **대량 여부와 무관하게 항상 백그라운드**로 돈다 — `Meta_view` 는 요청만 올리고
(`transition_requested`/`remove_requested`), 상위(`Main_page`)가 워커로 `meta.Move`/`meta.Delete` 를 돌리며
진행바에 표시하고 **그동안 `Meta_view` 를 비활성화해 편집을 차단**한다(워커가 데이터를 변형하는 동안 편집 끼어들기 방지).

완료 후 목록 재동기화는 **한 번의 `refresh()`(O(n))** 로 한다 — stem 마다 증분 갱신(`update_state`)은
리스트 전체 재스캔 + 재번호라 O(n²)라서 2만 건이면 폭발했다(과거 "응답 없음"의 실체 = 파일 이동이 아니라
이 목록 재그리기였음). `update_state`/`remove` 는 단일 항목 편집(편집 저장 등)에만 쓴다.

## Pipeline 경유

데이터 라이프사이클은 store 가 소유한다 — 상태 전이 = `meta.Move`, 삭제 = `meta.Delete`, 편집 저장 =
`meta.Save_item(stem)` (호출 측이 `meta.*` 직접). meta 정체성이 바뀌면(`set_pipeline`) 편집기를 폐기·재바인딩한다.
같은 stem 을 보는 팝아웃 창은 저장/이동 시 재로드해 일관성을 맞춘다.
