# data

3D 씬 데이터의 모델 정의, 파일 입출력, 에셋 캐시를 담당하는 순수 데이터 레이어임.

`graphics/`, `ui/`를 포함한 프로젝트 전 모듈이 이 레이어를 소비하며, `data/` 자체는 외부 모듈에 대한 의존이 없음 (단방향 흐름).

```
data/ ←── graphics/core/
      ←── graphics/viewport/
      ←── graphics/render/
      ←── ui/editor/
```

## 구조

```
data/
├── node/                    # 씬 그래프 노드 (트리 구조 데이터)
│   ├── stage.py             #   Stage_Controller — 트리 CRUD + JSON 직렬화 I/O
│   ├── type/
│   │   ├── base.py          #   Base_Node — Dirty Flag 기반 world_matrix 캐싱
│   │   ├── group.py         #   Group_Node — Xform/Stage 컨테이너
│   │   ├── mesh.py          #   Mesh_Node — Trimesh 인스턴스 보유 (얕은 복사)
│   │   └── camera.py        #   Camera_Node + Camera_Intrinsic
│   └── utils/
│       ├── transform.py     #   Build/Decompose_transform — Euler ↔ 4x4
│       └── traversal.py     #   walk_nodes — predicate 기반 제너레이터 순회
├── asset/                   # 파일에서 로드된 원시 데이터 (씬 그래프와 분리)
│   ├── cache.py             #   Asset_Cache — 타입별 분리 + deepcopy 반환
│   ├── type/
│   │   ├── base.py          #   Base_Asset
│   │   ├── mesh.py          #   Mesh_Asset (Trimesh)
│   │   └── point_cloud.py   #   PointCloud_Asset (points/colors/normals)
│   └── utils/
│       └── similarity.py    #   메시 유사도 (정확 비교, 표면 샘플링, ICP)
├── io/
│   ├── loader.py            # 확장자 라우팅 (load_as_asset / load_as_node)
│   └── obj.py               # OBJ → Mesh_Asset / Scene_Node 변환
└── register.py              # NODE_REGISTRY, ASSET_REGISTRY (python_toolbox.Registry)
```

## node/

씬 그래프의 핵심 데이터 구조임. USD Prim 스키마를 추종함.

### Base_Node 핵심 특성

- `PrimType` 리터럴 시스템: Stage, Xform, Mesh, Camera, Material, Shader, PhysicsScene, SkelRoot, Empty
- `local_matrix` (4x4 float32) 기반 계층 변환
- `world_matrix` 프로퍼티: **Dirty Flag 기반 캐싱**. `local_matrix`/`parent` 변경 시 `_Mark_dirty()`가 자손까지 전파되어 캐시를 무효화함
- `prim_path` 프로퍼티: `/Root/Child/...` 형태의 USD 호환 절대 경로
- `is_renderable` 프로퍼티: 부모 체인 visible 누적 검사
- `Serialize()`/`Clone()` 지원 (Base_Config 상속, `__custom_keys__`로 `local_matrix → local_matrix_meta` 키 매핑)

### 노드 타입 분화 (data/node/type/)

| 클래스 | prim_type | 추가 필드 |
|---|---|---|
| `Group_Node` | Xform / Stage | — |
| `Mesh_Node` | Mesh | `mesh: trimesh.Trimesh` (얕은 복사 인스턴싱) |
| `Camera_Node` | Camera | `intrinsic: Camera_Intrinsic` (width/height/fov/clip) |

각 타입은 `@NODE_REGISTRY.Register_module("…")`로 등록되어 `Stage_Controller.Load()`가 `prim_type` 문자열로부터 클래스를 역해석함.

### Stage_Controller

- 양방향 트리 무결성 관리: `Add_node`, `Move_node`, `Pop_node`, `Clear`
- `Add_node`는 컨테이너(Xform/Stage)를 받으면 자식만 평탄화 복제, 그 외에는 단일 클론을 추가
- `Save`/`Load`는 `python_toolbox.file.Utils`로 JSON 직렬화. `_Build_node`가 `NODE_REGISTRY` 조회 후 재귀 복원

### node/utils/

- `Build_transform(tx, ty, tz, rx, ry, rz)` — extrinsic XYZ Euler(°) → 4x4
- `Decompose_transform(matrix)` — 4x4 → (tx,ty,tz,rx,ry,rz), 짐벌락 근사 처리
- `walk_nodes(root, predicate)` — 제너레이터 기반 트리 순회 (중복 순회 코드 일원화)

## asset/

`node/`와 분리된 **순수 데이터 레이어**. 파일 1회 로드 → 캐시 → 씬 그래프에 인스턴스화하는 흐름의 중간 저장소임.

### Asset_Cache

- 내부 구조: `{ asset_type: { resolved_path: [Base_Asset, ...] } }` — 타입 버킷 분리로 `Get_by_type` 호출 시 전수 순회 회피
- `Get(file_path)`: 캐시 히트 시 **deepcopy** 반환 (원본 보호)
- `Get_all()`, `Get_by_type(asset_type)`: 원본 참조 반환 (브라우징 전용)
- `Register`, `Remove`, `Clear`

### asset/type/

| 클래스 | 보유 데이터 | 직렬화 제외 |
|---|---|---|
| `Base_Asset` | label, local_matrix, source_path | — |
| `Mesh_Asset` | `geometry: trimesh.Trimesh` | geometry |
| `PointCloud_Asset` | points/colors/normals (np.ndarray) | 전체 배열 |

### asset/utils/similarity.py

메시 형상 유사도 계측 독립 함수 모듈 (Mesh_Asset에 결합되지 않음).

| 함수 | 용도 |
|---|---|
| `Is_exact_match` | 정점/면 배열 정확 일치 (vertex count → bbox → 전수 비교 단계적 기각) |
| `Calculate_match_rate` | 동일 좌표계 전제. 표면 샘플링 → 양방향 거리 평균 |
| `Calculate_scan_match_rate` | 비정형 스캔 대응. 단위 정규화 → SVD 기반 ICP → 양방향 거리 max |

## io/

`loader.py`는 두 가지 진입점을 제공함:

- `load_as_asset(path) → list[Mesh_Asset]` — 순수 지오메트리 로드
- `load_as_node(path) → Base_Node` — 씬 트리 로드

각 진입점은 별도 디스패치 테이블(`_ASSET_LOADER`, `_NODE_LOADER`)을 보유함. 새 포맷 추가 시 파서 함수 작성 후 두 테이블에 등록함.

```python
_ASSET_LOADER = {".obj": load_obj_as_asset}
_NODE_LOADER  = {".obj": load_obj_as_node}
```

`obj.py`는 trimesh 그래프를 두 패스(Pass 1: 노드 인스턴스화, Pass 2: 부모-자식 링킹)로 평탄화하여 O(1) 부모 탐색을 보장함.

## register.py

`python_toolbox.project.Registry` 기반 전역 레지스트리.

```python
ASSET_REGISTRY = Registry[type[Base_Asset]]("Asset", Base_Asset)
NODE_REGISTRY  = Registry[type[Base_Node]]("Node",  Base_Node)
```

각 노드/에셋 타입 모듈은 import 시점에 `@NODE_REGISTRY.Register_module("Mesh")` 데코레이터로 자기 자신을 등록함.
