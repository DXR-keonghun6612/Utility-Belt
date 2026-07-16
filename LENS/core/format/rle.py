"""rle 구조 — run-length 로 압축된 픽셀 집합.

``{"counts": str, "size": [H, W]}`` — pycocotools 인코딩이라 detectron2·mmdet 등이 그대로 먹고,
COCO ``segmentation`` 으로도 그대로 나간다. ``counts`` 는 JSON 직렬화 가능한 str 로 든다.

**폴리곤과 달리 이 구조는 뜻이 하나다** — run-length 는 픽셀을 세는 것이라 면일 수밖에 없고, 선으로
읽을 여지가 없다. 그래서 [`polygon`](polygon.py) 이 `Fill`/`Stroke` 로 갈릴 자리를 남기는 것과 달리
여기는 `To_mask` 하나다. **구조마다 뜻의 여지가 다르다는 것 자체가 도메인이 따로 있는 이유다** —
여지가 없는 구조도 그 사실을 도메인이 알아야지, 구조가 스스로 정하지 않는다.

`To_mask` 는 **무손실**이다(폴리곤의 `Fill` 과 다르다) — rle 는 픽셀을 그대로 세므로 왕복해도 안 변한다.
"""

from __future__ import annotations

import numpy as np
from pycocotools import mask as coco_mask


def To_mask(rle: dict) -> np.ndarray:
    """rle → 이진 mask ``(H, W) uint8``. 무손실."""
    _rle_b = {"counts": rle["counts"].encode("utf-8"), "size": rle["size"]}
    return coco_mask.decode(_rle_b).astype(np.uint8)  # type: ignore[arg-type]


def From_mask(mask: np.ndarray) -> dict:
    """이진 mask → rle (`To_mask` 의 역). ``counts`` 는 JSON 직렬화 가능한 str."""
    _rle = coco_mask.encode(np.asfortranarray(np.asarray(mask).astype(np.uint8)))
    return {  # type: ignore[union-attr]
        "counts": _rle["counts"].decode("utf-8"),
        "size":   _rle["size"],
    }


def Size(rle: dict) -> tuple[int, int]:
    """이 rle 가 사는 캔버스 크기 ``(H, W)``."""
    return (int(rle["size"][0]), int(rle["size"][1]))
