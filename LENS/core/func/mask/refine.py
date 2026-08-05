"""기존 mask 를 이미지 신호로 **색 기반**으로 다듬는 primitive — 넓힘과 좁힘의 두 방향.

둘 다 **GUI 의 magic-wand 를 mask 가 정한 자리에서 누르는 것**이고, 각각 **한 방향만** 한다:

| 함수 | 방향 | seed 자리 | 번짐 기준 |
|---|---|---|---|
| `Refine_by_color` | 넓힘 | mask 안쪽(경계에서 ``seed_margin`` px), 평균색 **이내** | 그 seed 색 ±tolerance |
| `Cut_by_color`    | 좁힘 | mask 안, 평균색 **밖** & 반사광 아님 | 그 seed 색 ±tolerance |

**한 함수가 양방향을 하지 않는다.** 넓힘과 좁힘을 한 덩어리로 두면 결과가 줄었을 때 "덜 번진 것"인지
"깎인 것"인지 구분이 안 되고, 손잡이 하나가 두 일을 해서 어느 쪽을 움직였는지도 못 가린다. 나눠 두면
각 블록의 결과가 입력의 상위집합이거나 부분집합 중 하나로 고정돼 config 에서 순서·유무로 조합된다.

**색과 벽은 다른 축이고, 이 함수는 색만 안다.** floodFill 의 ``tolerance`` 는 "seed 색에서 얼마나
멀어졌나"(값의 크기)를 보고, 벽은 "색이 공간적으로 얼마나 급하게 꺾이나"(변화량)를 본다 — 저대비
경계는 색만으로 못 막고 변화량 edge 라야 막힌다. 그래서 벽은 밖에서 ``wall`` 로 받고(LoG·Canny 등
방법론은 producer 소유), 이 함수는 색 기준만 안쪽에서 소유한다. 벽이 없으면 색만으로 번진다.

**반사광(과포화 하이라이트)은 어느 방향도 손대지 않는다.** 넓힘은 기준색 표본에서 빼 seed 로 안 삼고,
좁힘은 후보에서 빼고 벽으로 보호한다 — raw mask 에 든 반사광은 그대로 통과시킨다.

**벨트(배경)를 보지 않는다.** 정제가 필요한 자리는 작은 구멍·붙은 경계인데 거기엔 배경이 아예 안
보이므로, 배경 색을 표본으로 삼는 방식은 쓸 수 없다. 있는 신호는 mask 자신의 색과 edge 뿐이고 이
둘만 쓴다.
"""

from __future__ import annotations

import cv2
import numpy as np

from ...typing import GRAY_IMAGE
from ..cv.filter import Filter_by_area, Make_morph_kernel


def _crop_slices(sel: np.ndarray, pad: int) -> tuple[slice, slice]:
    """``sel`` True 영역의 외접 박스를 ``pad`` 만큼 넓힌 crop 슬라이스. **비어 있지 않은 sel 전제.**"""
    _rows = np.flatnonzero(sel.any(axis=1))
    _cols = np.flatnonzero(sel.any(axis=0))
    _h, _w = sel.shape
    return (slice(max(0, int(_rows[0]) - pad), min(_h, int(_rows[-1]) + 1 + pad)),
            slice(max(0, int(_cols[0]) - pad), min(_w, int(_cols[-1]) + 1 + pad)))


def Refine_by_color(
    image: np.ndarray, anchor: np.ndarray, region: np.ndarray | None = None, *,
    wall: np.ndarray | None = None,
    tolerance: int = 12, seed_tolerance: int = 20, bright_margin: int = 40,
    seed_margin: int = 3, fill_radius: int = 0, grow: int = 2, close_size: int = 0,
    min_area: int = 0,
) -> GRAY_IMAGE | None:
    """``anchor`` mask 의 **픽셀마다 magic-wand 를 눌러** 덮이지 않은 이웃까지 넓힌다 — 확장 전용.

    GUI 채우기(``gui.editor.image.tool._fill.magic_wand``)를 사람이 mask 안 여기저기 클릭하는 것과
    같다. 다른 점은 클릭 위치를 사람이 아니라 mask 가 정한다는 것뿐이다:

    - **어디를 누르나** — ``anchor`` 를 ``seed_margin`` 만큼 침식한 안쪽(경계에서 ``seed_margin`` px
      들어간 자리부터). 경계 픽셀은 배경과 섞인 중간색이라 seed 로 쓰면 그 섞인 색을 기준으로 번진다.
    - **어디는 안 누르나** — 그 자리 색이 mask 평균색에서 ``seed_tolerance`` 를 넘게 벗어나면 건너뛴다.
      과칠·그림자처럼 mask 안이지만 객체 색이 아닌 자리가 자기 색으로 번지는 것을 막는 유일한 장치다.
    - **한 번 누르면** — 그 seed 색 ±``tolerance`` 인 인접 픽셀로 번지되 LoG(+``wall``) 벽과 ``region``
      경계에서 멈춘다. 기준이 **각 seed 자신의 색**이라(평균이 아니라) 얼룩덜룩한 객체도 제 색으로
      번진다 — 평균 하나로 재면 밝은 면과 어두운 면 중 한쪽이 통째로 밴드 밖으로 밀린다.
    - **얼마나 멀리** — ``fill_radius`` 가 있으면 각 seed 의 번짐을 **그 seed 중심 반경 원**으로 가둔다
      (GUI 채우기의 ``radius`` ROI 와 같다). 없으면(``0``) ``region`` 전체가 한 ROI 라, 색만 맞으면
      mask 에서 먼 자리까지 한 번에 번진다. seed 들이 anchor 를 촘촘히 덮으므로 **모든 seed 원의
      합집합 = seed 집합을 ``fill_radius`` 로 팽창한 것**이고, 그걸 벽에 한 번 심어 seed 마다 원을
      그리지 않는다(비용은 seed 수와 무관).

    **결과는 언제나 ``anchor`` 의 상위집합이다.** 이 함수는 아무것도 깎지 않는다 — 벽에 막혀 못 번진
    자리도, 색이 안 맞는 자리도 anchor 에 있던 것은 그대로 남는다. 덜 그려진 것을 채우는 게 목적이라
    잘못 그려진 것을 도려내는 판단은 여기 없다.

    이미 다른 seed 가 덮은 자리에서는 다시 번지지 않는다(누적 mask 가 곧 방문 표시라 전체 비용이
    ``region`` 크기에 비례한다). 그래서 겹치는 seed 들 중 **먼저 닿은 쪽의 색 밴드**가 그 자리를
    가져간다 — seed 는 좌상단부터 raster 순으로 돈다.

    계산은 ``region`` 의 외접 박스(+morphology 여유 pad) 안에서만 돈다 — 결과가 어차피 ``region`` 안이라
    잘려나가는 것이 없다. 벽(``wall``)은 프레임 전체에서 미리 난 것을 이 crop 으로 슬라이스해 쓴다.

    Args:
        image: BGR ``(H,W,3)`` 또는 gray ``(H,W)`` (gray 는 BGR 로 승격).
        anchor: 넓힐 기존 객체 mask ``(H,W)`` — seed 자리이자 결과의 하한.
        region: 확장을 가둘 영역 bool ``(H,W)`` (보통 확대 bbox). None 이면 프레임 전체.
        wall: 번짐을 막을 외부 edge 벽 ``(H,W)`` (변화량 기반 — LoG·Canny 등, producer 가 프레임
            전체에서 생성). None 이면 벽 없이 색만으로 번진다.
        tolerance: **한 seed 의** 번짐 허용 여유(채널값) — 그 seed 색 ±이 값. GUI 도구의 '허용'과 같다.
        seed_tolerance: seed 자격 — mask 평균색에서 이 값 이내인 픽셀만 누른다. 좁힐수록 객체 본색만
            번지고, 넓히면 mask 안 과칠도 자기 색으로 번진다.
        bright_margin: **평균 표본에서** 반사광을 빼는 밝기 여유(gray) — 평균 밝기 + 이 값 이상인
            픽셀은 기준색 평균에서 제외한다(seed 자격의 기준을 본체색으로). 절대값이 아니라 평균
            대비라 프레임 밝기에 적응한다. 반사광 자체는 넓힘 대상이 아니라 그대로 통과한다.
        seed_margin: 경계에서 안쪽으로 들어갈 px — seed 를 여기부터 놓는다. 침식으로 seed 가 사라지는
            얇은 객체는 anchor 전체를 seed 후보로 되돌린다.
        fill_radius: 각 seed 번짐을 가둘 **원 반경 px** (``0``=끔 → ``region`` 전체가 ROI). GUI 채우기의
            반경과 같은 뜻이다 — mask 에서 이 거리 이상 떨어진 자리엔 색이 맞아도 번지지 않아, 국소적으로만
            다듬는다. ``grow`` 되붙임과 독립이다(이건 번짐 **전**의 도달 한계, grow 는 번짐 **후**의 보정).
        grow: 번진 영역을 팽창해 벽 두께만큼 경계에 되붙일 **반경 px** (``2*grow+1`` 원형 커널,
            ``0``=끔). 벽 픽셀은 채워지지 않아 번짐이 벽 띠 안쪽에서 멈추므로 그만큼 되찾는 자리다.
            σ 가 크면 같이 키운다. ``region`` 밖은 자른다.
        close_size: morphology CLOSE 커널(px) — 색 얼룩으로 뚫린 작은 틈을 메운다(``0``=끔).
        min_area: **새로 덮은** 조각 중 이보다 작은 것은 버린다(``0``=끔). anchor 는 대상이 아니다.

    Returns:
        ``(H,W)`` uint8 0/255 (``anchor`` ∪ 확장). anchor 가 비면 None.
    """
    _h, _w = image.shape[:2]
    _img_full = image if image.ndim == 3 else cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    _region_full = np.ones((_h, _w), bool) if region is None else (region > 0)
    _anchor_full = (anchor > 0) & _region_full
    if not _anchor_full.any():
        return None

    # 계산은 region 외접 박스 안에서만 — 결과가 region 안이라 잘리는 것이 없다. pad 는 morphology 가
    # crop 경계를 물지 않게 하는 여유.
    _pad  = max(grow, close_size, fill_radius) + 2
    _sl   = _crop_slices(_region_full, _pad)
    _img, _region, _anchor = _img_full[_sl], _region_full[_sl], _anchor_full[_sl]
    _gray = cv2.cvtColor(_img, cv2.COLOR_BGR2GRAY)

    # 벽 = 외부 edge(변화량) 를 crop 으로 슬라이스한 것. 없으면 벽 없이 색만으로 번진다(edge 방법론은
    # 바깥 producer 가 소유 — 이 함수는 색만 안다).
    _walls = (wall[_sl] > 0) if wall is not None else np.zeros(_img.shape[:2], bool)

    _inner = cv2.erode(_anchor.astype(np.uint8), Make_morph_kernel(2 * seed_margin + 1)) > 0 \
        if seed_margin else _anchor
    if not _inner.any():                                        # 얇은 객체 — 침식으로 seed 소멸
        _inner = _anchor

    # 평균은 **안쪽에서만** — 경계에 삐져나간 과칠(배경색)이 평균을 끌어당기지 않게 한다. 그중에서도
    # 반사광은 빼 본체색만 잡는다(판정은 절대 밝기가 아니라 평균 대비라 프레임 밝기에 적응).
    _mean_gray = float(_gray[_inner].mean())
    _bright = _gray.astype(np.float32) >= _mean_gray + bright_margin
    _body = _inner & ~_bright
    _ref = _img[_body if _body.any() else _inner].reshape(-1, 3).astype(np.float32).mean(axis=0)
    _seeds = _inner & (np.abs(_img.astype(np.float32) - _ref).max(axis=2) <= seed_tolerance)

    # seed 마다 magic-wand — floodFill 의 mask 에 벽(LoG + region 밖)을 미리 심고, 채운 자리는 255 로
    # 남아 다음 seed 를 막는다(누적 mask = 방문 표시). GUI 도구와 같은 FIXED_RANGE(= seed 색 기준).
    _wall_all = _walls | ~_region
    if fill_radius > 0:                                         # seed 에서 이 반경 밖도 벽 (per-seed 원 합집합)
        _reach = cv2.dilate(_seeds.astype(np.uint8),
                            Make_morph_kernel(2 * fill_radius + 1, ellipse=True)) > 0
        _wall_all = _wall_all | ~_reach
    _flood = np.zeros((_img.shape[0] + 2, _img.shape[1] + 2), np.uint8)
    _flood[1:-1, 1:-1] = _wall_all.astype(np.uint8)
    _img_c = np.ascontiguousarray(_img)
    _tol   = (int(tolerance),) * 3
    _flags = 4 | cv2.FLOODFILL_MASK_ONLY | cv2.FLOODFILL_FIXED_RANGE | (255 << 8)
    for _y, _x in np.argwhere(_seeds):
        if _flood[_y + 1, _x + 1]:                              # 벽이거나 이미 다른 seed 가 덮은 자리
            continue
        cv2.floodFill(_img_c, _flood, (int(_x), int(_y)), 0, _tol, _tol, _flags)

    _add = _flood[1:-1, 1:-1] == 255                            # 번진 영역 (벽·region 밖은 못 든다)
    if grow > 0:                                                # 벽 띠만큼 되붙임 (region 안으로)
        _add = (cv2.dilate(_add.astype(np.uint8),
                           Make_morph_kernel(2 * grow + 1, ellipse=True)) > 0) & _region
    if close_size > 0:
        _add = (cv2.morphologyEx(_add.astype(np.uint8), cv2.MORPH_CLOSE,
                                 Make_morph_kernel(close_size)) > 0) & _region
    _add &= ~_anchor                                            # 새로 덮은 부분만
    if min_area > 0:
        _add = Filter_by_area(_add.astype(np.uint8) * np.uint8(255), min_area=min_area) > 0

    _full = np.zeros((_h, _w), np.uint8)                        # crop → 원래 프레임 좌표로
    _full[_sl] = (_anchor | _add).astype(np.uint8) * np.uint8(255)   # anchor 는 언제나 보존
    return _full


def Cut_by_color(
    image: np.ndarray, mask: np.ndarray, *,
    wall: np.ndarray | None = None,
    tolerance: int = 12, cut_tolerance: int = 30, bright_margin: int = 40,
    seed_margin: int = 3, grow: int = 0, close_size: int = 0, min_area: int = 0,
) -> GRAY_IMAGE | None:
    """``mask`` 안에서 **평균색 밖으로 뜨는 자리**에 magic-wand 를 눌러 걷어낸다 — 축소 전용.

    :func:`Refine_by_color` 의 거울상이다. 거기서는 평균색 **이내**인 안쪽 픽셀을 눌러 밖으로 번졌고,
    여기서는 평균색에서 ``cut_tolerance`` 를 넘게 **벗어난** mask 안 픽셀을 눌러 그 자리를 뺀다 —
    경계 밖으로 삐져나간 과칠, mask 안에 물린 배경 조각이 대상이다.

    **반사광은 작업 대상이 아니다.** 평균 밝기 + ``bright_margin`` 이상인 픽셀은 색이 평균에서 크게
    벗어나지만 객체의 일부다. seed 에서 빼는 것으로는 부족해서(옆에서 번져 들어온다) **벽으로 심어**
    번짐이 아예 못 들어가게 막는다.

    번짐은 ``mask`` 안에 갇힌다(mask 밖 = 벽) — 이 함수는 mask 를 넓히지 않는다. LoG(+``wall``) 벽도
    그대로 서 있어서, 과칠과 본체 사이에 edge 가 있으면 걷어내기가 본체로 넘어오지 못한다.

    **결과는 언제나 ``mask`` 의 부분집합이다.** 전부 걷어내지는 경우(남는 게 없음)는 지우지 않고
    ``None`` 을 돌려준다 — 객체를 통째로 잃는 것보다 손대지 않는 편이 낫다.

    Args:
        image: BGR ``(H,W,3)`` 또는 gray ``(H,W)``.
        mask: 걷어낼 대상 mask ``(H,W)`` — 작업 범위이자 결과의 상한.
        wall: 걷어내기 번짐을 막을 외부 edge 벽 ``(H,W)`` (변화량 기반 — producer 가 생성). None 이면
            벽 없이 색만으로 걷어낸다.
        tolerance: **한 seed 의** 번짐 허용 여유(채널값) — 그 seed 색 ±이 값.
        cut_tolerance: seed 자격 — 평균색에서 이 값을 **넘게** 벗어난 mask 안 픽셀만 누른다. 좁힐수록
            많이 걷어낸다(``Refine_by_color`` 의 ``seed_tolerance`` 보다 크게 잡아야 두 블록이 같은
            자리를 두고 다투지 않는다).
        bright_margin: 평균 밝기 + 이 값 이상이면 반사광 — 평균 표본에서 빼고 **벽으로 심어** 보호한다.
        seed_margin: 평균색 표본으로 쓸 안쪽 침식 폭(px) — 경계 혼합색을 평균에서 뺀다.
        grow: 걷어낸 영역을 팽창할 **반경 px** (``2*grow+1`` 원형, ``0``=끔). 벽 픽셀은 안 지워져 벽
            띠가 mask 에 남으므로 그만큼 더 걷어내는 자리. ``mask`` 밖으론 안 나간다.
        close_size: 걷어낸 영역의 CLOSE 커널(px) — 얼룩진 걷어내기를 한 덩어리로(``0``=끔).
        min_area: 걷어낸 조각 중 이보다 작은 것은 무시한다(``0``=끔).

    Returns:
        ``(H,W)`` uint8 0/255 (``mask`` − 걷어낸 영역). mask 가 비거나 전부 걷어내지면 None.
    """
    _h, _w = image.shape[:2]
    _img_full = image if image.ndim == 3 else cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    _mask_full = mask > 0
    if not _mask_full.any():
        return None

    _pad = max(grow, close_size) + 2
    _sl  = _crop_slices(_mask_full, _pad)
    _img, _m = _img_full[_sl], _mask_full[_sl]
    _gray = cv2.cvtColor(_img, cv2.COLOR_BGR2GRAY)

    # 벽 = 외부 edge(변화량) 를 crop 으로 슬라이스. 없으면 벽 없이 색만으로 걷어낸다.
    _walls = (wall[_sl] > 0) if wall is not None else np.zeros(_img.shape[:2], bool)

    _inner = cv2.erode(_m.astype(np.uint8), Make_morph_kernel(2 * seed_margin + 1)) > 0 \
        if seed_margin else _m
    if not _inner.any():
        _inner = _m

    _mean_gray = float(_gray[_inner].mean())
    _bright = _gray.astype(np.float32) >= _mean_gray + bright_margin   # 반사광 — 지우면 안 된다
    _body = _inner & ~_bright
    _ref = _img[_body if _body.any() else _inner].reshape(-1, 3).astype(np.float32).mean(axis=0)
    _dev = np.abs(_img.astype(np.float32) - _ref).max(axis=2)
    _seeds = _m & (_dev > cut_tolerance) & ~_bright              # 평균 밖이고 반사광 아닌 자리

    # 반사광·mask 밖·LoG 를 모두 벽으로 — 번짐이 반사광 안으로도, mask 밖으로도 못 나간다.
    _flood = np.zeros((_img.shape[0] + 2, _img.shape[1] + 2), np.uint8)
    _flood[1:-1, 1:-1] = (_walls | ~_m | _bright).astype(np.uint8)
    _img_c = np.ascontiguousarray(_img)
    _tol   = (int(tolerance),) * 3
    _flags = 4 | cv2.FLOODFILL_MASK_ONLY | cv2.FLOODFILL_FIXED_RANGE | (255 << 8)
    for _y, _x in np.argwhere(_seeds):
        if _flood[_y + 1, _x + 1]:                              # 벽이거나 이미 걷어낸 자리
            continue
        cv2.floodFill(_img_c, _flood, (int(_x), int(_y)), 0, _tol, _tol, _flags)

    _cut = _flood[1:-1, 1:-1] == 255
    if grow > 0:                                                # 남은 벽 띠까지 (mask 안으로)
        _cut = (cv2.dilate(_cut.astype(np.uint8),
                           Make_morph_kernel(2 * grow + 1, ellipse=True)) > 0) & _m
    if close_size > 0:
        _cut = (cv2.morphologyEx(_cut.astype(np.uint8), cv2.MORPH_CLOSE,
                                 Make_morph_kernel(close_size)) > 0) & _m
    _cut &= ~_bright                                            # 반사광은 어떤 경우에도 안 지운다
    if min_area > 0:
        _cut = Filter_by_area(_cut.astype(np.uint8) * np.uint8(255), min_area=min_area) > 0

    _out = _m & ~_cut
    if not _out.any():                                          # 통째로 사라지면 손대지 않는다
        return None
    _full = np.zeros((_h, _w), np.uint8)
    _full[_sl] = _out.astype(np.uint8) * np.uint8(255)
    return _full
