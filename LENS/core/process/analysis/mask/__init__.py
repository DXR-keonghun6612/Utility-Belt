"""mask — 객체 mask 한 장에 대한 분석 (데이터 타입: 이진 mask).

분석을 **편한 좌표계 기준**으로 하위 분할한다:

  - ``mask.area``  — (h, w) Cartesian 이 적절한 영역/크기 특징 (area, bbox, solidity 등)
  - ``mask.shape`` — (r, θ) centroid-극좌표가 편한 형상 특징 (radial profile, Fourier descriptor)

만능 구조를 미리 두지 않고 좌표계·데이터 성격에 따라 쪼갠다 — 사례가 충분히 쌓이면 공통 구조를
사후에 추출한다.
"""
