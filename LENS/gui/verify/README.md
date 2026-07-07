# gui/verify/

stem 한 장의 검수/편집 — 재사용 편집 surface(`Stem_editor`) + 팝아웃 다이얼로그.

`Stem_editor` 는 stem 목록·내비게이션을 갖지 않는다. 호출 측(본문 `Meta_view` / 팝아웃
`Stem_edit_dialog`)이 `load_stem` 으로 이 위젯을 몬다 — 임베드든 팝아웃이든 같은 위젯.

---

## 레이아웃

base 이미지 + mask/bbox 오버레이(좌) + 데이터/object 편집(우).

## 로드/저장

stem 파일은 그 stem 의 상태 버킷(`{root}/{state}`)에 산다 — 로드/저장 모두
`meta.State_root(meta.State_of(stem))` 기준. 저장은 작업 사본을 그 버킷에 되쓴다. 상태 승격은
별개다(호출 측 버튼이 `Pipeline.Move`).

## 구성

| 파일 | 역할 |
|---|---|
| `_editor` | 편집 surface (좌 오버레이 + 우 편집). 작업 사본으로 편집, 저장 시 되쓴다 |
| `_annotation` | object 트리 — 시각화 토글·값 편집·mask 브러시·병합. mask 는 프레임 segment(인스턴스 라벨맵)에서 파생 |
| `_overlay` | base + mask/bbox 합성 (검증 없이 보이는 대로) |
| `_draw` | 인터랙션 컨트롤러 — 조작(view/bbox/paint/erase) × 모양(brush/polygon/circle) + 진행 중 transient 상태 소유, 영속은 editor 백레퍼런스로. mask 편집은 그리기·지우기 × 브러시·다각형·원 6조합 |
| `_segment` | 저장 시 객체별 mask → 인스턴스 segment 한 장 (obj_id 재번호). 순수 함수 |
| `_history` | undo/redo 스택 인덱스 관리 (스냅샷 생성/복원은 호출 측 콜백) |
| `_edit_form` | object 값(class_id/obj_id/bbox) 폼 |
| `_helpers` | 색 아이콘 + bbox 기하 |
