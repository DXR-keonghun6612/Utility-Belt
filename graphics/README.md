# graphics

3D 시각화와 렌더링을 담당하는 도메인. `data/` 레이어의 소비자이며, UI(`ui/editor/`)에 시각 출력을 제공함.

## 의존 방향

```
data/  ←──  graphics/core/     (드로우, 리소스, 패스 정의)
       ←──  graphics/viewport/  (편집기 실시간 뷰포트, core 사용)
       ←──  graphics/render/    (오프라인 데이터셋 생성, core 사용)
                  ↑
              ui/editor/        (graphics의 최상위 소비자)
```

순환 참조 없음. UI는 `graphics/` 외부(`ui/`)에 위치하며, graphics는 UI를 참조하지 않음.

## 구조

```
graphics/
├── core/                      # 드로우/리소스/패스 정의 (viewport와 render의 공통 의존)
│   ├── draw.py                #   Draw_mesh — VBO 우선, 클라이언트 배열 폴백
│   ├── resource.py            #   GPU_Resource_Manager — 메시 → VBO 캐시
│   └── pass_/
│       ├── base.py            #     Base_Pass (ABC, Template Method)
│       ├── registry.py        #     Pass_Registry
│       ├── build.py           #     Get_render(name) — 패스 인스턴스 팩토리
│       ├── rgb.py             #     Phong 조명 RGB
│       ├── depth.py           #     선형 미터 단위 뎁스
│       ├── normal.py          #     로컬 법선 RGB 인코딩
│       └── segmentation.py    #     인스턴스 ID RGB 인코딩
├── viewport/                  # 편집기 실시간 뷰포트 (→ viewport/README.md)
│   ├── renderer.py
│   ├── view.py
│   ├── transform.py
│   └── tool/
└── render/                    # 데이터셋 오프라인 생성 (→ render/README.md)
    ├── config.py
    ├── pipeline.py
    └── exporter.py
```

> **참고**: 편집기 UI는 프로젝트 루트의 `ui/editor/` 패키지에 위치함. 과거에는 `graphics/ui/`에 있었으나 도메인 분리 리팩토링으로 이관됨.

## core/

`viewport/`와 `render/` 양쪽에서 사용하는 OpenGL 코어 및 렌더 패스 구현체를 보유함.

### draw.py — Draw_mesh

| 모드 | 트리거 | 특성 |
|---|---|---|
| VBO 경로 | `res_manager` 인자 전달 시 | `GPU_Resource_Manager.Sync_mesh()`로 캐시된 VBO 사용 |
| 클라이언트 배열 폴백 | `res_manager=None` | trimesh 배열을 매 프레임 직접 전달 |

### resource.py — GPU_Resource_Manager

`id(mesh)` 키 기반 VBO 캐시. 정점/법선/인덱스 + Normal Pass 전용 색상 VBO(`(n+1)*127.5`)를 함께 업로드하여 `Normal_Pass`가 추가 변환 없이 재사용함. `Clear()`로 일괄 해제.

### core/pass_/

오프라인 렌더 패스 구현체와 추상 베이스. **이전에는 `graphics/render/pass_/`에 있었으나 viewport에서도 재사용 가능하도록 core로 이관됨.**

`Base_Pass`는 Template Method 패턴으로 공통 흐름을 고정하고, 서브클래스는 다음 훅만 오버라이드함:

- `_On_setup()` — GL 상태 설정 (조명/디더 등)
- `_On_draw(root)` — 씬 드로우 (기본: `_Draw_scene` 재귀)
- `_On_readback(w, h, **kw)` — `glReadPixels` (필수 구현)
- `_On_cleanup()` — 상태 복구

공통 헬퍼: `_Apply_camera`(intrinsic→glPerspective + world_matrix 역행렬→ModelView), `_Read_rgb`, `_Read_depth`. 패스 등록은 `@Pass_Registry.Register_module("name")` 데코레이터로 수행하며, `Get_render(name)`이 인스턴스를 반환함.

상세 패스 사양은 `graphics/render/README.md` 참조.

## viewport/ vs render/

| 항목 | viewport/ | render/ |
|---|---|---|
| 컨텍스트 | 호스트(Qt) 위젯 컨텍스트 | EGL 우선, Qt 폴백 헤드리스 FBO |
| 사용처 | 편집기 실시간 미리보기 | `capture_cli.py` 데이터셋 생성 |
| 카메라 | `Orbit_Camera` (편집기 전용) | `Camera_Node`(intrinsic 보유) |
| 패스 사용 | 자체 메인 패스 + ID 패스 | `core/pass_/` 패스 시퀀스 |
