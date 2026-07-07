"""CLI (얇은 래퍼) — 배경 크로마 공간 의존성 진단. ``python -m analysis --c0-acc ... --c1-acc ...``

analyze 로 ``ChromaDiag`` 를 계산하고, 표현(리포트·히트맵 저장/표시)은 공통 :func:`present` 에
위임한다. chroma 패키지가 ``format_report``/``build_figure`` 를 노출하므로 그대로 넘긴다.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from core.pipeline.process.chroma._space import CHROMA_SPACES

import analysis.chroma as chroma
from analysis._base import present


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="배경 크로마 공간 의존성 진단 (전역 vs 픽셀별 결정)")
    p.add_argument("--space", choices=sorted(CHROMA_SPACES), default="hsv",
                   help="색공간 (hsv=H·S / lab=a*·b*) — 누산에 쓴 space 와 맞출 것")
    p.add_argument("--c0-acc", type=Path, required=True,
                   help="c0_acc npy 파일 또는 디렉토리 (dir 이면 최대 누산 스냅샷 자동 선택)")
    p.add_argument("--c1-acc", type=Path, required=True, help="c1_acc npy 파일 또는 디렉토리")
    p.add_argument("--window", type=int, default=10,
                   help="robust mode 채택 반경(bin) — 누산에 쓴 pixelwise_chroma_stats.window 와 맞출 것")
    p.add_argument("--min-count", type=int, default=10,
                   help="진단·시각화에 쓸 픽셀별 최소 표본 수 (이하=저신뢰, 제외)")
    p.add_argument("--out-dir", type=Path, default=None,
                   help="히트맵/리포트 저장 경로 (기본: c0-acc 의 부모)")
    p.add_argument("--no-show", action="store_true", help="히트맵 창 띄우지 않음 (저장만)")
    p.add_argument("--no-plot", action="store_true", help="시각화 생략(수치 리포트만)")
    return p


def main() -> None:
    args = _build_parser().parse_args()

    print(f"[analyze] space={args.space}  c0={args.c0_acc}  c1={args.c1_acc}")
    diag = chroma.analyze(args.c0_acc, args.c1_acc,
                          space=args.space, window=args.window, min_count=args.min_count)

    _out_dir = args.out_dir or args.c0_acc.parent
    present(diag, chroma, _out_dir,
            prefix=f"chroma_spatial_{diag.space.name}",
            plot=not args.no_plot, show=not args.no_show)


if __name__ == "__main__":
    main()
