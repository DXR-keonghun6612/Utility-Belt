"""stream — 종류1 연산: 스트리밍 ``Base_Process`` 유닛 (Stage 체인, frame/object 축).

각 도메인(preprocess/filter/mask/chroma/model/select)의 유닛. 엔진 계약(``Base_Process``·
표시 힌트 ``UI``·타입 별칭 ``BBOX``/``IMAGE``/``GRAY_IMAGE``)과 레지스트리(``PROCESS_REGISTRY``)를 여기서
재노출해, 유닛이 ``from .. import Base_Process, UI, …`` 로 얕게 참조한다(엔진은 process 루트 소유).
"""

from .. import PROCESS_REGISTRY
from .._base import Base_Process, UI, BBOX, IMAGE, GRAY_IMAGE

__all__ = ["PROCESS_REGISTRY", "Base_Process", "UI", "BBOX", "IMAGE", "GRAY_IMAGE"]
