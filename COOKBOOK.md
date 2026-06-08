# PLAN Cookbook

PLAN 코드베이스의 핵심 개념과 자주 쓰이는 패턴을 정리한 레퍼런스다.

---

## 1. 노드 타입과 역할

모든 씬 오브젝트는 `SceneNode`이며, 네 가지 `NodeType`으로 구분된다.

| 타입 | 역할 | Scene Tree 표시 |
|------|------|----------------|
| `GROUP` | 모델 인스턴스의 루트 컨테이너 | 표시 |
| `ANCHOR` | 다른 모델이 붙는 연결 지점 | 표시 (exposed=true일 때) |
| `JOINT` | 로봇 관절 (회전 가능) | **비표시** — 내부 구현 |
| `LINK` | 관절 간 강체 링크 | **비표시** — 내부 구현 |

> **설계 원칙**: Scene Graph 패널은 "무엇이 어디에 붙어 있는가"를 관리하는 공간이다.
> JOINT/LINK는 모델 내부 구조이며 씬 레벨에서 편집 대상이 아니므로 트리에 노출하지 않는다.
> JOINT 각도 조작은 Raycast 선택 → Inspector 슬라이더 경로로 처리한다.

---

## 2. 핵심 데이터 흐름

```
NodeDescriptor (JSON)
    │
    ▼ NodeAssembler.materializeInstance()
SceneNode 트리 (런타임 메모리)
    │
    ├─▶ NodeRegistry (id → SceneNode 전역 맵)
    │
    ▼ SceneSerializer.serialize()
SceneSnapshot (저장/복원용 JSON)
    │
    ▼ SceneDeserializer.load()
SceneNode 트리 (복원)
```

---

## 3. NodeDescriptor — 에셋 정의 형식

```jsonc
{
  "id": "robot_arm",
  "type": "GROUP",
  "label": "Robot Arm",

  // 인스턴스마다 달라지는 파라미터 스키마
  "parameters": {
    "reach": { "type": "number", "default": 1.0, "min": 0.5, "max": 2.0, "unit": "m" }
  },

  // 파라미터로부터 파생되는 계산값
  "computed": {
    "halfReach": "reach * 0.5"
  },

  // 반복 사용되는 하위 구조를 이름으로 정의
  "definitions": {
    "link_body": { "id": "link_body", "type": "LINK", "geometry": { "shape": "JointCapsule", ... } }
  },

  "children": [
    {
      "id": "robot_arm.j1",
      "type": "JOINT",
      "metadata": { "axis": "y", "min": -3.14, "max": 3.14 },
      "children": [
        "link_body",             // definitions 참조
        {
          "id": "robot_arm.anchor_ee",
          "type": "ANCHOR",
          "layout": { "kind": "single", "exposed": true }
        }
      ]
    }
  ]
}
```

### 파라미터 참조 문법

- `"$params.reach"` — 인스턴스 파라미터 참조
- `"$computed.halfReach"` — computed 값 참조
- transform, geometry, layout의 모든 숫자/문자열 필드에 사용 가능

---

## 4. NodeAssembler — 인스턴스 조립

### 4-1. 새 인스턴스 생성

```typescript
const descriptor = assetManager.getModel('robot_arm');
const root = NodeAssembler.materializeInstance(
    descriptor,
    'robot_arm_1',          // instanceId — 전역 유일해야 함
    {
        modelName: 'robot_arm',     // SceneSerializer가 역직렬화에 사용
        state: {
            params: { reach: 1.5 },
        },
    },
);
// root.metadata._modelName === 'robot_arm'
// root.id === 'robot_arm_1'
// 내부 노드 id는 'robot_arm_1.j1', 'robot_arm_1.anchor_ee' 등으로 remapping
```

### 4-2. 파라미터 변경 후 리빌드

파라미터를 바꾸면 전체 노드 트리를 재조립해야 한다.

```typescript
const nextRoot = NodeAssembler.rebuildInstance(
    currentRoot,    // 교체할 기존 SceneNode
    descriptor,
    { params: { reach: 2.0 } },
);
// 기존 root는 NodeRegistry에서 자동 해제되고 새 root가 같은 위치에 삽입됨
// 부착된 자식 인스턴스(attached models)는 자동으로 재연결됨
```

### 4-3. 인스턴스 상태 읽기/쓰기

```typescript
// 읽기
const state = NodeAssembler.readInstanceState(root);
// { params: { reach: 1.5 }, anchorOverrides: { ... } }

// 부분 업데이트 (merge)
const next = NodeAssembler.updateInstanceState(root, {
    params: { reach: 2.0 },       // 기존 params에 merge
});
```

---

## 5. NodeRegistry — 전역 노드 맵

모든 `SceneNode`는 생성 시 자동 등록되며, id로 O(1) 조회가 가능하다.

```typescript
NodeRegistry.get('robot_arm_1.j1')    // SceneNode | undefined
NodeRegistry.has('robot_arm_1')       // boolean
NodeRegistry.unregister(node)         // 단일 해제
for (const n of node.flatten()) NodeRegistry.unregister(n)  // 서브트리 일괄 해제
NodeRegistry.clear()                  // 씬 전체 초기화 (씬 로드 전 호출)
```

> **주의**: id가 중복되면 `register`에서 즉시 throw. `nextInstanceId(seed)` 헬퍼로 유일한 id를 생성할 것.

---

## 6. Anchor 시스템

### 6-1. AnchorLayout 종류

```typescript
// single: 자식 하나만 붙을 수 있는 단일 슬롯
{ kind: 'single', exposed: true }

// array: 동일 간격으로 여러 슬롯 (컨베이어 위 팔레트 배열 등)
{
    kind: 'array',
    count: 5,
    gap: 2.0,
    start: 0,
    axis: 'x',
    exposed: true,
    defaultModel: 'pallet',   // 슬롯 자동 populate용
}
```

### 6-2. exposed 속성

- `exposed: true` (기본값) — Scene Graph 패널에 표시, 사용자가 직접 attach/detach 가능
- `exposed: false` — 내부 anchor, UI에 미표시 (예: 컨베이어 다리 배열)

### 6-3. 자동 populate

`AnchorPopulator.populate(anchor, modelLoader)` — 자식이 없고 `defaultModel` 또는 `defaultNode`가 있는 ANCHOR에 자동으로 인스턴스를 생성해 붙인다. `SceneDeserializer.load()` 완료 후 자동 호출된다.

### 6-4. Anchor에 인스턴스 부착 (SceneEditorApp 기준)

```typescript
// single anchor
const child = NodeAssembler.materializeInstance(descriptor, instanceId, { modelName });
child.metadata['_slotIndex'] = 0;
anchor.addChild(child);

// array anchor — 슬롯 위치 계산 필요
applyAnchorSlotTransform(anchor, child, slotIndex);
child.metadata['_slotIndex'] = slotIndex;
anchor.addChild(child);
```

---

## 7. SceneSerializer / SceneDeserializer

### 직렬화 출력 형식 (SceneSnapshot)

```jsonc
{
  "version": 1,
  "scene": [
    {
      "model": "robot_arm",
      "instanceId": "robot_arm_1",
      "transform": { "position": [0, 0, 0], "rotation": [0, 0, 0] },
      "params": { "reach": 1.5 },
      "anchorOverrides": {
        "robot_arm_1.anchor_ee": { "layout": { "kind": "single" } }
      },
      "overrides": {
        "robot_arm_1.j1": { "rotation": [0, 0.785, 0] }   // JOINT 각도 변경분
      },
      "children": [
        // 이 인스턴스의 anchor에 붙은 자식 모델들
        {
          "model": "gripper",
          "instanceId": "gripper_1",
          "attachTo": "robot_arm_1.anchor_ee",
          ...
        }
      ]
    }
  ]
}
```

### 직렬화 규칙

- `params`: schema 기본값과 다른 경우에도 모두 기록 (복원 시 asset이 바뀌어도 안전)
- `overrides`: JOINT 회전이 `_defaultRotation`에서 `1e-6` 이상 차이날 때만 기록
- `children`: DFS로 만나는 `_modelName` 노드를 `attachTo: parentNode.id`와 함께 기록

---

## 8. SceneGraphPanel — 트리 가시성 규칙

### 무엇이 보이는가

```
sceneRoot (GROUP, 비표시)
  ├── robot_1 (GROUP, _modelName) ← render()가 직접 열거
  │     └── anchor_ee (ANCHOR, exposed=true) ← _getVisibleChildren(GROUP)
  │           └── gripper_1 (GROUP, _modelName) ← _getVisibleChildren(ANCHOR)
  │                 └── anchor_tool (ANCHOR, exposed=true)
  └── conveyor_1 (GROUP, _modelName)
        └── ... (exposed anchors only)
```

### `_getVisibleChildren` 로직 요약

```typescript
// GROUP: JOINT/LINK를 투명하게 통과, 노출된 ANCHOR만 수집
if (node.type === NodeType.GROUP) {
    traverse(node); // JOINT, LINK는 skip, ANCHOR(exposed)만 push
}

// ANCHOR (single): 부착된 모델 인스턴스(_modelName)만 반환
if (node.type === NodeType.ANCHOR && layout.kind !== 'array') {
    return children.filter(c => c._modelName !== undefined);
}

// ANCHOR (array): 자식 없음 — 슬롯은 _buildSlotRows()가 별도 렌더
if (layout.kind === 'array') return [];

// JOINT/LINK: 항상 [] — 트리에 표시하지 않음
```

### highlight() — Raycast 선택 처리

JOINT/LINK를 Raycast로 클릭하면 트리에 표시되지 않으므로, `_nearestTreeNode()`가 가장 가까운 GROUP 또는 ANCHOR 조상으로 대체해 하이라이트한다.

---

## 9. 자주 쓰는 패턴

### 노드 삭제

```typescript
// NodeRegistry 해제 → SceneNode 트리에서 분리 → Three.js object3D도 자동 분리
for (const n of node.flatten()) NodeRegistry.unregister(n);
node.parent?.removeChild(node);
```

### 인스턴스 루트 찾기

```typescript
// 임의 노드에서 올라가며 _modelName을 가진 GROUP을 찾는다
let cur: SceneNode | null = node;
while (cur) {
    if (cur.metadata['_modelName'] !== undefined) return cur; // 인스턴스 루트
    cur = cur.parent;
}
```

### 씬 전체 루트 찾기

```typescript
let cur = node;
while (cur.parent) cur = cur.parent;
return cur; // sceneRoot
```

### SceneEditorApp에서 패널 동기화

```typescript
private refreshPanels(): void {
    this.graphPanel.render([this.sceneRoot]);
    this.sceneActionPanel.setRoot(this.sceneRoot);
    this.builderPanel.setSceneRoot(this.sceneRoot);
}
```

모든 씬 변경(추가/삭제/attach/detach/reparent) 후 `refreshPanels()`를 호출한다.

---

## 10. 알려진 주의사항

| 상황 | 주의 |
|------|------|
| `NodeRegistry.register()` | id 중복 시 즉시 throw — 인스턴스 생성 전 `nextInstanceId()` 사용 |
| `rebuildInstance()` | 기존 root는 해제되므로 저장된 참조가 있으면 갱신 필요 |
| `onAttachToAnchor` 콜백 | `slotIndex` 파라미터 전달 누락 주의 (array anchor 오작동 원인) |
| `onClearAnchor` 콜백 | 동일하게 `slotIndex` 전달 필수 |
| ANCHOR `exposed: false` | `_getVisibleChildren`에서 수집되지 않으므로 Scene Tree에 미노출 — 의도된 동작 |
| `_ensureVisible()` | JOINT/LINK 조상은 DOM row 없음 → querySelector null 안전 처리됨 |
