"""detect — 프롬프트 없는 ONNX 전경-분할 정책 프로세스.

``_base.py`` 의 ``Detect_instances`` 가 등록된다. backend([`Onnx_segmenter`](../onnx/segment.py))는
config 로 주입 — SAM3(box 프롬프트)와 계약이 달라 별도 정책이다(``Infer_logits``/``Origin``).
"""

from ._base import Detect_instances

__all__ = ["Detect_instances"]
