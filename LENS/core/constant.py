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

# split = 파생(sample) store 범주. build 때 frame stem 해시로 배정(=데이터셋 정체성, 재-export 파생 아님).
TRAIN = "train"
VAL   = "val"
TEST  = "test"
SPLITS: tuple[str, ...] = (TRAIN, VAL, TEST)
UNCLASSIFIED = "__unclassified__"     # 미분류 class 이름 — 정본 class_id 미지정 값 = classification fallback

# ── 라우팅 목적지 어휘 (outputs spec `to`) ──────────────────────────────────────
#
# **값이 어디로 가나** — 하나의 축, 세 개의 배타적 값. process(spec 을 쓴다)와 port(그릇을 짓는다)가
# 같이 읽으므로 여기 산다. 인라인은 사이드카 안에 사는 것이라 "트리 밖 진단"이 될 수 없다 — 그래서
# 셋이 한 축에서 갈린다(TRACE 는 항상 파일).

TO_META    = "meta"        # 사이드카 인라인 — 값이 Data_Ref.info 에 그대로 (attr·rle)
TO_STORAGE = "storage"     # 정본 파일 — 트리 leaf + {범주}/{종류}/{stem}.{ext} (전이·내보내기 대상)
TO_TRACE   = "trace"       # 진단 파일 — 트리 밖 .trace/{run}/{종류}/ (leaf 없음 = 라이프사이클 없음)
ROUTE_TARGETS: tuple[str, ...] = (TO_META, TO_STORAGE, TO_TRACE)

TRACE_DIR = ".trace"       # 진단 산출물 루트 ({root}/.trace/{run}/…) — 트리 밖이라 `.` 로 숨긴다
