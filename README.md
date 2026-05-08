# Page-based Layout & Asset Navigator

PLAN은 Three.js + TypeScript + Vite 기반의 3D 씬 편집기로, 페이지형 레이아웃 구성, 에셋 배치, 재사용 가능한 모델 조립을 위한 프로젝트다.

## 개요

프로젝트는 두 개의 편집기로 나뉜다.

- Scene Editor: 모델을 장면에 배치하고, 계층을 확인하고, transform을 조정하고, anchor에 객체를 부착하며, 장면을 저장/불러온다.
- Asset Editor: 모델 구조를 만들거나 수정하고, geometry를 미리 보고, 메인 편집기로 에셋을 다시 등록한다.

현재 노드 모델은 `GROUP`, `ANCHOR`, `JOINT`, `LINK`를 사용해 컨테이너 구조, 부착 지점, 관절, geometry를 분리한다.

## 현재 기능

- 씬 편집기와 에셋 편집기를 분리한 멀티 엔트리 Vite 앱
- `AssetManager`를 통한 JSON 기반 모델 / 프리셋 로드
- Scene 저장 / 불러오기
- Anchor 기반 부착 및 배열 배치
- Asset Editor에서 Scene Editor로의 BroadcastChannel 기반 에셋 전달

## 현재 진행 방향

다음 단계의 핵심은 공용 에셋 정의와 장면 인스턴스 상태를 더 명확히 분리하는 것이다.

- `Scene` 탭: 장면 상태 확인, 루트 객체 배치, anchor 부착, transform 편집
- `Builder` 탭: 현재 선택된 인스턴스의 배치 파라미터 편집
- `Asset Editor`: 새 에셋 생성 및 인스턴스 기반 에셋 저장

목표는 여러 장면 인스턴스가 하나의 에셋 정의를 공유하면서도, 각 인스턴스는 `length`, `legCount`, 슬롯 지정, anchor override 같은 작은 상태만 별도로 가지게 만드는 것이다.

## 개발 노트

- 2026-05-08: 다음 단계의 기준을 인스턴스 파라미터 편집, 루트 배치 흐름, 파일명 기준 에셋 저장 방식으로 재정의함.
