# ROADMAP

## 현재 상태

- Three.js + TypeScript + Vite 기반 3D 씬 에디터 기본 동작
- 노드 타입: GROUP / JOINT / LINK
- JOINT가 동역학 관절과 정적 마운트 포인트를 겸용 → 시맨틱 혼재
- JOINT에 배열 layout이 있으나 GROUP에 있어야 적절함
- Builder 탭이 에셋 생성과 씬 편집을 혼재
- 씬에 모델 추가 시 native `prompt()` 사용

---

## 목표 상태

- 노드 타입 4종으로 시맨틱 명확화
- ANCHOR 기반 배열 배치 및 무작위 transform 변이 지원
- Asset Editor를 별도 탭(새 브라우저 탭)으로 분리
- 메인 패널은 씬 조작과 ANCHOR 편집에 집중

---

## 노드 타입 정의

| 타입 | 역할 | 주요 속성 |
|------|------|-----------|
| **GROUP** | 모델 루트 컨테이너 | transform |
| **ANCHOR** | 부착 지점 + 배열 레이아웃 | transform, layout |
| **JOINT** | 순수 동역학 관절 | transform, axis, min, max |
| **LINK** | 강체 지오메트리 | transform, geometry |

### ANCHOR layout 스키마

```jsonc
"layout": {
  "kind": "single" | "array",

  // array 전용
  "count": 6,
  "gap": 4.0,
  "axis": "x" | "y" | "z",

  // 슬롯에 기본 배치될 모델
  "defaultModel": "elbow",

  // 무작위 변이 설정
  "randomize": {
    "components": ["ry"],              // 변이 적용 성분
    "ranges": { "ry": [-3.14, 3.14] } // 성분별 범위
  },

  // 슬롯 개별 override (index → 설정)
  "slots": {
    "2": { "model": "camera_3lens", "transform": { "rotation": [0, 0, 0] } },
    "5": { "locked": true }
  }
}
```

**transform 계층 (array 슬롯 기준):**
```
ANCHOR 노드 transform       (부모 공간 내 앵커 위치)
  + index * gap * axis      (배열 기준 슬롯 offset)
  + slots[i].transform      (슬롯 개별 override)
  + randomize 변이           (locked=true 슬롯 제외)
```

**populate 흐름:**
- 씬에 모델 최초 추가 시 → defaultModel + randomize로 slots 자동 생성 → 씬 snapshot에 SceneEntry로 저장
- 이후 씬 로드 시 → snapshot의 SceneEntry를 그대로 읽음 (재계산 없음)
- Re-randomize 버튼 → locked 슬롯 제외하고 재생성 → snapshot 덮어씀

---

## 씬 구조 원칙

씬 루트는 평면 리스트. ANCHOR는 모델 내부에만 존재.

```
Scene Root
├── chamber_0  (GROUP)
│   ├── LINK (frame)
│   ├── ANCHOR (ceiling, kind=single) ← 로봇 부착
│   └── ANCHOR (floor,   kind=single) ← 장비 부착
└── conveyor_0 (GROUP)
    ├── LINK (body)
    └── ANCHOR (surface, kind=array, defaultModel="elbow")
```

---

## UI 구조

```
우측 패널
├── SCENE 탭
│   ├── SceneGraphPanel   — 씬 트리 탐색 (GROUP/ANCHOR/JOINT/LINK 배지 구분)
│   ├── Save / Load Scene
│   └── InstancePanel     — 선택 노드 편집
│         GROUP  : transform 슬라이더
│         ANCHOR : transform + 슬롯 에디터 (모델 교체, Re-randomize)
│         JOINT  : 각도 슬라이더 (axis / range 표시)
│         LINK   : transform + geometry 치수 조정
│
└── BUILDER 탭 (간소화)
      씬에 배치된 모델에 ANCHOR 추가 / 편집
      ANCHOR layout 설정 (kind / count / gap / defaultModel / randomize)
      복잡한 에셋 조합은 Asset Editor 탭으로 위임

별도 브라우저 탭 — Asset Editor
├── NodeComposer   — 노드 트리 편집 (GROUP / ANCHOR / JOINT / LINK)
├── GeometryEditor — shape / color / dimensions / joint config
├── Save / Load Asset JSON
└── BroadcastChannel → 메인 씬의 AssetManager에 등록
```

---

## 구현 계획

### Phase 1 — 타입 / 스키마 ✅

- [x] `SceneNode.ts`: `NodeType`에 `ANCHOR` 추가
- [x] `NodeAssembler.ts`: `AnchorLayout` 인터페이스 정의, `NodeDescriptor`의 `layout` 필드를 ANCHOR 전용으로 이동, JOINT에서 `layout` 제거
- [x] `NodeFactory.ts`: ANCHOR 타입 처리, `LayoutDescriptor` → `AnchorLayout` 교체
- [x] `GeometryEditor.ts`: `_renderJoint` 에서 layout 분리 → `_renderAnchor` 신규, JOINT는 kinematic만
- [x] `SceneGraphPanel.ts` / `NodeComposer.ts`: `badge-ANCHOR` 배지 추가
- [x] `panel.css`: `badge-GROUP`, `badge-ANCHOR` 클래스 추가 (기존 누락 버그 픽스 포함)

### Phase 2 — AnchorPopulator ✅

- [x] `core/AnchorPopulator.ts` 신규 작성
  - `populate(anchor, modelLoader)` → 기존 자식 전부 제거 후 slots 재생성
  - `repopulate(anchor, modelLoader)` → `_slotIndex` + `slots[i].locked` 기준으로 locked 슬롯 보존, 나머지 재생성
  - randomize 로직: components 목록 기준 각 성분에 range 내 균등 난수 적용
  - 슬롯 자식에 `_slotIndex`, `_modelName` metadata 저장

### Phase 3 — Serializer / Deserializer ✅

- [x] `SceneDeserializer.ts`: `_loadEntry` 완료 후 `_autoPopulateAnchors` 호출 — 자식 없고 `defaultModel` 있는 ANCHOR 자동 populate. 다른 모델 루트 경계는 탐색하지 않음.
- [x] `SceneSerializer.ts`: 변경 없음 — `traverseForChildren`이 이미 ANCHOR 자식을 `attachTo=anchorId`로 올바르게 직렬화함.
- [x] `BuilderPanel.ts`: `applyDraftToNode` 및 `_serializeGroup`에서 JOINT layout → ANCHOR layout으로 정정

### Phase 4 — Asset Editor (새 탭) ✅

- [x] `vite.config.ts` multi-page 설정 (main + assetEditor 엔트리)
- [x] `asset-editor.html` + `src/asset-editor.ts` Vite 엔트리 추가
- [x] `src/core/NodeDescriptorExporter.ts` 신규 — SceneNode 트리 → NodeDescriptor 직렬화
- [x] `src/ui/AssetEditorApp.ts` 신규 — Three.js 프리뷰 + NodeComposer + GeometryEditor + 파일 I/O
- [x] `src/ui/asset-editor.css` 신규 — Asset Editor 전용 스타일
- [x] `NodeComposer.ts`: ANCHOR 타입 추가, JOINT 초기화 수정 (axis/min/max), ANCHOR 초기화 추가
- [x] `BroadcastChannel` 송신: Send to Scene 시 `{ type: 'ASSET_SAVED', name, descriptor }` 전송
- [x] `SceneEditorApp.ts`: BroadcastChannel 수신 → `AssetManager.registerModel()` + 토스트 알림
- [x] `TabManager.ts`: 탭 바에 "✦ ASSET" 버튼 추가 → `window.open('/asset-editor.html', '_blank')`

### Phase 5 — 메인 패널 개편 ✅

- [x] `ui/InstancePanel.ts` 신규 (PropertiesPanel 대체)
  - ANCHOR (single): transform 슬라이더 + 모델 attach/detach UI
  - ANCHOR (array): transform + 슬롯 리스트 (모델 교체 드롭다운, lock 토글) + Re-randomize 버튼
  - JOINT: 각도 슬라이더 (axis/range 힌트 표시)
  - GROUP / LINK: transform 슬라이더
- [x] `ui/BuilderPanel.ts` 간소화
  - 선택된 GROUP 노드에 ANCHOR 추가 기능
  - ANCHOR layout 편집 (kind / count / gap / defaultModel / randomize 설정)
  - NodeComposer / GeometryEditor 제거 (Asset Editor로 이전)
- [x] `SceneEditorApp.ts`: PropertiesPanel → InstancePanel 교체, onAddToJoint 제거, BuilderPanel에 assetManager 전달
- [x] `ui/SceneGraphPanel.ts`: JOINT의 "+" 버튼 제거, ANCHOR 노드 트리에 표시
- [x] `ui/TabManager.ts`: BUILDER 탭 유지, Asset Editor 탭 열기 버튼 추가
- [x] CSS: `badge-GROUP`, `badge-ANCHOR` 추가

### Phase 6 — JSON 파일 수정 ✅

- [x] `models/passive/chamber.json`: `ceiling`, `floor` → `JOINT` to `ANCHOR`
- [x] `models/passive/conveyor.json`: `surface` → `JOINT` to `ANCHOR`, `kind: array`, `defaultModel: "elbow"`, `randomize: { ry: [-π, π] }` 추가, anchor 위치 중앙 정렬 (-4, 4.72, 0)
- [x] `presets/chamber_default.json`: 변경 없음 (SceneEntry 구조 유지)
- [x] `presets/conveyor_line.json`: 변경 없음
- [x] `ui/InstancePanel.ts`: ANCHOR single 뷰에서 `_modelName` 있는 자식만 attached model로 인식 (구조적 LINK 자식 무시)

---

## 버그 픽스 ✅

- [x] `badge-GROUP` CSS 클래스 누락
- [x] `tree-remove-btn` CSS 클래스 누락 — `.tree-remove-btn` / `:hover` 추가
- [x] `RaycastSelector.dispose()` bind 버그 — `_boundOnClick` 필드로 bound fn 보관
- [x] 패널 가로 리사이즈 시 renderer 미동기화 — `w()` 가 DOM에서 실제 패널 폭 읽도록 변경 + `ResizeObserver` 로 드래그 리사이즈도 감지
