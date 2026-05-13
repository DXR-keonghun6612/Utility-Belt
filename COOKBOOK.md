# COOKBOOK

## C/C++ 분석 (cchart)

### 기본 사용

cmake로 생성한 `compile_commands.json`을 진입점으로 사용한다.

```bash
# cmake 프로젝트에서 compile_commands.json 생성
cmake -DCMAKE_EXPORT_COMPILE_COMMANDS=ON -B build .

# 전체 프로젝트 분석
cchart build/compile_commands.json
```

출력 디렉토리(`diagrams/`)에 디렉토리별 `.drawio` 파일이 생성된다.

### 루트 디렉토리 필터

서드파티 라이브러리를 제외하고 자신의 코드만 분석하려면 `--root`를 사용한다.

```bash
cchart build/compile_commands.json --root src/
```

`src/` 하위 파일만 분석 대상이 되며, 외부 심볼은 stub 노드로 표현된다.

### 네임스페이스 필터

특정 네임스페이스에 집중할 때는 `--namespace`를 사용한다. 복수 지정이 가능하다.

```bash
cchart build/compile_commands.json -n mylib::core mylib::utils
```

### 상세 모드

메서드 인자 타입과 반환 타입을 다이어그램에 표시한다.

```bash
cchart build/compile_commands.json -d
```

### 옵션 전체

```text
cchart <compile_db> [-o OUTPUT] [-d] [-r ROOT] [-n NS [NS ...]]

  compile_db          compile_commands.json 파일 경로
  -o, --output DIR    출력 디렉토리명 (기본값: diagrams)
  -d, --detail        상세 모드 (인자 및 반환 타입 표시)
  -r, --root DIR      분석 루트 디렉토리 필터
  -n, --namespace NS  네임스페이스 필터 (복수 가능)
```

### 출력 구조

```text
project/
  diagrams/
    src.core.drawio      # src/core/ 디렉토리의 클래스 다이어그램
    src.utils.drawio     # src/utils/ 디렉토리의 클래스 다이어그램
```

각 `.drawio` 파일을 draw.io (diagrams.net)에서 열면 클래스 관계, 상속, 의존성이 시각화된다.

---

## 엣지 타입 참조

| 타입 | 의미 | UML 표기 |
|------|------|----------|
| `inheritance` | 일반 상속 | 실선 + 빈 삼각형 |
| `realization` | 추상/인터페이스 구현 | 점선 + 빈 삼각형 |
| `composition` | 강한 포함 (라이프사이클 공유) | 실선 + 채운 마름모 |
| `dependency` | 단순 타입 참조 | 점선 화살표 |
| `call` | 함수 호출 | 실선 화살표 |
| `include` | `#include` (C/C++) | 점선 화살표 |
| `friend` | `friend` 접근 (C/C++) | 점선 |
