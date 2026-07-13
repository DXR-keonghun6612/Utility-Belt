"""마이그레이션 — 옛 정본에 섞여 있던 **진단 leaf** 를 트리 밖 ``.trace/legacy`` 로 보낸다.

옛 flow 는 중간·디버그 산출물을 정본과 같은 메커니즘(``to: storage``)으로 냈다 — 그래서 ``edge``·
``mask`` 같은 진단 이미지가 정본 leaf 로 사이드카에 실리고, 전이(``Move``)·삭제·병합·내보내기의
라이프사이클을 함께 탔다(검수에서 버린 프레임의 디버그까지 영구 보존됐다). 지금은 진단이 ``to: trace``
로 트리 밖으로 빠지므로, 옛 저장본의 진단 leaf 를 걷어내 그 상태로 맞춘다.

**정본으로 남는 것** — ``frame``(원본) · ``class_id``(인라인 라벨) · ``segment``(인스턴스 라벨맵,
geometry 원천) · 객체 BRANCH(bbox). **진단으로 빠지는 것** — ``DEBUG_KINDS``.

하는 일 둘:

- 사이드카에서 진단 leaf 를 뗀다(``Pop`` → ``Save``) — 정본 트리가 셋만 남는다.
- 진단 payload 폴더 ``{cat}/{kind}`` 를 통째 ``.trace/legacy/{cat}/{kind}`` 로 옮긴다. 폴더째라
  사이드카가 참조하던 파일이든 트리에서 떨어진 고아(예: ``Replace_branches`` 잔재)든 함께 걷힌다.

**파생(sample) 은 안 건드린다** — 진단 leaf 는 정본에만 있었다.

실행 (기본은 dry-run — 무엇이 바뀔지만 찍는다):

    python migrate_debug_to_trace.py result/sl_mirror_tech
    python migrate_debug_to_trace.py result/sl_mirror_tech --write
"""

from __future__ import annotations

import argparse
import shutil
import sys
from collections import Counter
from pathlib import Path

from core.constant import META_STATES, TRACE_DIR
from core.store import Dataset_Meta

# 정본에서 진단으로 빠지는 leaf 이름(=종류 폴더). 정본은 frame·class_id·segment·객체 bbox 만.
DEBUG_KINDS = frozenset({"edge", "mask", "seg_raw", "hole_seed", "hole_edge", "hole_grown"})


def _strip_sidecars(store: Dataset_Meta, *, write: bool) -> Counter:
    """모든 item 에서 진단 leaf 를 뗀다 (뗀 종류별 개수). write 면 사이드카를 다시 쓴다."""
    _stripped: Counter = Counter()
    for _cat, _key, _item in store._iter():
        _debug = [_n for _n in _item.Leaves() if _n in DEBUG_KINDS]
        if not _debug:
            continue
        for _n in _debug:
            _item.Pop(_n)
            _stripped[_n] += 1
        if write:
            store.Save(_key)                              # 진단 빠진 사이드카 다시 쓰기
    return _stripped


def _archive_payload(root: Path, *, write: bool) -> Counter:
    """진단 payload 폴더 ``{cat}/{kind}`` → ``.trace/legacy/{cat}/{kind}`` (옮긴 파일 수)."""
    _moved: Counter = Counter()
    for _cat in META_STATES:
        for _kind in DEBUG_KINDS:
            _src = root / _cat / _kind
            if not _src.is_dir():
                continue
            _moved[_kind] += sum(1 for _f in _src.iterdir() if _f.is_file())
            if write:
                _dst = root / TRACE_DIR / "legacy" / _cat / _kind
                _dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(_src), str(_dst))
    return _moved


def migrate(root: Path, *, write: bool) -> None:
    print(f"\n═══ {root}  ({'적용' if write else 'dry-run'})")
    if not (root / ".meta").is_dir():
        print("  .meta 없음 — 건너뜀")
        return
    _store = Dataset_Meta.Restore(root)
    _stripped = _strip_sidecars(_store, write=write)
    _moved = _archive_payload(root, write=write)

    print("  사이드카에서 뗀 진단 leaf:")
    for _n in sorted(DEBUG_KINDS):
        if _stripped[_n]:
            print(f"      {_n:12s} {_stripped[_n]}")
    print(f"  → .trace/legacy 로 옮긴 payload 파일: {sum(_moved.values())}")
    if write:
        _orphans = _store.Vacuum()                        # 진단 폴더 밖의 잔여 고아 청소
        print(f"  Vacuum 이 지운 잔여 고아: {_orphans}")
    else:
        print("  (--write 를 주면 사이드카 재작성 + payload 이동 + Vacuum 을 수행)")


def main() -> int:
    _ap = argparse.ArgumentParser(description="진단 leaf 를 .trace/legacy 로 보내는 마이그레이션")
    _ap.add_argument("roots", nargs="+", help="dataset root(들)")
    _ap.add_argument("--write", action="store_true", help="실제로 적용 (기본은 dry-run)")
    _args = _ap.parse_args()
    for _r in _args.roots:
        migrate(Path(_r), write=_args.write)
    return 0


if __name__ == "__main__":
    sys.exit(main())
