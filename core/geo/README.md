# Core Geo Module (Location Manager)

## 개요
이 모듈(`core/geo`)은 거래가 발생한 장소의 위치 정보(Coordinates)를 다룹니다. 단순히 좌표를 저장하는 것을 넘어, 위치 데이터의 유효성을 검증하고 추후 지도 서비스와 연동하기 위한 기반 로직을 제공합니다.

## 주요 기능

### 1. Location Validator (`location.py`)
*   **유효성 검사:** 입력된 위도(Latitude)와 경도(Longitude)가 유효한 범위 내에 있는지 확인합니다.
    *   위도: -90 ~ 90
    *   경도: -180 ~ 180
*   **포맷팅:** 다양한 형식의 좌표 입력(예: DMS)을 표준 십진수(Decimal Degrees) 포맷으로 변환 및 통일.

### 2. Geo-Spatial Helpers (Future Plan)
*   **거리 계산:** 두 지점 사이의 거리를 계산 (예: Haversine 공식 적용).
*   **영역 필터링:** 특정 지도 화면(Bounding Box) 내에 포함되는 거래 내역을 찾기 위한 쿼리 헬퍼.

## 데이터 구조
위치 정보는 보통 `(latitude, longitude)`의 튜플 형태나, 이를 감싼 객체 형태로 Core 내부에서 전달됩니다.
