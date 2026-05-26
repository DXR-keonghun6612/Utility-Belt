# 중간 결과 저장 · 캐시 / 무효화

## 중간 결과 저장

### 옵션

- `--debug` (기본값 `true`, 릴리즈 시 `false`로 전환)
- `--output-root <path>` (기본값 있음)

### 디렉토리 구조

```
{output_root}/
  debug/
    01_parser/{file_key}.yaml
    02_classifier/{file_key}.yaml
    03_linker/{dir}.yaml
    04_layout/{dir}.yaml
  result/
    {dir}.drawio
```

플로우 트랙의 중간 결과 경로는 [flow-track.md](flow-track.md) 참고.

### 포맷

- yaml / json (확장자 기반 자동 직렬화, `python_toolbox` 활용)
- Data_Schema 상속으로 클래스 자동 직렬화
- 역직렬화 디스패치 키: yaml 본문의 `type` 필드 (클래스명)

## 캐시 / 무효화

### 해시 알고리즘

`hashlib.blake2b(digest_size=16)` — 변경 감지 용도이므로 빠르고 가벼운 선택.

### 무효화 키

각 단계 yaml의 `meta`에 4종의 해시를 기록 → 자동 무효화 판정:

| 해시 | 의미 |
|------|------|
| `source_hash` | 자기 소스 파일 해시 |
| `dependency_hashes` | 의존 파일(C++의 transitive include / Python의 import) 각각의 해시 |
| `context_hash` | 언어별 빌드/실행 컨텍스트 (C++의 compile_flags, Python 버전 등) |
| `upstream_hash` | 직전 단계 출력 yaml의 해시 (단계 체이닝) |

### 재진입 규칙

- 단계별로 yaml 존재 여부 + 해시 일치 → 그대로 사용
- 어느 하나라도 불일치 → 그 단계부터 재실행 (이후 단계 자동 재실행)
- 의심 시 해당 단계 폴더 삭제로 강제 재실행
