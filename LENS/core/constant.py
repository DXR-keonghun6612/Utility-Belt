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
# 미분류 class_id — id_map 0번 슬롯(`no_label`)이자 학습 측 ignore_index. `class_id` attr 은 **번호**를
# 들고 이름은 id_map 조회로만 얻는다: 이름은 개정되지만(부품코드) 번호는 안 움직이므로, 이름을 저장하면
# 개정 한 번에 저장된 라벨 전부가 id_map 과 어긋난다(실제로 19만 건이 그렇게 끊겼다).
UNCLASSIFIED_ID = 0

# ── 라벨의 출처 — `class_id` 옆 객체 attr ────────────────────────────────────────
#
# **값과 근거는 같은 자리에 둔다.** 라벨이 사람이 보고 정한 것인지 자동 배정(type 다수결 등)이 붙인
# 것인지 구분이 없으면, 그 라벨로 학습한 모델이 **자기 출력을 다시 배운다**. obj 단위로 붙는 이유도
# 같다 — 결정이 객체마다 나므로 stem 이나 class 에 걸면 섞인다.
#
# 없으면 `human` 으로 읽지 **않는다** — 모르는 것이다(이 칸이 생기기 전에 붙은 라벨).
CLASS_SRC  = "class_src"
# **사람의 결정이 있었다.** 표본을 눈으로 보고 정했든 분석 결과(구성·순도·거리)를 보고 정했든 같다 —
# 근거의 종류가 다를 뿐 결정의 주체가 사람이다(무리 전체를 잰 값이 눈짐작보다 나은 근거이기도 하다).
SRC_HUMAN  = "human"
# 사람의 결정 없이 앉은 라벨 — 모델 예측 write-back 처럼 **학습된 것이 자기 라벨을 다시 만드는** 경로.
# 이쪽만 학습 입력에서 걸러야 한다. 가르는 기준은 "얼마나 봤나" 가 아니라 "결정이 있었나" 다.
SRC_AUTO   = "auto"
# 그 0번 슬롯의 이름. 내보내기(`export`)와 정본 표 편집(`id_map`)이 같은 문자열을 써야 하므로 여기 산다 —
# class 를 지운다는 건 **그 라벨을 이 자리로 되돌린다**는 뜻이라 두 곳이 같은 슬롯을 가리켜야 한다.
UNLABELED_CLASS = "no_label"

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
