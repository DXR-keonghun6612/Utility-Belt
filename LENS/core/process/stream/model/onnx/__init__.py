"""onnx 파일 기반 backend — **기능별 클래스 + 교체되는 건 onnx 파일 하나**.

torch 기반([`../torch`](../torch/__init__.py))과 갈리는 지점은 무엇을 들여오느냐다. 저쪽은 **모델 코드**
(``import sam3``)에 기대 그 코드가 아는 만큼만 할 수 있고, 이쪽은 **파일**만 들여온다 — 그래서 파일이
자기 입출력을 스스로 설명하면(``onnx`` 그래프 + ``*_rt_cfg.yaml``) 코드를 안 고치고 갈아끼울 수 있다.

```text
_spec.py      Model_spec · Tensor_spec — onnx 그래프(진실) + cfg(대조·layout) 파싱
_runner.py    Onnx_runner  — 세션·Infer. 기능 무관 공용 base (전/후처리 없음)
segment.py    Onnx_segmenter — 기능: 전경 분할. 이 기능의 전/후처리를 든다
weights/      onnx + cfg 쌍 (onnx 는 gitignore — 89MB 짜리가 코드와 섞이지 않게)
```

**기능이 늘면 파일로 낸다** (분류·키포인트 …). 같은 기능의 **모델**이 바뀌는 건 파일 교체라 코드가 안
늘어난다 — ``weights/`` 에 onnx+cfg 를 떨구고 config 의 ``onnx_file:`` 한 줄을 바꾼다.

**GPU 전용이다** — CUDA provider 가 없으면 CPU 로 떨어지지 않고 터진다(성능이 소리 없이 죽는 것보다
부재를 드러내는 게 낫다).
"""

from ._runner import Onnx_runner
from ._spec import Model_spec, Tensor_spec
from .segment import Onnx_segmenter

__all__ = ["Model_spec", "Onnx_runner", "Onnx_segmenter", "Tensor_spec"]
