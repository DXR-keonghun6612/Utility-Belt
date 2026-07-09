"""gui/steps — process-chain 편집 공통 모듈 (run·sampler 공유).

process step 카드(``Process_step``: 타입 선택 + 파라미터 폼 + inputs/slots/outputs 배선)와 그 동적
목록 컨테이너(``Step_list``: add/remove/move + min-count 정책)를 소유한다. `core.process.PROCESS_REGISTRY`
를 반영해 UI 를 자동 생성하며, 소비처(run 의 Flow_card·sampler 의 실체화 체인)는 ``to_config()``/``load()``
config-dict 계약으로만 붙는다 — 표현(현재 카드)을 나중에 node-graph 로 갈아끼워도 계약은 고정. 설계는 README.
"""

from gui.steps._list import Step_list
from gui.steps._step import Process_step

__all__ = ["Process_step", "Step_list"]
