# 01_parser — IR 추출

**책임**
- AST → 언어별 IR (`Class_Info`, `Method_Info`, `Module_Info`, 언어 확장)
- 노드 ID 부여
- 분류는 하지 않음 (`abstraction = concrete` 기본값, `traits = []`)
- 가능한 모든 메타데이터 추출 — 버리는 건 이후 단계 책임

01_parser는 구조 트랙과 플로우 트랙의 **공유 줄기**다. 클래스/메서드 시그니처뿐 아니라
메서드 본문 내 call-site도 추출한다 (구조 트랙은 call-site를 무시) — [flow-track.md](flow-track.md) 참고.

**노드 ID 규칙**

```
{file_key}::{namespace_path}::{name}
```
- C++: `src/core/widget.cpp::core::Widget`
- Python: `src/core/widget.py::Widget`

**yaml 예시**

```yaml
# debug/01_parser/src__core__widget.cpp.yaml
meta:
  schema_version: 1
  language: cxx
  source_path: /abs/path/src/core/widget.cpp
  source_hash: <blake2b-16>
  dependency_hashes:
    /abs/path/src/core/widget.h: <hash>
    /abs/path/src/core/base.h:   <hash>
  context_hash: <hash of compile_flags + language version>

body:
  type: Module_Info
  name: widget.cpp
  file_path: /abs/path/src/core/widget.cpp
  imported_symbols: {...}
  functions: [...]
  classes:
    - type: CXX_Class_Info
      id: src/core/widget.cpp::core::Widget
      name: Widget
      kind: class
      namespace_path: core
      template_params: []
      origin: internal
      abstraction: concrete       # 기본값 — 02에서 갱신
      traits: []                  # 기본값 — 02에서 채움
      bases: ["core::BaseWidget"]
      attributes: [...]
      methods: [...]
      source_line: 42
```
