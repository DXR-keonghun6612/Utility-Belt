from __future__ import annotations

from abc import ABC, abstractmethod

from ..handler import Data_Ref


class Base_Converter(ABC):
    """raw 입력을 새 dataset 포맷(``Data_Ref``)으로 변환하는 베이스.

    포맷별 변환 전략은 이 클래스를 상속해 ``Convert`` 를 구현한다 (예: ``discover/`` 의
    폴더 스캔 계열). 파일 쓰기·경로는 직접 하지 않고 dataset 핸들러(``handler.Save``)에
    위임한다 — converter 는 디스크립터 템플릿과 raw 소스만 정한다.
    """

    @abstractmethod
    def Convert(
        self, stem_root: str, params_root: str
    ) -> tuple[list[tuple[str, Data_Ref]], dict[str, Data_Ref]]:
        """raw 입력을 탐색해 ``(stem, 컨테이너 Data_Ref)`` 목록과 params 를 반환한다.

        프레임 파일은 ``stem_root`` 에, params 파일은 ``params_root`` 에 쓴다 — staging 에서
        새 프레임은 ``modified`` 버킷(``{root}/modified``)으로, params/id_map 은 상태 무관하게
        ``root`` 직속으로 가르기 위함이다 (flow 의 프레임 root vs params root 분리와 동일).

        Args:
            stem_root: 프레임 파일 출력 루트 (보통 ``{save_root}/modified``).
            params_root: params 파일 출력 루트 (``save_root`` 직속).

        Returns:
            frames: ``(stem, 컨테이너 Data_Ref)`` 목록 (``type="stem"``; 자식 ``info`` 는 leaf 로 시작).
            params: ``{name: Data_Ref}`` — ``Dataset_Meta.params``(범주 무관 root 데이터)에 등록될 값.
        """

    def Load_id_map(self) -> dict[str, dict[str, int]]:
        """class→scope→id 정의를 반환한다 (없으면 빈 dict)."""
        return {}
