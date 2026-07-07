# mask — 마스크

이진 mask 를 만들고(이진화) 다듬고(정리) 인스턴스로 쪼갠다(분리). 색공간·출처와 무관한 일반 연산.

## 이진화 (`threshold.py`)

- **Threshold_score** — 스코어/거리 맵 `dist`(예: `chroma_distance`)를 임계로 이진화. `k`(strong)를
  넘는 픽셀이 전경. 적용 순서는 **strong 임계 → 면적 필터(min/max_area) → weak 임계(hysteresis) 확장**.
  `k_weak` 로 hysteresis(강·약 이중 임계)를 켠다. `invert=True` 면 스코어 작은 픽셀을 전경으로
  (배경 추출, hysteresis 방향도 반전). ctx `roi` 가 있으면 그 외접 박스 밖은 버린다.

## 정리 (`cleanup.py`)

- **Normalize_mask** — mask 를 정사각으로 crop 후 `target_shape` 로 pad (분류기 입력 규격화).
- **Morph_mask** — morphology. 기본 **CLOSE→OPEN**(작은 구멍을 먼저 메운 뒤 가는 잡티를 털어냄),
  `reverse` 면 OPEN→CLOSE(잡티 먼저 → 구멍 메움).
- **Combine_mask** — `mask` 와 `other` 두 이진 영역을 `mode` 로 합친다 — `subtract`(`mask & ~other`,
  예: 컨베이어 ROI 에서 SAM3 segment 를 빼 belt 만 남김) / `intersect`(`mask & other`) /
  `union`(`mask | other`). `other` 없으면 무연산 통과, 결과가 비면 스킵.
  - **max_change** (`[-1,1]`, 0=무제한) — 면적 변화율 `(new-old)/old` 한계. 축소(subtract/intersect)는
    **음수** 한계로 과도한 삭제, `union` 은 **양수** 한계로 과도한 확대를 막는다(부호가 mode 와 짝지어짐).
    한계 초과 시 `drop_on_over`: True 면 프레임 스킵, False 면 연산 취소하고 원본 `mask` 통과.

## 분리 (`separate.py`)

- **Split_objects** — 이진 mask 를 `connectedComponents` 한 패스로 **인스턴스 segment 맵 +
  객체(컨테이너 `Data_Ref`) 리스트**로 쪼갠다. `segment` 는 stem 한 장의 (H,W) 라벨맵(**픽셀값 = obj_id+1, 0=배경**,
  `segmap` 핸들러 저장)이라 객체별 mask 를 따로 저장하지 않는다. `min_area` 미만 조각은 버린다.
  - **merge_gap** — 두 컴포넌트 bbox **중심점 거리**가 이 값 이하면 union-find 로 한 객체로 묶는다
    (segment 조각 형태는 그대로 두고 같은 obj_id, bbox 는 합집합). 끊긴 조각을 한 인스턴스로.
  - **bbox_gap** — 객체 bbox 를 비율로 확대/축소(이미지 범위 클램프).
  - `class_id` 는 프레임 ctx `class_id`(컨버터가 label 에서 읽음) 기본, 없으면 `__unclassified__`.
  - 출력 `object` 는 flow 가 frame `info` 의 객체(stem) entry 를 리스트로 교체(obj_id=리스트 순번, leaf 는
    보존), `segment` 는 config outputs(`{to: storage, level: frame, type: segmap}`)로 `frame.info` 에 저장.
- **Order_objects** (`order.py`) — 객체를 **이미지 중심에서 가까운 순**으로 정렬해 `obj_id` 를
  0부터 재부여한다. 각 객체 bbox 중심과 이미지 중심(`segment` 크기 기준) 거리 오름차순이라
  가장 가까운 객체가 `obj_id="0"`. `segment` 라벨맵(픽셀=obj_id+1)도 새 순서로 재라벨(형태는
  그대로, 값만 갱신). bbox 없는 객체는 맨 뒤. `class_id`·bbox 등 나머지 데이터는 유지.
  `Split_objects` 뒤에 붙여 인스턴스 번호를 안정적인 공간 순서로 정돈할 때 쓴다.
