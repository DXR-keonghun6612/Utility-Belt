# chroma — 배경모델

각 유닛의 인자·동작은 그 유닛의 docstring 에 있다. 이 문서는 **유닛 사이에 걸치는 것** — 왜 이 파이프라인
이고, 왜 이 통계인가 — 만 다룬다.

```text
convert_to_chroma → accumulate_chroma_histogram ─(carry)─→ [finalize] robust_chroma_stats ─(params)─→ chroma_distance
```

명도(HSV 의 V, Lab 의 L)는 조명에 취약해 **버리고** 색 2채널만으로 배경(컨베이어 belt)을 모델링한 뒤,
프레임의 배경 대비 편차로 객체를 찾는다. 색공간 의존값(채널·bins·순환 여부·cvt code)은 전부
`func/chroma/_space.ChromaSpace` 가 들고, 각 유닛은 `space` **이름만** 받는다.

누산이 `carry` → `finalize` 로 갈리는 이유는 엔진 규칙 그대로다 — 누산기가 순회와 함께 죽으므로 그걸
통계로 바꾸는 변환은 같은 호출 안에서 일어나야 한다([`../../README.md`](../../README.md)).

---

## 왜 median + IQR 인가

배경(belt)이 분포의 **다수**라, **가중 중앙값**을 배경값으로 쓰고 **IQR/1.349**(가우시안 σ와 일치)를
robust σ로 쓴다. 분위수 기반이라 객체(소수 꼬리)는 median·IQR 둘 다 거의 못 흔든다 — **50% 미만 오염에
면역**이다. 순환 채널(hue)은 mode 를 중심으로 `±B/2` 좌표로 재배열해 비순환처럼 처리한다.

> **이전 mode-window 방식의 실패 (다시 만들지 말 것)** — mode 에서 `window` bin 밖 표본을 통째로 버려
> 배경 퍼짐을 **8~12배 과소추정**했다. 작은 σ가 정규화 거리를 폭주시켜 **모든 픽셀이 전경**이 됐다.
> 분위수 척도는 belt 의 실제 spread 를 보존하면서 객체 꼬리는 무시한다.

## 전역 vs 픽셀별 — 한 줄로 갈린다

별도 클래스가 아니라 `accumulate_chroma_histogram.per_pixel` 한 줄이다(구조는 동일). 다만 픽셀별 모델은
한 픽셀을 객체가 절반 이상 점유하면 그 픽셀 통계가 오염된다(**positional bias**) — 객체 위치에 경향이 있는
데이터라면 belt 이 전역 다수인 **전역 모델이 구조적으로 강하다**.
