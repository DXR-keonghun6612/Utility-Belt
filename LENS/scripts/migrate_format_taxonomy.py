"""사이드카 마이그레이션 — 옛 `format[0]`(handler 이름) → 새 `(domain, format)` taxonomy.

port 가 `format = (handler, detail)` 에서 **`(domain, format)`** 로 바뀌었다(도메인 = 무엇을 담나 / 포맷 =
어떻게 직렬화하나). 대부분의 첫 칸은 **이미 도메인 이름**이라 그대로다(`image`·`segmap`·`array`·`docs`) —
실제로 바뀌는 건 인라인 마스크뿐이다:

    ("rle", "rle")  →  ("mask", "rle")      # rle 은 handler 가 아니라 mask 도메인의 한 포맷이다

`Restore` 가 모양 안 맞는 서술자에 **fail-loud** 하므로(조용히 안 버림), 옛 저장본은 이 스크립트 없이는
안 열린다. payload 파일은 **안 건드린다** — 인라인 값이라 사이드카 JSON 안에만 산다.

실행:
    python scripts/migrate_format_taxonomy.py <dataset_root> [--dry-run]

`dataset_root` 아래 `.meta/**/*.json`(정본) 과 `sample/*/.meta/**/*.json`(파생)을 모두 훑는다.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

#: 옛 첫 칸 → 새 (domain, format). 첫 칸이 곧 도메인이던 것들은 여기 없다(무변경).
RENAMES: dict[str, tuple[str, str]] = {
    "rle": ("mask", "rle"),
}


def _migrate_node(node: dict) -> int:
    """서술자 dict(재귀) 를 제자리 마이그레이션 — 바꾼 leaf 수를 돌려준다."""
    _n = 0
    _fmt = node.get("format")
    if isinstance(_fmt, (list, tuple)) and _fmt:
        _new = RENAMES.get(_fmt[0])
        if _new is not None:
            node["format"] = list(_new)
            _n += 1
    _info = node.get("info")
    if isinstance(_info, dict):
        for _v in _info.values():                    # BRANCH 자식 또는 LEAF payload
            if isinstance(_v, dict) and "format" in _v:
                _n += _migrate_node(_v)
    return _n


def Migrate(root: Path, *, dry_run: bool = False) -> tuple[int, int]:
    """``root`` 아래 모든 사이드카를 마이그레이션 — ``(바꾼 파일 수, 바꾼 leaf 수)``."""
    _files = sorted(root.rglob(".meta/**/*.json"))
    _nf = _nl = 0
    for _p in _files:
        try:
            _data = json.loads(_p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as _e:
            print(f"  ! 읽기 실패 (건너뜀): {_p} — {_e}", file=sys.stderr)
            continue
        if not isinstance(_data, dict):
            continue
        _n = _migrate_node(_data)
        if not _n:
            continue
        _nf += 1
        _nl += _n
        print(f"  {'[dry]' if dry_run else '[fix]'} {_p.relative_to(root)} — leaf {_n}개")
        if not dry_run:
            _p.write_text(json.dumps(_data, ensure_ascii=False, indent=2), encoding="utf-8")
    return _nf, _nl


def main() -> int:
    _ap = argparse.ArgumentParser(description="사이드카 format taxonomy 마이그레이션 (rle → mask/rle)")
    _ap.add_argument("root", type=Path, help="dataset_root (정본·파생 사이드카를 모두 훑는다)")
    _ap.add_argument("--dry-run", action="store_true", help="쓰지 않고 바뀔 것만 보여준다")
    _a = _ap.parse_args()
    if not _a.root.exists():
        print(f"경로가 없습니다: {_a.root}", file=sys.stderr)
        return 1
    print(f"사이드카 스캔: {_a.root}")
    _nf, _nl = Migrate(_a.root, dry_run=_a.dry_run)
    print(f"\n{'바꿀' if _a.dry_run else '바꾼'} 파일 {_nf}개 · leaf {_nl}개"
          + (" (dry-run — 아무것도 안 썼다)" if _a.dry_run else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
