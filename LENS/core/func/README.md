# func — 계산

연산의 **계산**이 사는 층. 자유함수뿐이고 클래스도 상태도 없다.
각 함수의 인자·반환·근거는 그 함수의 docstring에 있다. 이 문서는 **경계**만 말한다.

---

## 경계는 "무엇을 아는가"로 긋는다

무슨 일을 하느냐가 아니라 **무슨 타입을 아느냐**가 이 층을 정의한다.

> `func/` 는 도메인 자료형만 안다 — 배열, 박스, id, 스칼라, 색공간 spec.
> **`Data_Ref`·`Dataset_Meta`·`handler` 를 모른다.**

이게 지켜지면 모든 계산은 store 없이, 파이프라인 없이, 단독으로 호출·검증된다. 어기는 순간 그 계산은
저장 표현에 묶여 재사용도 테스트도 불가능해진다 — **객체가 개념 앞에 서는 것**이다.

반대 방향의 경계는 [`../stream/README.md`](../stream/README.md)가 갖는다: stream 은 저장 표현을 알고
계산을 모른다. 해체와 조립이 stream 의 유일한 일감이다.

## 도메인 경계

```text
func/
├── cv/       제네릭 — 도메인 의미가 없는 raster·좌표 연산
│   ├── filter.py   Canny·LoG·morphology·hysteresis·윤곽 채움·면적 필터·저주파 밝은영역
│   ├── geom.py     roi/bbox ↔ 영역 좌표 변환 · 중심 · crop/pad
│   └── color.py    색공간을 오가는 채널 조작 (명도 평탄화·강도 스케일)
├── chroma/   크로마 배경모델 — 2채널 변환 · 누산 · robust 통계 · 거리
│   ├── _space.py   ChromaSpace (채널·bins·순환 여부·cvt code)
│   └── _core.py    To_chroma · Accumulate_histogram · Distance_map · Robust_mean_std
└── mask/     이진 영역·인스턴스 의미가 붙은 연산
    ├── instance.py  연결요소 분할 · 중심 정렬 · bbox 클러스터
    ├── combine.py   집합 연산 · 면적 변화
    ├── enclosure.py edge 장벽으로 갇힌 영역 도려내기
    ├── flood.py     배경 flood → 반전
    ├── fill.py      국소 배경색 · 색 구멍 · 라벨별 carve
    └── polar.py     (r,θ) 변환 · hollowness
```

**`cv/` 는 도메인이 아니라 "도메인 없음"이다.** 여기 있는 함수는 어느 도메인 유닛이 써도 누수가 아니다.
반대로 `mask/`·`chroma/` 는 그 도메인의 의미(전경·구멍·배경색)를 전제한다. 새 함수를 놓을 때 묻는다 —
**이 함수가 "mask" 라는 말을 몰라도 성립하는가.** 그러면 `cv/` 다.

`cv/filter.py` 의 `Filter_by_area`·`Fill_contours` 처럼 이름에 mask 가 없어도 mask 를 다루는 것들이 있다.
그것들은 "이진 배열의 연결성분"이라는 raster 사실만 알지 전경/구멍 같은 **의미**를 모르므로 제네릭이다.

## 규약

- **호출 측이 판단한다.** 계산은 결과가 비면 `None` 을 돌려줄 뿐, "스킵할지"는 정하지 않는다.
  그 정책은 stream 유닛의 몫이다(빈 dict 관례).
- **누산기는 인자로 받고 갱신본을 돌려준다.** 상태를 들지 않으므로 cross-frame 누산은 호출 측의
  `carry` 가 만든다 (`Accumulate_histogram`).
- **비싼 값은 인자로 받는다.** 프레임당 1회면 충분한 것(예: LoG 벽)을 루프 안에서 다시 구하지 않는다
  (`Carve_holes_by_label(..., walls=...)`).
- `_space.py`·`_core.py` 의 밑줄은 **모듈이 사설이라는 뜻이 아니다** — 지금은 소비자가 깊게 직접 import
  한다. 공개 facade 재설계는 [`../TODO.md`](../TODO.md).
