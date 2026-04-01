# data

3D 씬 데이터의 모델 정의, 파일 입출력, 캐시 관리를 담당하는 순수 데이터 레이어.

`graphics/`를 포함한 프로젝트 내 모든 모듈이 이 레이어를 소비하며, `data/` 자체는 외부 모듈에 대한 의존이 없음 (단방향 흐름).

```
data/ ←── graphics/viewport/
      ←── graphics/render/
      ←── graphics/ui/
```

## 구조

```
data/
├── scene/
│   ├── node.py       # Scene_Node — USD Prim 기반 씬 그래프 노드 (dataclass)
│   └── stage.py      # Stage_Controller — 씬 트리 CRUD 및 양방향 참조 관리
├── model/
│   └── camera.py     # Camera_Intrinsic — 물리 카메라 광학 파라미터 (Base_Config 상속)
├── io/
│   ├── loader.py     # 확장자 기반 파서 라우팅 (load_file)
│   └── obj.py        # OBJ 포맷 파서 (trimesh → Scene_Node 트리 변환)
└── registry.py       # Asset_Registry — 경로 기반 에셋 캐시 (Clone 반환으로 원본 보호)
```

## scene/

`Scene_Node`는 프로젝트 전체의 핵심 데이터 구조임.

- USD의 Prim 스키마를 추종하는 `PrimType` 타입 시스템 (Stage, Xform, Mesh, Camera 등)
- `local_matrix` (4x4 float32) 기반 계층적 변환
- `world_matrix` 프로퍼티: 루트까지 누적 행렬을 재귀 계산하여 반환
- `prim_path` 프로퍼티: USD 호환 절대 네임스페이스 경로 (`/Root/Child/...`)
- `mesh` 필드: Trimesh 지오메트리 데이터 (얕은 복사로 인스턴싱)
- `intrinsic` 필드: Camera 노드 전용 광학 파라미터 (`Camera_Intrinsic`)

`Stage_Controller`는 씬 트리의 상태 무결성을 관리함 (노드 추가/이동/분리/초기화).

## model/

`Camera_Intrinsic`은 `Base_Config`를 상속하여 직렬화(`Serialize`) 및 파일 저장(`Write_to`)을 지원함.

| 필드 | 기본값 | 용도 |
|---|---|---|
| `fov` | 60.0 | 수직 화각 (degrees) — OpenGL 투영에 사용 |
| `near_clip` / `far_clip` | 0.1 / 1000.0 | 클리핑 평면 |
| `focal_length` | 50.0 | mm 단위 — 메타데이터 기록용 |
| `sensor_width` / `sensor_height` | 36.0 / 24.0 | mm 단위 — 메타데이터 기록용 |

## io/

`loader.py`는 확장자 → 파서 함수 매핑 딕셔너리(`_LOADER_REGISTRY`)를 통해 라우팅함. 새 포맷 추가 시 파서 함수를 작성하고 딕셔너리에 등록하면 됨.

```python
# 확장 예시
_LOADER_REGISTRY = {
    ".obj": load_obj,
    # ".gltf": load_gltf,
}
```

## registry.py

`Asset_Registry.Get(path)`는 캐시 히트 시 I/O 없이 `Clone()`을 반환하고, 캐시 미스 시 `load_file`을 호출하여 등록 후 복제본을 반환함. 원본 데이터는 레지스트리 내부에서만 보유됨.
