# 외부 의존성 정책

## 사용

- **libclang** — C++ AST 추출 (대체 불가)
- **python_toolbox** — Data_Schema, Registry, 직렬화

## 사용하지 않음 (직접 구현)

- **networkx** 등 외부 그래프 라이브러리
  - 필요한 알고리즘(위상정렬, DFS, 사이클 감지)은 `core/graph_ops.py`에 직접 구현 (~100줄 예상)
- **graphviz / grandalf** 자동 레이아웃
  - 의미론적 휴리스틱이 도메인 지식 기반이므로 자체 구현(`core/layout/semantic.py`)

이유: 의존성 적을수록 배포·유지보수 편함. 우리 그래프 크기(디렉토리당 수십~수백 노드)에서는
직접 구현으로 충분.
