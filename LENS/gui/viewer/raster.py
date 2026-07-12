"""raster 뷰어 — 캔버스에 겹쳐 그릴 수 있는 것들 (``image`` · ``segmap`` · ``rle``).

**체크박스가 표시 여부다** — 노드 트리에서 체크한 raster 들을 위에서부터 합성한다. 그래서 "base 이미지"
라는 특별한 개념이 없다: BGR 로 디코드되는 leaf 는 배경이 되고, mask/라벨맵은 색을 입혀 겹친다.

편집기는 여기 없다 — 앱에 하나뿐인 `Mask_editor` 가 이 노드들을 **조준**한다(계약은 `_base`).
"""
from __future__ import annotations

from typing import Any

import cv2
import numpy as np
from PySide6.QtWidgets import QLabel, QWidget

from core.schema import Data_Ref

from ._base import Node_viewer, Register


@Register("image")
class Image_viewer(Node_viewer):
    """색 이미지 — 캔버스의 **배경**이 된다 (BGR 그대로).

    **단채널(mask)로 들어온 것만 조준할 수 있다** — `roi` 같은 dataset-wide mask 를 손보는 자리다.
    3채널 색 이미지를 브러시로 칠하는 건 라벨링이 아니라 그림 그리기라 열지 않는다(원본 픽셀은 정본이고,
    손대면 되돌릴 수 없다). 그 판별은 값의 모양이 하므로 `Data_view` 가 ndim 을 보고 거른다.
    """

    RASTER   = True
    EDITABLE = True

    @classmethod
    def layer(cls, value: Any, ref: Data_Ref) -> np.ndarray | None:
        if not isinstance(value, np.ndarray) or value.ndim < 2:
            return None
        return value if value.ndim == 3 else cv2.cvtColor(value, cv2.COLOR_GRAY2BGR)

    @classmethod
    def summary(cls, value: Any, ref: Data_Ref) -> str:
        if not isinstance(value, np.ndarray):
            return "image (로드 실패)"
        _h, _w = value.shape[:2]
        return f"image {_w}×{_h}"

    @classmethod
    def panel(cls, value: Any, ref: Data_Ref, *, ctx=None, on_change=None) -> QWidget | None:
        return QLabel(cls.summary(value, ref))


@Register("segmap")
class Segmap_viewer(Node_viewer):
    """인스턴스 라벨맵 (픽셀 = obj_id + 1) — 라벨마다 색을 달리해 겹친다.

    **직접 조준하지 않는다**(``EDITABLE`` 이 아니다). 이 라벨맵을 칠한다는 건 언제나 "어떤 객체의
    mask 를 칠한다"는 뜻이라, 편집기는 **객체를 겨누고** 그 결과가 여기 라벨로 찍힌다. 라벨맵 자체를
    겨누면 "몇 번 라벨로 칠할지"를 손으로 골라야 하고 — 그건 객체를 UI 가 모른다는 뜻이다.
    """

    RASTER   = True

    @classmethod
    def layer(cls, value: Any, ref: Data_Ref) -> np.ndarray | None:
        """라벨맵을 **라벨 그대로** 돌려준다 — 색칠은 캔버스가 한다(객체 색과 맞춰야 하므로)."""
        if not isinstance(value, np.ndarray) or value.ndim != 2:
            return None
        return value

    @classmethod
    def summary(cls, value: Any, ref: Data_Ref) -> str:
        if not isinstance(value, np.ndarray):
            return "segmap (로드 실패)"
        _n = int(value.max())
        return f"segmap · 인스턴스 {_n}개"

    @classmethod
    def panel(cls, value: Any, ref: Data_Ref, *, ctx=None, on_change=None) -> QWidget | None:
        return QLabel(cls.summary(value, ref))


@Register("rle")
class Rle_viewer(Node_viewer):
    """coco RLE mask — 디코드된 이진 mask 를 겹친다 (인라인이라 파일이 없다)."""

    RASTER = True

    @classmethod
    def layer(cls, value: Any, ref: Data_Ref) -> np.ndarray | None:
        if not isinstance(value, np.ndarray) or value.ndim != 2:
            return None
        return (value > 0).astype(np.uint8)

    @classmethod
    def summary(cls, value: Any, ref: Data_Ref) -> str:
        if not isinstance(value, np.ndarray):
            return "rle"
        return f"rle · {int((value > 0).sum())}px"
