# gui/meta_view/

Dataset_Meta 뷰어 = 메인 본문. 3-pane — 좌 stem 목록 · 가운데 임베드 편집기 · 우 id_map/params.

---

## 구성

- 좌 `Stem_list` — 2-버킷 상태 뱃지(변경됨/staged). 우클릭 = staged/modified 로 보내기·삭제,
  더블클릭 = 팝아웃. 목록 자체는 meta 를 모른다 (표시·신호·증분 갱신만).
- 가운데 `Stem_editor`(verify/) — 선택 stem 임베드 편집기.
- 우 `Idmap_panel` / `Params_panel` — id_map·params 트리. 편집은 넘겨받은 dict 를 직접 수정하고
  `changed` emit (디스크 저장은 상위가).

## Pipeline 경유

모든 상태 변경은 `Pipeline` 을 거친다 — 상태 전이 = `meta.Move`, 편집 저장 = meta 갱신 후
`meta.Save_item(stem)`. meta 정체성이 바뀌면(`set_pipeline`) 편집기를 폐기·재바인딩한다. 같은 stem 을
보는 팝아웃 창은 저장/이동 시 재로드해 일관성을 맞춘다.
