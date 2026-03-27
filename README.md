# 3D 객체 시뮬레이션

목표: 3D 가상 시뮬레이션 환경을 구축하고, 해당 환경에서 알고리즘의 사전 검증, 로봇 학습 등을 진행.

## 진행 사항

- [ ] 정적 편집기
  - [x] 기본 구조 (데이터 입출력 (*.obj), 공간상에 배치, pose 정보 수정 등)
  - [ ] 편집 결과 저장 및 읽기 -> *.usd 포멧


## 환경

### 공통 기술 스택

- 사용 언어: Python( >=3.11 )
- UI : PySide6

### 구조

```txt
sim
├─ README.md
├─ app.py
├─ asset
│  ├─ io
│  │  ├─ loader.py
│  │  └─ obj.py
│  └─ registry.py
├─ scene
│  ├─ node.py
│  └─ stage.py
├─ test.py
├─ ui
│  ├─ panels
│  │  ├─ asset
│  │  │  └─ browser.py
│  │  ├─ engine.py
│  │  └─ scene
│  │     ├─ page.py
│  │     ├─ property.py
│  │     └─ scene_tree.py
│  ├─ sidebar.py
│  └─ viewer.py
└─ viewport
   ├─ renderer.py
   ├─ tool
   │  ├─ gizmo.py
   │  └─ selection.py
   ├─ transform.py
   └─ view.py
```

### 설치

  ...

## 기능 별 분류

### 정적 편집기

3D 객체 데이터를 배치, 교체, 여러 객체 데이터 사이의 상관 관계를 편집 할 수 있는 정적 편집기.

#### 정적 편집기: Tech Stack

- 3D 시각화: OpenGL
- 3D 데이터 처리 및 연산: numpy, scipy (rotation)
- 데이터 입출력
  - trimesh (*.obj)

### 동적 분석기

3D 객체 모델을 단위시간 간격으로 진행하면서 상황을 시뮬레이션 하고 그 결과를 확인 할 수 있는 분석.

#### 동적 분석기: Tech Stack

...

### AI 모델 학습기

...

#### AI 모델 학습기: Tech Stack

...
