# 디렉토리 구조 (목표)

```
core/
  definition.py        # IR (Class_Info, Method_Info, Module_Info, ...)
  graph.py             # Graph_Model, Edge_Info, Node_Info, Positioned_Graph
  graph_ops.py         # 위상정렬, DFS, 사이클 감지 등 (직접 구현)
  registry.py          # 전역 심볼 테이블 베이스
  hashing.py           # 4종 해시 계산 + 무효화 판정
  serialization.py     # Data_Schema 기반 yaml/json 자동 직렬화
  layout/
    semantic.py        # 의미론적 layer/wing/col 부여
    crossing.py        # barycenter 교차 최소화

parser/                # 언어별 parser
  protocol.py          # Parser Protocol 인터페이스
  cxx/                 # C/C++
    extractor.py       # AST → IR
    classifier.py      # 02_classifier 로직 (C++ 한정)
    linker.py          # 03_linker 로직 (C++ 한정)
  python/              # Python
    extractor.py
    classifier.py
    linker.py

render/                # 시각화 백엔드 (3계층의 renderer)
  drawio/
  mermaid/
  plantuml/

# 진입점 (CLI) — 단일
code_chart/            # CLI facade 'code-chart' — --language로 언어별 parser 디스패치
```
