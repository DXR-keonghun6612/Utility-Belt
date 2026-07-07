# preprocess — 전처리

flow 앞단에서 프레임을 다듬는 process 들.

## 크롭 (`crop.py`)

- **Frame_crop** — `mask` 가 덮는 영역의 외접 박스로 `frame` 을 잘라 `crop` 을 낸다. mask 가 비면
  빈 dict("스킵").

## 색보정 (`color.py`)

- **Normalize_color** — 조명 정규화. BGR→HSV 로 옮겨 V(명도)를 상수(`value`)로 덮어 밝기 변화를
  지우고 BGR 로 되돌린다. 색상(H)·채도(S)는 보존되므로 그림자/하이라이트로 생기는 밝기 경계는
  사라지고 **색 경계만** 남는다 — 뒤따르는 `detect_edge` 의 입력(`norm_image`)이 된다.
