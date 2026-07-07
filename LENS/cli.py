"""LENS CLI — config 파일로 ``Pipeline`` 을 만들고 단계를 순서대로 실행하는 얇은 래퍼.

``python cli.py --config <config.yaml> --stages converter run verify``. 각 stage 는 독립이며
나열한 순서대로 돈다. config 로드·경로 resolve·실행은 모두 ``core`` 의 ``Pipeline`` 이 한다 —
이 파일은 인자 파싱과 진행 출력만 담당한다.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from core import Load_pipeline

_STAGES = ("converter", "run", "verify")   # 실행 가능한 단계 (나열 순서대로 수행)


def main() -> None:
    parser = argparse.ArgumentParser(prog="LENS")
    parser.add_argument("--config", type=Path, required=True, help="config.yaml 경로")
    parser.add_argument(
        "--stages",
        nargs="+",
        choices=_STAGES,
        metavar=f"{{{','.join(_STAGES)}}}",
        required=True,
        help="실행할 단계 (순서대로)",
    )
    args = parser.parse_args()

    pipeline = Load_pipeline(args.config)

    for stage in args.stages:
        if stage == "converter":
            n = pipeline.Convert()
            if n == 0:
                print(f"⚠ converter: 매칭 파일 0개 — sources/globs 확인 → {pipeline.root}")
            else:
                print(f"converter 완료 → {n} frames, {pipeline.root}")
        elif stage == "run":
            pipeline.Run()
            print(f"run 완료 → {pipeline.root}")
        elif stage == "verify":
            pipeline.Verify()
            print(f"verify 완료 → {pipeline.root}")


if __name__ == "__main__":
    main()