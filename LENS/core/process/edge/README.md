# edge — 엣지

edge 를 검출하고(탐색), 닫힌 윤곽으로 다듬어 영역 mask 를 만드는(기본) process 들.
파일 = 중분류: `canny.py`(탐색) / `edge.py`(기본). 탐색법이 늘면 파일을 추가한다(sobel 등).

전형 파이프라인: `detect_edge` → (`close_edge`) → `fill_edge` → `split_objects`,
또는 `detect_edge` → `edge_blob` → `combine_mask` (subtract 모드, mask 안 큰 edge 덩어리 제외),
또는 `segment` → `detect_edge` → `remove_edge_holes` → `split_objects`
(SAM 이 메운 구멍·슬릿을 edge 로 되뚫기).

## 탐색 (`canny.py`)

- **Detect_edge** — raw 프레임에서 cv2 Canny 로 0/255 edge. 기본은 gray 변환 후 한 장에서 Canny
  (OpenCV 표준 — 빠르고 노이즈 적음). `gray=False` 면 채널별 Canny 를 OR 로 합친다 — gray 한 장은
  등휘도 색차(채널 간 색경계)를 놓칠 수 있어, 어느 채널이든 바뀌는 곳을 잡는다. 별도 색공간 변환·
  조명 정규화 없이 raw RGB 에서 바로 검출. 검출 전 옵션 Gaussian blur 로 잡티를 줄인다.

## 기본 (`edge.py`)

- **Close_edge** — 끊긴 edge 를 morphology CLOSE 로 이어 닫는다. Canny edge 는 경계가 군데군데
  끊겨 그대로 채우면 내부가 배경으로 샌다. CLOSE(팽창→침식)로 틈을 메워 뒤의 채움이 가능해진다.
  OPEN(잡티 제거)은 얇은 edge 자체를 지워버려 쓰지 않는다.
- **Fill_edge** — 닫힌 외곽 윤곽(`RETR_EXTERNAL`) 내부를 solid 로 채워 객체 raw mask 를 만든다.
  `min_area` 미만 윤곽은 잡음으로 버린다(면적 필터 본판은 뒤의 `split_objects`). `border_gap` 은
  **이미지 경계에 걸쳐 잘린 객체**를 닫는다 — 경계에 닿은 edge 끝점이 그 폭 이하로 떨어져 있으면
  경계 변을 따라 이어 윤곽을 닫는다. 객체 사이 큰 배경 간격(>`border_gap`)은 잇지 않아 전체 프레임이
  채워지지 않는다.
- **Edge_blob** — `Fill_edge` 와 같은 채움이되 결과를 객체 mask 가 아니라 **제외용 blob** 으로 보고
  별도 port(`blob`)로 낸다. `min_area`/`max_area` 로 뺄 크기 범위를 골라(예: 큰 덩어리만) `combine_mask`
  (subtract, `slots: {blob: other}`)로 mask 에서 떼어낸다. 같은 채움을 다른 역할로 쓰는 자리라, `slots: {mask: blob}` 재배선으로
  `Fill_edge` 를 그대로 재사용해도 된다(README 상위: slot 재배선).

## 구멍·슬릿 되뚫기 (`edge.py`)

- **Remove_edge_holes** — SAM 등이 **메운 `mask`** 에서 edge 로 갇힌 **구멍·슬릿을 다시 뚫는다**
  (경계-재건). 프레임 `edge` 를 mask 내부(`boundary_margin` 침식 안쪽)로 국한해 장벽으로 삼아
  mask 를 절단하고, mask 경계 띠에 닿는 연결성분만 부품 몸통으로 본다 — edge loop 에 갇혀 경계에서
  **못 닿는 성분이 구멍·슬릿**이다. `combine_mask`/`edge_blob` 의 contour 채움과 달리 **절단+연결성**
  이라 (1) 얇은 슬릿에 강하고 (2) 부품 표면·반사광 edge 는 영역을 가두지 못해 몸통에 흡수돼
  **가짜 구멍이 안 생긴다**. 완전히 갇힌 작은 반사광 blob 만 `min_area` 로 걸러 되메운다.
  다객체 프레임도 한 번에 처리(각 몸통이 경계 띠에 닿음) — `unit: frame`, ROI·색공간 불필요.
  - **boundary_margin** — 외곽 실루엣 edge 제외용 침식 폭(바깥 띠는 재건 seed). 너무 크면 얇은
    부품을 통째 seed 로 봐 구멍을 못 뚫는다.
  - **close_size** — 내부 edge 틈을 CLOSE 로 이어 장벽화(슬릿 끝 닫힘). 틈이 남으면 새어들어 못 뚫음.
  - **min_area** — 이보다 작은 갇힌 영역은 반사광 잡음으로 되메움(0=끄기).
