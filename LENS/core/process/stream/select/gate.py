"""선택 게이트 — ctx 값 조건으로 unit 을 통과/스킵한다 (``{}`` 반환 = 스킵).

``Base_Process`` 계약의 **"빈 dict = 이 unit 스킵"** 관례를 그대로 쓴다 — Stage 엔진이 gate 스킵 시
체인 break + ``emit`` 스킵(구조 생성 안 함). Stage 엔진이 공유돼 **Run·Sample 어디서든** 동작한다:
Run 에선 그 obj 의 이후 처리·라우팅을 멈추고(정본은 안 지움), Sample 에선 그 obj 를 학습셋에서 뺀다.

값은 source 가 ctx 에 올린 것을 읽는다 — ``obj_id``(양 source 가 주입) · 인라인 attr(``center_dist``·
``class_id`` 등; Run 은 resolve, Sample 은 inline attr). 그래서 gate 는 payload I/O 없이 판정한다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Any

from .. import PROCESS_REGISTRY, Base_Process, UI


@PROCESS_REGISTRY.Register_module()
@dataclass
class Attr_gate(Base_Process, category="선택/게이트"):
    """ctx 값 하나(``key``)를 조건과 견줘 통과(값 반환)/스킵(``{}``)한다 — 범용 selection 게이트.

    조합 예 (Sample flow 에 체인):
      - **obj0 만** — ``{key: obj_id, keep: ["0"]}``
      - **중심거리 ≤ 0.1** — ``{key: center_dist, max: 0.1}``  (Run 이 기록한 attr)
    두 gate 를 나란히 두면 AND. ``key`` 가 ctx 에 없으면 ``missing`` 정책(기본 skip — fail-closed:
    측정 안 된 obj 는 안 넣음). 통과 시 그 값을 그대로 재출력해 체인을 잇는다(ctx 오염 없음).
    """

    key:     Annotated[str,   UI(label="검사할 ctx 키 (obj_id · center_dist …)")]      = ""
    # 허용 값 목록(예: ["0"]) — 비면 미검사(전부 통과). 폼은 쉼표 구분 한 줄 입력.
    keep:    Annotated[list[str] | None, UI(label="허용 값 (쉼표 구분; 비우면 미검사)")] = None
    max:     Annotated[float | None, UI(label="상한(포함)", min=0.0, max=1.0, step=0.01)] = None
    min:     Annotated[float | None, UI(label="하한(포함)", min=0.0, max=1.0, step=0.01)] = None
    missing: Annotated[str,   UI(label="키 부재 시 (skip=fail-closed | pass)")]         = "skip"

    def Run(self, **ctx) -> dict:
        if self.key not in ctx or ctx[self.key] is None:
            return {} if self.missing == "skip" else {"_gate": True}
        _v = ctx[self.key]
        # 문자열로 정규화해 비교한다 — yaml 의 keep: ['0'] 과 ctx 의 obj_id "0"/0 이 타입만 달라
        # 조용히 통과해 버리는 걸 막는다(빈 목록 = 미검사).
        if self.keep and str(_v) not in {str(_k) for _k in self.keep}:
            return {}
        if self.max is not None or self.min is not None:
            _f = float(_v)
            if self.max is not None and _f > self.max:
                return {}
            if self.min is not None and _f < self.min:
                return {}
        return {self.key: _v}                    # 통과 — 값 재출력(=ctx 그대로, 체인 계속)
