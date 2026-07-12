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

WORKING = "data"                      # (레거시) split 없는 단일 파생 버킷 — sampler 마이그레이션 전까지 존치
# split = 파생(sample) store 범주. build 때 frame stem 해시로 배정(=데이터셋 정체성, 재-export 파생 아님).
TRAIN = "train"
VAL   = "val"
TEST  = "test"
SPLITS: tuple[str, ...] = (TRAIN, VAL, TEST)
UNCLASSIFIED = "__unclassified__"     # 미분류 class 이름 — 정본 class_id 미지정 값 = classification fallback
