# discover

정해진 annotation 포맷이 없는, 한 폴더에 흩어진 loose 파일을 패턴으로 묶어 샘플을
*재구성*하는 converter 계열. 각 전략은 `Base_Converter` 를 상속해
`Convert(stem_root, params_root)` 를 구현한다 (함수가 아니라 상속 구조).

상위 맥락은 [`../README.md`](../README.md), 디스크립터·핸들러 규약은
[`../../README.md`](../../README.md)·[`../../schema.py`](../../schema.py) 참조.

---

## 구조

```text
discover/
├── __init__.py    Glob_Discover re-export
└── glob.py        Glob_Discover — glob 스캔 + stem 그룹핑
```

- 포맷 파서(`coco.py`/`yolo.py` — 정해진 포맷 직접 파싱)는 여기가 아니라
  `converter/` 직속에 둔다. discover 는 포맷이 없는 폴더를 패턴으로 *추정*하는 쪽.

---

## Glob_Discover (`glob.py`)

glob 패턴으로 raw 파일을 탐색해 stem 컨테이너 `Data_Ref`(`type="stem"`)를 생성한다.
glob key 마다 처리 `type` 을 선언한다 (key 이름 = 데이터 이름). `type` 을 생략하면 패턴의
확장자로 핸들러를 추론한다(`handler.Infer_type`). 추론 안 되는 확장자(txt 등)는 명시한다.

```yaml
sources: [/data/raw]
globs:
  frame:    {pattern: "*_pose.png"}                          # type 생략 → 확장자 추론(png→image)
  class_id: {pattern: "*_pose.txt", type: attr}              # txt 추론 안 됨 → type 명시
  mask:     {pattern: "*_mask.png", type: image, dir: raw_mask}  # dir 오버라이드
params:
  roi: {pattern: /…/roi.png}                                 # dir 생략 → params
id_map: /…/id_map.yaml
```

`globs`/`params` 값은 `{pattern, type?, dir?, format?}` dict 또는 패턴 문자열(type 은
확장자 추론, dir 기본)을 받는다.

### 처리 흐름 (`Convert(stem_root, params_root)`)

1. `_Scan()` → `{stem: {name: src_path}}` — 모든 key 가 매칭된 stem 만 (inner join).
   stem 은 `_extract_stem` 이 glob `*` 위치의 variable part 로 뽑는다.
2. stem 마다 `Data_Ref(type="stem")` 구성 — 각 `(name, src)` 에 대해
   `frame.info[name] = handler.Save(stem_root, stem, name, ref, src)`
   (`image`/`array`: 복사 / `attr`: 내용 읽어 인라인 / `rle`: 인코딩). 객체(중첩 stem)는 없이 시작.
3. `params` 도 `handler.Save(params_root, None, name, ref, src)` (stem 없음 → 파일명 = name).
4. 반환 `(frames, params)`.

라벨이 여러 개든 다른 종류(rle·array)든 동일 규칙으로 확장된다.

---

## 전략 추가

```python
# discover/my.py — 새 폴더 스캔 전략
from .._base import Base_Converter

class My_Discover(Base_Converter):
    def Convert(self, root):
        ...   # 디스크립터 템플릿 + raw 소스만 정하고 handler.Save 에 위임
```

`__init__.py` 에 re-export 한 줄 추가한다.