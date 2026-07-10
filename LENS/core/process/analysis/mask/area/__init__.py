"""mask.area — (h, w) Cartesian 좌표계가 적절한 영역/크기 특징.

centroid(다른 모듈의 원점 기준), area, (예정) bbox/convex/solidity 등 '크기·채움' 계열. (r, θ)로
바꿀 이점이 없는, 픽셀 격자 그대로가 자연스러운 특징을 여기 둔다.
"""

from .props import centroid, area

__all__ = ["centroid", "area"]
