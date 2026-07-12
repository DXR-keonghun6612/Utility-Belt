# gui/meta_page/view/

Dataset_Meta 뷰어 = 메인 본문. 3-pane — 좌 stem 목록 · 가운데 (params·데이터·객체) 트리 · 우 데이터 뷰어.

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
- 가운데 = **세로 3단 접기(`Collapsible`) 트리** — params(dataset-wide) · 데이터(선택 stem) · 객체(선택 stem).
  **같은 재귀 렌더러 `Node_tree` 를 scope 로 세 번 쓴다**(`all`/`leaves`/`objects`). 데이터모델은 하나
  (재귀 `Data_Ref`)지만 **표현 축이 다르다**: raster leaf(`데이터`)는 체크해서 합성하고, 객체(`객체`)는
  골라서 조준·편집한다. `Node_panel` 이 각 트리에 역할별 추가/삭제 툴바를 얹는다(데이터=`+데이터`,
  객체=`+객체`/`+속성`). **객체 툴바는 storage 추가를 안 내놓아** "객체는 payload-free"(geometry 는
  stem 레벨 segment 한 장)가 UI 구조로 강제된다.
- 우 `Data_view` — **체크된 raster 합성 캔버스 + 인스펙터**. 무엇을 어떻게 그리고 고치나는 타입별
  레지스트리 [`gui/viewer`](../../viewer)가 안다(core 의 `HANDLER_REGISTRY` 와 짝). 캔버스 위 `Mask_editor`
  는 **앱에 하나** — 노드를 고르면 그 대상으로 **조준**만 바뀐다. 무엇을 겨눌지는 **구조**가 정한다
  (객체 → 프레임의 segment 에 그 라벨 = obj_id+1, mask leaf → 그 라스터 자체). id_map 은 별도 패널 없이
  params 트리의 일반 데이터로 함께 보이고, `class_id` 를 고를 때만 view 가 id_map 후보를 뷰어에 넘긴다.

## 상태 전이 = 백그라운드 (Move/Delete)

상태 전이·삭제는 **대량 여부와 무관하게 항상 백그라운드**로 돈다 — `Meta_view` 는 요청만 올리고
(`transition_requested`/`remove_requested`), 상위(app `Meta_ops`)가 워커로 `meta.Move`/`meta.Delete` 를 돌리며
진행바에 표시하고 **그동안 `Meta_view.set_editable(False)` 로 편집만 잠근다**(워커가 데이터를 변형하는
동안 편집 끼어들기 방지). 뷰 전체를 얼리지 않으므로 stem 목록 클릭·이미지 보기·줌은 그대로 되고,
잠기는 건 수정 경로뿐이다 — 전이/삭제 우클릭 메뉴, 데이터/객체 트리의 추가/삭제, 캔버스의 mask/bbox
편집, 인스펙터의 인라인 값 편집. `set_editable` 은 `Stem_list`·데이터/객체 `Node_panel`·`Data_view`
(→`Mask_editor`)로 전파한다.

완료 후 목록 재동기화는 **한 번의 `refresh()`(O(n))** 로 한다 — stem 마다 증분 갱신(`update_state`)은
리스트 전체 재스캔 + 재번호라 O(n²)라서 2만 건이면 폭발했다(과거 "응답 없음"의 실체 = 파일 이동이 아니라
이 목록 재그리기였음). `update_state`/`remove` 는 단일 항목 편집(편집 저장 등)에만 쓴다.

## Pipeline 경유 — 라이프사이클은 store 소유

호출 측이 `meta.*` 를 직접 부른다 — 상태 전이 = `meta.Move(…)`, 삭제 = `meta.Delete(…)`, 편집 저장 =
`meta.Save(stem)` (그 item 사이드카만; params 편집은 전체 `Save()`).

- **객체 삭제 = `meta.Remove_object(stem, obj_id)`** — 컨테이너 pop **+ 그 obj 의 segment 라벨 0** 을
  원자적으로 한다(store 소유). 정본은 per-obj mask 를 안 들고 frame-level segment 한 장(픽셀=obj_id+1)에
  담으므로, 컨테이너만 지우면 라벨이 유령 mask 로 남기 때문이다. **빈 자리는 구멍으로 둔다** — obj_id
  재부여·압축은 `Order_objects`(process)의 몫이고, 편집은 정합만 지킨다. 그래서 데이터 leaf 삭제
  (`Delete_node`)와 객체 삭제(`Remove_object`)를 트리가 가른다.
- 캔버스 라스터 편집은 `meta.Route`(payload write) → 그 자리에 다시 꽂기. meta 정체성이 바뀌면
  (`set_pipeline`) 트리를 다시 로드한다.
