"""torch 기반 backend — **모델 코드**에 기대는 런타임.

onnx 기반([`../onnx`](../onnx/__init__.py))과 갈리는 지점은 무엇을 들여오느냐다. 이쪽은 파일이 아니라
**코드**(``import sam3``)를 들여온다 — 가중치만 바꿔 끼울 수 없고, 그 라이브러리가 아는 만큼만 할 수
있다. 대신 파일 하나로 표현 못 하는 것(상태를 든 인코딩·프롬프트 디코드 루프)을 할 수 있다.

```text
_sam3.py    Sam3_runner — promptable segmenter (encode/run 프리미티브)
```
"""

from ._sam3 import Sam3_runner

__all__ = ["Sam3_runner"]
