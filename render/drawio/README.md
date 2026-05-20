# render/drawio — Draw.io 백엔드 가이드

`04_layout`이 부여한 추상 좌표(`layer / wing / col`)를 Draw.io의 픽셀 좌표와
`mxCell` XML로 변환하는 백엔드의 구현 규칙.

상위 설계는 [`METHODOLOGY.md`](../../METHODOLOGY.md) 참고.

---

## 1. 역할

| 입력 | `04_layout` 출력 (`Positioned_Graph`) |
|------|-------------------------------------|
| 출력 | `.drawio` XML (디렉토리당 1개) |
| 책임 | 추상 좌표 → 픽셀 변환 / 노드 크기 계산 / 엣지 스타일 매핑 |
| 위임 | 엣지 라우팅(자동) → `edgeStyle=orthogonalEdgeStyle` |

---

## 2. 추상 좌표 → 픽셀 변환

```
픽셀_x = WING_OFFSET[wing] + col × COL_STEP
픽셀_y = layer × LAYER_STEP
```

| 상수 | 기본값 | 비고 |
|------|--------|------|
| `WING_OFFSET[left]` | 40 | 외부 stub 영역 |
| `WING_OFFSET[center]` | 500 | 본류 영역 |
| `WING_OFFSET[right]` | 2000 | macro / registry 영역 |
| `COL_STEP` | 450 | 같은 layer 내 가로 간격 |
| `LAYER_STEP` | 350 | layer 간 세로 간격 |

값은 `style.py`의 모듈 상수로 노출 — 튜닝 가능.

---

## 3. 클래스 박스 (swimlane 패턴)

```xml
<!-- 클래스 헤더 -->
<mxCell id="N" value="ClassName"
  style="swimlane;fontStyle=1;startSize=26;childLayout=stackLayout;..." />

<!-- 구분선 -->
<mxCell style="line;..." parent="N">
  <mxGeometry y="{startSize}" width="{W}" height="8"/>
</mxCell>

<!-- 필드/메서드 행 -->
<mxCell value="+ methodName(params): ReturnType"
  style="text;...portConstraint=eastwest;..." parent="N">
  <mxGeometry y="{startSize + 8 + n*26}" width="{W}" height="26"/>
</mxCell>
```

### 3.1 노드 크기 계산

```
height = startSize + 8 + (멤버 수 × ROW_HEIGHT)
width  = DEFAULT_WIDTH         # 고정 (현재 350)
```

| 상수 | 기본값 |
|------|--------|
| `DEFAULT_WIDTH` | 350 |
| `ROW_HEIGHT` | 26 |
| `HEADER_HEIGHT` | 40 (스테레오타입 없을 때) |
| `STEREOTYPE_HEADER` | 60 (스테레오타입 있을 때) |

---

## 4. 엣지 스타일 매핑

[`METHODOLOGY.md` §4.3](../../METHODOLOGY.md)의 엣지 종류와 1:1 매핑.

| 엣지 (`edge_type`) | 화살표 끝 | 채움 | 점선 | UML 표기 |
|--------------------|----------|------|------|----------|
| `inheritance` | `block` | `0` (hollow) | `0` | hollow triangle (실선) |
| `realization` | `block` | `0` (hollow) | `1` | hollow triangle (점선) |
| `composition` | `diamondThin` | `1` (filled) | `0` | filled diamond |
| `aggregation` | `diamondThin` | `0` (hollow) | `0` | hollow diamond |
| `association` | `open` | `0` | `0` | 실선 (단방향 화살표) |
| `dependency` | `open` | `0` | `1` | dashed open arrow |
| `include` | `open` | `0` | `1` (회색) | dashed open arrow (회색) |

### 4.1 다중 엣지 시각화 우선순위

같은 노드쌍에 여러 엣지가 있으면 다음 순서로 한 개만 표시(기본):

```
inheritance > realization > composition > aggregation > association > dependency > include
```

전체 표시는 `--show-all-edges` 옵션(예정)으로 제어.

---

## 5. 스테레오타입 시각화 (Type 카테고리에만 적용)

[`METHODOLOGY.md` §4.2](../../METHODOLOGY.md)의 `abstraction` × `traits`를 직교 채널에 매핑.

| 분류값 | 시각 채널 | drawio 표현 |
|--------|----------|-------------|
| `abstraction == interface` | swimlane 헤더 크기 | `startSize=40` + 헤더에 `«interface»` 텍스트 |
| `abstraction == abstract` | 폰트 스타일 | 클래스명에 `fontStyle=2` (이탤릭) |
| `abstraction == concrete` | — | 마커 표시 안 함 (UML 관례) |
| `traits ∋ template` | 클래스명 텍스트 | `ClassName<T, Args...>` |
| `traits ∋ macro` | 배경 색상 | `fillColor=#dae8fc` (연한 파랑) |
| `traits ∋ data` | 배경 색상 | `fillColor=#fff2cc` (연한 노랑) |

직교 채널이므로 동시 적용 가능. 예: `{abstraction=interface, traits={template}}` →
`startSize=40` + 헤더에 `«interface»` + 클래스명에 `<T>`.

---

## 6. 외부 클래스 시각화 (`origin == external`)

| 처리 옵션 | 동작 |
|-----------|------|
| 기본 | 회색 흐림 (`strokeColor=#bbbbbb`, `fontColor=#777777`, 반투명 fill) + 좌측 wing 배치 |
| `--hide-external` | 노드/엣지 전부 숨김 |

stub 노드는 메서드/속성이 비어있으므로 헤더만 그려짐.

---

## 7. namespace 그룹화

`04_layout`의 `namespace_groups`를 받아 swimlane 컨테이너로 감쌈:

```xml
<mxCell value="«namespace» core" style="swimlane;startSize=20;..." />
```

같은 namespace 내 노드들은 이 컨테이너의 자식으로 배치.
컨테이너의 위치/크기는 자식 노드 좌표의 bounding box.

---

## 8. 생성 흐름 요약

```
입력:  Positioned_Graph (04_layout)
       │
       ▼
  ┌────────────────────────────────────┐
  │  1. 노드별 크기 계산 (멤버 수 기반)  │
  │  2. (layer, wing, col) → (x, y)    │
  │  3. namespace 컨테이너 생성         │
  │  4. swimlane + 자식 cells 생성      │
  │  5. 엣지 cells 생성 (스타일 매핑)    │
  │  6. mxGraphModel XML 직렬화         │
  └────────────────────────────────────┘
       │
       ▼
출력:  {dir}.drawio
```

---

## 9. 참고: 좌표/스타일 상수 위치

- 픽셀 변환 상수: `render/drawio/style.py` (예정)
- swimlane 스타일 빌더: `render/drawio/style.py::get_swimlane_style`
- 엣지 스타일 빌더: `render/drawio/style.py::get_edge_style`
- XML 직렬화: `render/drawio/builder.py` (예정)

(현재 `core/form/drawio/`에 있는 기존 구현은 점진적으로 본 위치로 이전 예정.)
