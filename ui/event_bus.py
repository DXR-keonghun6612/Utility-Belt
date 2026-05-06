"""애플리케이션 전역 이벤트 버스.

컴포넌트 간 결합도를 낮추기 위해 Publish-Subscribe(Pub/Sub) 패턴을 구현한 싱글톤 시그널 허브입니다.
Main_Window 등 특정 부모 위젯을 경유하지 않고 위젯끼리 독립적으로 통신할 수 있게 합니다.
"""
from PySide6.QtCore import QObject, Signal


class _Event_Bus(QObject):
    # Scene 조작 시그널
    scene_loaded = Signal()                   # 새로운 씬이 완전히 로드됨
    scene_path_changed = Signal(str)          # 현재 scene 파일 경로가 변경됨
    scene_mutated = Signal()                  # 씬의 구조(노드 추가/삭제)가 변경됨
    selection_changed = Signal(list)          # 아웃라이너나 뷰포트에서 노드가 선택됨 (list[Base_Node])
    loading_progress = Signal(int, int, str)  # 파일/mesh 로드 진행 상태
    simulation_progress = Signal(int, int, str)  # 시뮬레이션 진행 상태
    
    # 노드 속성 변경 시그널
    property_changed = Signal()               # 인스펙터 등에서 노드의 속성(Transform 등)이 변경됨
    
    # 카메라 조작 시그널
    camera_changed = Signal()                 # 카메라 렌즈/파라미터 값 변경 (UI에서 조작)
    camera_moved = Signal()                   # 카메라 물리적 위치/각도 변경 (마우스 드래그 조작)
    
    # 뷰포트 표시 설정 시그널
    viewer_config_changed = Signal()            # 그리드 간격·범위 등 뷰포트 표시 설정 변경

# 싱글톤 인스턴스 전역 노출
EVENT_BUS = _Event_Bus()
