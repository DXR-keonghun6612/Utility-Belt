"""횡단 공유 상수 — 여러 단계(meta/process/sampling)가 같이 쓰는 값의 단일 소스(문자열 중복 방지).

타입 별칭·표시 메타는 값이 아니라 타입이라 [`typing.py`](typing.py) 에 둔다. 도메인-로컬 상수
(``META_FILE``·``DEFAULT_SPACE`` 등)는 여기로 올리지 않는다 — 소유 패키지에 둔다.
"""

from __future__ import annotations

# ── staging 상태 어휘 ──────────────────────────────────────────────────────────

MODIFIED = "modified"                 # working 버킷 — flow 가공 대상 (작업 할거)
STAGED   = "staged"                   # 검수 완료 버킷 — annotation 대상 (검수한거)
SKIPPED  = "skipped"                  # 보류 버킷 — 작업 대상 외 (되돌리기 가능, 모든 파이프라인서 제외)
# 정본(meta) 스테이지 범주. Run→modified·Sample/Export→staged 만 지목하므로 skipped 는 자연히 빠진다.
META_STATES: tuple[str, ...] = (MODIFIED, STAGED, SKIPPED)

# ── 파생(sample) 스테이지 어휘 ──────────────────────────────────────────────────

WORKING = "data"                      # 파생 작업 버킷 — split 없는 단일 범주 (분석·class 재배정 대상)
# train/val/test 는 store 범주가 아니라 내보내기 산출물(frame stem 해시로 파생) — 여기선 이름만.
SPLITS: tuple[str, ...] = ("train", "val", "test")
UNCLASSIFIED = "__unclassified__"     # 미분류 class 이름 — 정본 class_id 미지정 값 = classification fallback
