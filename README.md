# Page-based Layout & Asset Navigator

PLAN은 Three.js + TypeScript + Vite 기반의 3D 씬 편집기다. 공용 에셋 정의와 장면 인스턴스 상태를 분리해, 하나의 에셋을 여러 위치와 파라미터로 재사용하는 구조를 목표로 한다.

## 개요

프로젝트는 세 가지 주요 작업 영역으로 구성된다.

- Scene 탭: 현재 장면의 객체 목록과 anchor 배치 상태를 확인하고, 루트 객체 추가/삭제, 빈 anchor 배치/비우기, transform 편집을 수행한다.
- Builder 탭: 선택된 인스턴스의 배치 파라미터를 편집한다. 에셋 구조 작성 책임은 Asset Editor로 분리한다.
- ASSETS 탭: `src/asset/<대분류>/<소분류>/<asset>.json` 폴더 구조를 읽기 전용 tree로 보여주고, 선택한 에셋을 Asset Editor로 연다.

Asset Editor는 새 에셋을 만들거나 기존 에셋 정의를 수정하는 별도 화면이다. 저장 시 파일명을 입력하고, 같은 이름이면 런타임 등록값을 덮어쓰며 새 이름이면 새 에셋으로 등록한다.

## 구조

- `src/core/`: scene graph, node 조립, serialization, asset 관리 로직
- `src/ui/scene/`: Scene 탭 tree, action, inspector 패널
- `src/ui/builder/`: 인스턴스 파라미터 편집 UI
- `src/ui/assets/`: asset DB tree와 asset 선택 UI
- `src/ui/asset-editor/`: Asset Editor 앱과 geometry 편집 UI
- `src/asset/`: 폴더 기반 asset DB
- `src/presets/`: 시작 장면 preset

## UI 사용법

- [Scene 탭](src/ui/scene/README.md): 장면 배치, anchor 조작, transform 편집, scene 저장/불러오기
- [Builder 탭](src/ui/builder/README.md): 선택 인스턴스의 `parameters` 편집
- [ASSETS 탭](src/ui/assets/README.md): asset DB tree 확인과 Asset Editor 진입
- [Asset Editor](src/ui/asset-editor/README.md): asset JSON 편집, preview 재빌드, 저장/전송

## 현재 기능

- 씬 편집기와 에셋 편집기를 분리한 멀티 엔트리 Vite 앱
- `AssetManager`를 통한 JSON 기반 모델, catalog, preset 로드
- Scene 저장 / 불러오기
- root 객체 추가/삭제와 anchor attach/detach를 Scene tree 안에서 처리
- 노출 가능한 anchor와 내부 anchor를 구분하기 위한 `exposed` 속성
- 선택 인스턴스의 상태(`params`, anchor override)를 공용 에셋 정의와 분리해 보관하는 코어 구조
- asset root의 `parameters` 스키마를 기준으로 Builder 편집 대상을 결정
- `"$params.length"` 같은 asset 내부 참조값을 인스턴스 파라미터로 resolve하는 조립 경로
- asset root의 `definitions`와 string child reference를 사용해 깊은 내부 구조를 평활화하는 조립 경로
- Asset Editor에서 Scene Editor로의 BroadcastChannel 기반 에셋 전달

## 개발 방향

현재 우선순위는 인스턴스 상태 저장/복원과 파라미터 기반 재빌드 흐름을 완성하는 것이다. 예를 들어 하나의 `conveyor` 에셋 정의를 공유하면서, 장면에는 5m 컨베이어와 10m 컨베이어를 각각 다른 `length`, `legGap` 값으로 배치할 수 있어야 한다.

상세 진행 항목은 `TODO.md`에서 체크박스로 관리한다.

## 개발 로그

### 2026-05-08

- 공용 에셋 정의와 인스턴스 상태를 분리하기 위해 `params`, anchor override, 인메모리 인스턴스 상태 구조를 추가했다.
- Scene 탭을 장면 상태 확인과 배치 흐름 중심으로 정리하고, root 객체 추가/삭제와 anchor attach/detach를 Scene tree 안에서 처리하도록 변경했다.
- Builder 탭은 선택 인스턴스의 파라미터 편집 역할로 한정하고, 에셋 구조 작성 책임은 Asset Editor로 분리했다.
- `src/asset/<대분류>/<소분류>/<asset>.json` 폴더 구조를 기준으로 asset DB tree를 구성하고, 별도 `ASSETS` 탭에서 읽기 전용으로 표시하도록 정리했다.
- Asset Editor는 파일명 입력 기반 저장 흐름을 사용하며, 같은 이름은 덮어쓰기, 새 이름은 새 에셋 등록으로 처리하도록 방향을 정했다.
- `src/ui/`를 `scene`, `builder`, `assets`, `asset-editor`, `app` 폴더로 나눠 탭과 역할 기준으로 정리했다.
- Builder 노출 기준을 root `parameters` 스키마로 바꾸고, conveyor의 `length`, `legGap`을 전역 파라미터로 정리했다.
- elbow, camera, chamber의 root `metadata` 값을 제거해 내부 형상 값과 인스턴스 편집 파라미터를 분리했다.
- conveyor 다리를 전용 `LegArray` geometry에서 inline `defaultNode`와 `exposed:false` 내부 anchor array 조합으로 분리했다.
- robot 에셋을 `definitions` 기반 평활화 구조로 바꾸고, J1-J6 회전값을 Builder 파라미터로 분리했다.
- scene 저장 시 각 인스턴스의 effective `params`, anchor override, transform override를 함께 기록하고, 로드 시 공용 asset 정의와 조합해 복원하도록 정리했다.
- Asset Editor를 원본 JSON 중심으로 재작업해 `parameters`, `computed`, `definitions`, inline `defaultNode` 구조를 보존한 채 preview를 재빌드하도록 변경했다.
- Scene Inspector에서 노출 anchor의 layout(`kind`, `axis`, `count`, `gap`, `start`)을 수정하고 인스턴스 `anchorOverrides`로 저장할 수 있게 했다.
