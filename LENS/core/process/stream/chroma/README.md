# chroma — 색공간

2채널 크로마 배경모델 파이프라인. 명도(HSV의 V, Lab의 L)는 조명에 취약해 버리고 색 2채널만 써서
배경(컨베이어 belt)을 모델링하고, 프레임의 배경 대비 편차로 객체를 찾는다. 색공간 의존값
(채널·bins·순환 여부·cvt code)은 전부 `_space.ChromaSpace` 가 들고, 각 process 는 `space` 이름만 받는다.

파이프라인:

```
convert_to_chroma → accumulate_chroma_histogram ─(carry)─→ [finalize] robust_chroma_stats ─(params)─→ chroma_distance → (mask/threshold …)
```

## 변환 (`convert_to.py`)

- **Convert_to_Chroma** — 프레임을 `space` 로 옮겨 2채널 크로마 `(H,W,2)` 를 뽑는다
  (hsv=H·S / lab=a*·b*). 명도 채널은 버린다.

## 누산 (`accumulate.py`)

- **Accumulate_Chroma_histogram** — 크로마 값을 히스토그램에 더하는 순수 reducer. 누산기를 입력
  (`c0_acc`/`c1_acc`)으로 받아 갱신본을 출력 → flow 가 `carry` 로 프레임 간 이월하면 무상태로
  cross-frame 누산이 된다(첫 프레임은 `None` → 모양 맞춰 생성). `roi` 픽셀만 누산 가능.
  - **per_pixel** — `False`: 전 픽셀을 1-D 히스토그램 `(B,)` 로 합산(전역 배경색). `True`: 픽셀별
    `(H,W,B)`(위치별 배경, 정적 카메라).

## 통계 (`robust_stats.py`) — finalize

- **Robust_Chroma_Stats** — 누산 히스토그램에서 **median + IQR** robust 통계로 배경 평균/표준편차
  4키(`mean_c0/1`, `std_c0/1`)를 낸다. finalize 체인 끝단이라 순회 후 1회 돌며 params 로 나간다.
  1-D면 스칼라 4개, `(H,W,B)`면 `(H,W)` 배열 4개.

  **왜 median+IQR** — 배경(belt)이 분포의 다수라 **가중 중앙값**을 배경값, **IQR/1.349**(가우시안 σ와
  일치)를 robust σ로 쓴다. 분위수 기반이라 객체(소수 꼬리)는 median·IQR 둘 다 거의 못 흔들어 **50%
  미만 오염에 면역**. 순환 채널(hue)은 mode 를 중심으로 `±B/2` 좌표로 재배열(gather)해 비순환처럼 처리.
  - *이전 mode-window 방식의 실패*: mode 에서 `window` bin 밖 표본을 통째로 버려 배경 퍼짐을 8~12배
    **과소추정** → 작은 σ가 정규화 거리를 폭주시켜 **모든 픽셀이 전경**이 됐다. 분위수 척도는 belt 의
    실제 spread 를 보존하면서 객체 꼬리는 무시한다.

## 거리 (`distance.py`)

- **Chroma_distance** — 배경 모델(params 4키) 대비 정규화 편차 맵 `dist = √((Δc0/σ0)²+(Δc1/σ1)²)`.
  모델이 스칼라(전역)든 `(H,W)`(픽셀별)든 numpy 브로드캐스팅으로 한 process 가 공용 처리한다. 순환
  채널 wrap 은 `Channel_delta`(`_core.py`)가 보정, `sigma_floor` 로 작은 σ 잡음을 억제. 출력 `dist`
  는 보통 outputs 미선언으로 ctx 로만 흘러 `threshold_score` 가 받는다.

## 전역 vs 픽셀별 — 한 줄로

별도 클래스가 아니라 `accumulate_chroma_histogram.per_pixel` 한 줄로 갈린다(구조 동일). 주의:
픽셀별 모델은 한 픽셀을 객체가 절반 이상 점유하면 그 픽셀 통계가 오염될 수 있다(**positional bias**).
객체 위치 경향이 있는 데이터는 belt 이 전역 다수인 전역 모델(`per_pixel=false`)이 구조적으로 강하다.

## 내부

- `_space.py` — `ChromaSpace`(채널·bins·circular·cvt_code), `Get_space`/`DEFAULT_SPACE`.
- `_core.py` — `Channel_delta`(순환 채널 wrap 보정 차분).
