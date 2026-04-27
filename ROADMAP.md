# Sandbox Refactoring Roadmap

## 개요

Three.js 기반 3D 뷰어를 범용 씬 편집 도구로 확장한다.
크게 두 영역으로 나뉜다.

- **A. 백엔드 모듈**: 3D 요소를 노드 그래프로 추상화하고 직렬화
- **B. 프론트엔드 UI**: 노드 트리 기반 3탭 관리 패널

---

## A. 백엔드 모듈

### 핵심 방향

모델 구조(부모-자식 관계, 조인트 축, 형상 파라미터)는 **JSON 데이터**로 정의한다.
코드는 그 데이터를 읽어 조립하는 역할만 한다.
새 모델을 추가할 때 코드 파일은 건드리지 않고 **JSON 파일 하나만 추가**하면 된다.

```
JSON (관계 · 형상 정의)
    ↓ NodeAssembler.load(json)
SceneNode 트리 (부모-자식 관계)
    ↓ NodeFactory.build(descriptor)
THREE.Group (실제 3D 메쉬)
    ↓ scene.add(node.object3D)
씬
```

---

### A-1. 코어 시스템 (고정 파일)

새 모델이 추가되어도 이 파일들은 변경되지 않는다.

#### SceneNode 구조

```
SceneNode
├── id: string              (고유 식별자, e.g. "robot.j2")
├── label: string           (표시 이름, e.g. "J2 Shoulder")
├── type: NodeType          (ROOT | JOINT | LINK | PART | CAMERA | FIXTURE)
├── object3D: THREE.Group
├── parent: SceneNode | null
├── children: SceneNode[]
└── metadata: Record<string, any>   (축, 범위, 치수 등 도메인 정보)
```

#### 경계 캡슐화 원칙

씬은 각 모델의 root node만 `scene.add()` 한다.
내부 계층은 JSON 정의에서만 다룬다.

```
ChamberApp (씬)
├── chamber   → root SceneNode
└── robot     → root SceneNode
                ├── base        [LINK]
                ├── j1          [JOINT]
                │   └── j2      [JOINT]
                │       ├── link_upper  [LINK]
                │       └── j3  [JOINT]
                │           └── ...
                └── camera      [CAMERA]
```

#### 구현 파일

| 파일 | 역할 |
|---|---|
| `src/core/SceneNode.ts` | 노드 클래스 — id, type, parent/children 관계, object3D 보유 |
| `src/core/NodeFactory.ts` | geometry descriptor → `THREE.Group` (CADUtils 호출 담당) |
| `src/core/NodeRegistry.ts` | 전체 노드 id 관리 (중복 방지, id로 노드 조회) |
| `src/core/NodeAssembler.ts` | JSON 노드 정의 → SceneNode 트리 재귀 조립 |

---

### A-2. 모델 정의 (데이터 파일)

새 모델 추가 = JSON 파일 하나 추가. 코드 변경 없음.

```
src/models/
├── vision_robot.json
├── chamber.json
├── conveyor.json
└── elbow.json
```

#### 포맷 예시 (`vision_robot.json` 발췌)

```jsonc
{
  "id": "robot",
  "type": "ROOT",
  "geometry": { "shape": "Cylinder", "radiusTop": 0.6, "radiusBottom": 0.65, "height": 0.2, "color": "#d8dbe2" },
  "transform": { "position": [0, 0, 0], "rotation": [0, 0, 0] },
  "children": [
    {
      "id": "robot.j1",
      "type": "JOINT",
      "geometry": { "shape": "Capsule", "radius": 0.45, "length": 0.8, "color": "#d8dbe2" },
      "transform": { "position": [0, 0.2, 0], "rotation": [0, 0, 0] },
      "metadata": { "axis": "y", "min": -3.14, "max": 3.14, "label": "J1 Base (Yaw)" },
      "children": [
        {
          "id": "robot.j2",
          "type": "JOINT",
          "geometry": { "shape": "JointCapsule", "radius": 0.4, "length": 1.0, "bodyColor": "#d8dbe2", "capColor": "#00bcd4" },
          "transform": { "position": [0, 0.8, 0], "rotation": [0.52, 0, 0] },
          "metadata": { "axis": "x", "min": -3.14, "max": 3.14, "label": "J2 Shoulder (Pitch)" },
          "children": ["..."]
        }
      ]
    }
  ]
}
```

---

### A-3. 직렬화 (Read / Write)

#### 모델 vs 씬 구분

| 개념 | 파일 위치 | 역할 |
|---|---|---|
| **Model** | `src/models/*.json` | 독립 3D 객체 정의. 자기 자신의 노드 구조·형상만 기술 |
| **Scene** | `src/presets/*.json` | 모델 인스턴스 배치 + 인스턴스 간 부착 관계 기술 |

모델 파일은 다른 모델을 참조하지 않는다.
씬 파일은 "어떤 모델을, 어디에, 무엇에 붙여서" 배치할지만 기술한다.

#### 씬 스냅샷 포맷 (`SceneSnapshot`)

```jsonc
{
  "version": 1,
  "scene": [
    {
      "model": "chamber",
      "instanceId": "chamber_0",
      "transform": { "position": [0, 0, 0], "rotation": [0, 0, 0] },
      "children": [
        {
          "model": "robot_ur5e",
          "instanceId": "robot_0",
          "attachTo": "chamber_0.ceiling",     // 챔버 천장 노드에 부착
          "transform": { "position": [0, 0, 0], "rotation": [3.14, 0, 0] },
          "overrides": {
            "robot_0.j1": { "rotation": [0, 0.5, 0] }
          },
          "children": [
            {
              "model": "camera_3lens",
              "instanceId": "camera_0",
              "attachTo": "robot_0.j6",        // 로봇 j6에 카메라 부착
              "transform": { "position": [0, 0, 0.2], "rotation": [0, 0, 0] }
            }
          ]
        }
      ]
    },
    {
      "model": "conveyor",
      "instanceId": "conveyor_0",
      "transform": { "position": [15, 0, 0], "rotation": [0, 0, 0] },
      "children": [
        {
          "model": "elbow",
          "instanceId": "elbow_0",
          "attachTo": "conveyor_0.surface",    // 컨베이어 표면에 부품 적재
          "transform": { "position": [-3, 0, 0], "rotation": [0, 0.5, 0] }
        },
        {
          "model": "elbow",
          "instanceId": "elbow_1",
          "attachTo": "conveyor_0.surface",    // 같은 모델 여러 인스턴스
          "transform": { "position": [0, 0, 0], "rotation": [0, 1.2, 0] }
        }
      ]
    }
  ]
}
```

#### instanceId와 노드 id 네임스페이스

같은 모델을 여러 번 인스턴스화할 때 노드 id 충돌을 방지한다.
`NodeAssembler.load(descriptor, instanceId)` 호출 시 모델 내부의 모든 노드 id가
`<model_root_id>.*` → `<instanceId>.*` 로 치환된다.

```
모델 "elbow" (root id: "elbow")를 instanceId "elbow_0"으로 로드
  → NodeRegistry에 "elbow_0" 으로 등록

모델 "robot_ur5e" (root id: "robot")를 instanceId "robot_0"으로 로드
  → "robot"    → "robot_0"
  → "robot.j1" → "robot_0.j1"
  → "robot.j6" → "robot_0.j6"   ← attachTo 타겟이 됨
```

#### 구현 파일

| 파일 | 역할 |
|---|---|
| `src/core/SceneSerializer.ts` | 현재 SceneNode 트리 상태 → SceneSnapshot JSON |
| `src/core/SceneDeserializer.ts` | SceneSnapshot → 재귀 모델 인스턴스화 + attachTo 연결 |
| `src/presets/chamber_default.json` | ChamberApp 기본 씬 프리셋 |
| `src/presets/conveyor_line.json` | CADViewerApp 씬 프리셋 |

---

## B. 프론트엔드 UI

lil-gui 단순 슬라이더 나열에서 벗어나 노드 계층 구조를 탐색하고 제어할 수 있는 3탭 패널을 만든다.

### 탭 구조

```
┌────────────────────────────────────────┐
│  [ Scene Graph ] [ Inspector ] [ Builder ]
├────────────────────────────────────────┤
│              탭별 내용                  │
└────────────────────────────────────────┘
```

| 탭 | 역할 |
|---|---|
| **Scene Graph** | 전체 씬 노드 트리 탐색, 노드 선택 |
| **Inspector** | 선택된 노드의 런타임 값 조작 (조인트 각도, 위치 등 — 이미 만들어진 것을 움직임) |
| **Builder** | 노드의 구조/형상 자체를 편집 (새 노드 추가, 메쉬 파라미터, 조인트 축 설정 — 모델을 만들고 수정) |

---

### B-1. Scene Graph 탭 + Inspector 탭

#### Scene Graph 탭

```
┌─────────────────────────────┐
│  SCENE GRAPH            [−] │
├─────────────────────────────┤
│ ▼ chamber        [FIXTURE]  │
│ ▼ robot          [ROOT]     │
│   ▼ j1           [JOINT]    │
│     ▼ j2         [JOINT]    │
│       · link_upper [LINK]   │
│       ▼ j3       [JOINT]    │
│         ...                 │
│   · camera       [CAMERA]   │
└─────────────────────────────┘
```

- 노드 클릭 → Inspector 탭 갱신
- 3D 씬에서 오브젝트 클릭 (raycasting) → 트리에서 해당 노드 하이라이트

#### Inspector 탭

```
┌─────────────────────────────┐
│  PROPERTIES                 │
│  id     : robot.j2          │
│  type   : JOINT             │
│  ─────────────────────      │
│  rotation.x  [━━●━━━] 0.52  │
│  rotation.y  [━━━●━━] 0.00  │
│  (axis: x / range: ±π)      │
├─────────────────────────────┤
│  PRESETS                    │
│  [Load ▾]  [Save] [Export]  │
└─────────────────────────────┘
```

- JOINT 노드: `metadata`의 축/범위를 읽어 슬라이더 자동 생성
- FIXTURE/ROOT 노드: position / rotation 표시
- Presets: `SceneSerializer`로 현재 상태 export, `SceneDeserializer`로 불러오기

#### 구현 파일

| 파일 | 역할 |
|---|---|
| `src/ui/SceneGraphPanel.ts` | 트리 렌더링 + 노드 선택 이벤트 |
| `src/ui/PropertiesPanel.ts` | 선택 노드 기반 프로퍼티 슬라이더 자동 생성 |
| `src/ui/PresetPanel.ts` | 저장/불러오기 버튼 |
| `src/ui/RaycastSelector.ts` | 3D 씬 클릭 → 노드 선택 연동 |

---

### B-2. Builder 탭

**목표**: 기존 노드를 조작하는 것이 아니라 새 노드를 설계하고 조립하는 탭.
로봇 팔을 하나 추가하거나, 조인트 축 방향을 바꾸거나, 링크 메쉬의 크기/위치를 수정하는 작업을 GUI로 처리한다.

```
┌────────────────────────────────────────┐
│  TARGET NODE                           │
│  robot  ▾  >  j3  ▾                   │  ← 편집할 노드 선택 (부모 기준 드릴다운)
├────────────────────────────────────────┤
│  NODE TREE  (선택된 노드 하위만 표시)   │
│  ▼ j3              [JOINT]             │
│    · link_lower    [LINK]   [+] [×]    │
│    ▼ j4            [JOINT]  [+] [×]   │
│      · link_wrist  [LINK]   [+] [×]   │
│  [ + Add Child Node ]                  │
├────────────────────────────────────────┤
│  SELECTED: link_lower  [LINK]          │
│                                        │
│  ■ Geometry                            │
│    Shape   [ Capsule ▾ ]               │  ← Capsule / Box / Cylinder / Torus
│    radius  [━━●━━━━━] 0.30             │
│    length  [━━━━●━━] 3.92              │
│                                        │
│  ■ Material                            │
│    color   [■ #d8dbe2 ]                │
│                                        │
│  ■ Transform  (relative to parent)     │
│    pos.x   [━━━●━━━] 0.00             │
│    pos.y   [━━●━━━━] 1.96             │
│    pos.z   [━━━━●━━] -0.25            │
│    rot.x   [━━━●━━━] 0.00             │
│    rot.y   [━━━●━━━] 0.00             │
│    rot.z   [━━━●━━━] 0.00             │
│                                        │
│  ■ Joint Config  (type=JOINT일 때만)   │
│    axis    [ X ▾ ]                     │
│    min     [━●━━━━━] -3.14            │
│    max     [━━━━━●━]  3.14            │
├────────────────────────────────────────┤
│  [ Rebuild Preview ]     [ Apply ]     │
└────────────────────────────────────────┘
```

#### 핵심 동작

| 동작 | 설명 |
|---|---|
| **Target Node 선택** | 편집할 노드 범위를 좁힘. 범위 밖 오브젝트는 씬에서 반투명 처리 |
| **Add Child Node** | 타입(JOINT / LINK / PART / CAMERA) 선택 후 새 SceneNode 생성, 트리에 즉시 반영 |
| **Geometry 수정** | Shape 드롭다운 + 파라미터 입력 → `CADUtils` 호출로 메쉬 재생성 |
| **Transform 수정** | 부모 기준 상대 좌표 / 회전 직접 입력 |
| **Joint Config** | 회전축(x/y/z), 범위(min/max) → metadata 저장 → Inspector 탭 슬라이더에 자동 반영 |
| **Rebuild Preview** | 변경 내용을 씬에 즉시 반영 (기존 메쉬 교체) |
| **Apply** | 변경 내용을 SceneNode 트리에 확정 + 직렬화 가능 상태로 저장 |

#### 구현 파일

| 파일 | 역할 |
|---|---|
| `src/ui/BuilderPanel.ts` | Builder 탭 전체 컨트롤러 |
| `src/ui/NodeComposer.ts` | 자식 노드 추가/삭제 트리 |
| `src/ui/GeometryEditor.ts` | Shape 선택 + 파라미터 → `CADUtils` 연결 |
| `src/ui/TabManager.ts` | 3탭 전환 관리 |

---

## 작업 순서

```
Phase 1  코어 시스템 (A-1)
  1-1. SceneNode + NodeRegistry
  1-2. NodeFactory (geometry descriptor → THREE.Group)
  1-3. NodeAssembler (JSON → SceneNode 트리)

Phase 2  모델 정의 (A-2)
  2-1. vision_robot.json
  2-2. chamber.json
  2-3. conveyor.json / elbow.json

Phase 3  직렬화 (A-3)
  3-1. SceneSerializer / SceneDeserializer
  3-2. 프리셋 JSON 2종 (chamber_default, conveyor_line)

Phase 4  UI — Scene Graph + Inspector (B-1)
  4-1. TabManager + SceneGraphPanel
  4-2. PropertiesPanel (노드 metadata 기반 슬라이더 자동 생성)
  4-3. RaycastSelector (3D 클릭 → 노드 연동)
  4-4. PresetPanel (저장/불러오기)

Phase 5  UI — Builder (B-2)
  5-1. NodeComposer (자식 추가/삭제 트리)
  5-2. GeometryEditor (Shape 선택 + 파라미터)
  5-3. BuilderPanel 통합 + Rebuild Preview / Apply
```
