# stream — 배선

`Stage` 체인을 흐르는 연산 유닛(`Base_Process`)이 사는 층. 프레임·객체 단위로 ctx 를 받아 ctx 를 낸다.
엔진은 [`../README.md`](../README.md), 계산은 [`../../func/README.md`](../../func/README.md).

---

## 유닛은 계산하지 않는다

> `stream/` 은 저장 표현을 알고 **계산을 모른다.** `func/` 는 그 반대다.

유닛이 하는 일은 넷뿐이다.

1. **config 를 든다** — `@dataclass` 필드(+ GUI 표시 힌트 `UI`).
2. **ctx 에서 값을 꺼낸다** — `Run` 시그니처가 곧 입력 선언(`INPUTS` 자동추출).
3. **`func` 를 부른다.**
4. **결과를 판정하고 조립한다** — 빈 결과면 `{}`(스킵), 객체 리스트면 `Data_Ref` 컨테이너로 싼다.

`Data_Ref` 를 아는 것은 이 층의 **권한이자 책임**이다. 계산을 `func` 에 넘기고 저장 표현을 여기서만
입히므로, 같은 계산이 GUI·분석·테스트에서 store 없이 재사용된다.

유닛 몸통에 `cv2.`/`np.` 연산이 쌓이기 시작하면 그건 `func` 로 내려갈 것이 유닛에 갇힌 것이다.
`self` 를 안 쓰는 private 메서드는 특히 그렇다 — 그런 헬퍼는 이미 자유함수다.

## 도메인 = 출력의 도메인

프로세스는 **입력이 아니라 출력의 도메인**에 속한다. edge 를 읽어 mask 를 내는 유닛은 mask 유닛이다
(입력은 어느 도메인에서 와도 된다 — 그게 데이터흐름이다). 그래서 `Fill_edge`·`Remove_edge_holes` 는
`filter/` 가 아니라 `mask/from_edge.py` 에 산다.

> `stream/<domain>` 은 `func/<domain>` 과 제네릭 `func/cv` 만 import 한다. **다른 도메인의 func 금지.**

이 선을 넘으면 폴더는 도메인이 아니라 "예전에 누가 여기 뒀던 것"이 된다.

```text
stream/
├── preprocess/  프레임 다듬기 — crop · color
├── filter/      edge 를 만든다 — canny(탐색) · edge(닫기)
├── mask/        이진 영역·인스턴스 — threshold · cleanup · reflect · separate · order ·
│                from_edge · flood · carve · radial
├── chroma/      크로마 배경모델 — convert_to · accumulate · robust_stats(finalize) · distance
├── model/       무거운 모델에 기대는 유닛 — detect·segment(정책) + onnx·torch(backend)
└── select/      측정·게이트 — center(측정) · gate(선택)
```

파일 = 갈래. 늘어나는 축은 파일로 분리한다(탐색법이 늘면 `filter/sobel.py`). 새 유닛은 **출력 도메인**
폴더에 더하고 `@PROCESS_REGISTRY.Register_module()` 로 등록한다 — 등록명은 클래스 데코레이터가 잡으므로
모듈을 옮겨도 config 의 `object_type` 은 바뀌지 않는다.

## 관례

- **빈 dict = 이 unit 스킵.** 엔진이 체인을 끊고 `emit` 도 건너뛴다. `select/gate.py` 가 이 관례 하나로
  Run·Sample 어디서든 게이트가 되는 이유다(엔진이 공유되므로).
- **무거운 모델은 소유하지 않는다.** pipeline 이 스펙당 1회 빌드해 주입하고 유닛은 핸들만 든다.
- **측정은 Run(정본), 선택은 Sample(파생).** task 가 바뀌어도 쓰는 값(기하 측정)은 정본에 남기고,
  task 특화 선별은 파생에서 솎아낸다 — 정본은 손실 없이.

## 유닛은 store 를 모른다

객체 목록이 필요하면 ctx 의 **`object`** 를 읽는다 — 엔진이 store 에서 seed 하고 `split_objects` 가 같은
키로 덮어쓰므로, **입력과 출력이 같은 이름으로 대칭**이다. (예전엔 `meta.Find(stem)` 으로 store 를 직접
뒤졌는데, 그건 유닛의 일탈이 아니라 엔진이 ctx 에 store 핸들을 넣어줬기 때문이었다. 안 넣으니 사라졌다.)

## 아직 지켜지지 않는 것

- `model/torch/_sam3.py` 는 상태를 든 **런타임**이라 유닛도 자유함수도 아니다. 이 층에 있을 것이 아니다
  ([`../TODO.md`](../TODO.md)). `model/onnx/` 도 같다.
