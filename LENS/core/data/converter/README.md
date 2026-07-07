# converter

raw 데이터를 탐색해 stem 컨테이너 `Data_Ref`(`type="stem"`) 목록 + params(`Data_Ref`)를 생성한다 —
`data` 계층의 **raw → 구조 ingest 게이트**(payload I/O 게이트 `handler` 와 대칭). 모든 디스크 쓰기·경로
파생은 직접 하지 않고 핸들러(`handler.Save`)에 위임한다 — converter 는 디스크립터 템플릿과 raw 소스만 정한다.

`meta` 를 import 하지 않는다 — 산출물은 어느 스테이지에도 매이지 않은 stem `Data_Ref` 고, 바인더
(`Pipeline`)가 그걸 `Dataset_Meta.modified` 로 병합한다. 설계 전제(Data_Ref · 핸들러)는
[`../README.md`](../README.md)·[`../schema.py`](../schema.py) 참조.

---

## 구조

```text
converter/
├── _base.py            Base_Converter (abstract) — Convert(stem_root, params_root)
└── discover/           폴더에 흩어진 파일을 패턴으로 묶는 계열 (Base_Converter 상속)
    ├── __init__.py
    └── glob.py         Glob_Discover — glob 스캔 + 그룹핑
```

- `discover/` — 정해진 annotation 포맷이 없는, 한 폴더의 loose 파일을 패턴으로 그룹핑해
  샘플을 *재구성*하는 converter 계열. 각 전략은 `Base_Converter` 를 상속해 `Convert` 를 구현한다.
- 포맷 파서(`coco.py`/`yolo.py` 등 — 정해진 포맷 직접 파싱)는 `converter/` 직속에 추가한다.

---

## Base_Converter

```python
class Base_Converter(ABC):
    @abstractmethod
    def Convert(self, stem_root: str, params_root: str
                ) -> tuple[list[tuple[str, Data_Ref]], dict[str, Data_Ref]]:
        """raw 입력을 탐색해 (stem, 컨테이너 Data_Ref) 목록과 params 를 반환한다.
        파일 쓰기·경로는 handler.Save 에 위임. 프레임은 stem_root(보통 {root}/modified),
        params 는 params_root({root} 직속)로 가른다."""

    def Load_id_map(self) -> dict[str, dict[str, int]]:
        """class → scope → id 정의 (없으면 {}). id_map 소비는 sample 계층(보류)."""
```

- `Convert(stem_root, params_root)` 가 계약. `Discover` 는 메서드가 아니라 `Base_Converter` 를
  상속하는 클래스 계열(`discover/`)이다.
- `meta` 를 받지 않는다 — converter 는 stem 컨테이너 `Data_Ref` 를 생산하는 쪽. 핸들러가 필요로 하는 건
  출력 루트(경로 파생)뿐이라 `stem_root`/`params_root` 만 받고 `(frames, params)` 를 돌려준다.
  (호출 측 = 바인더가 `Dataset_Meta` 에 병합)

---

## Glob_Discover (`discover/glob.py`)

glob 패턴으로 raw 파일을 탐색해 stem 컨테이너 `Data_Ref` 를 생성한다. `label_key` 특수처리는 없다 —
glob key 마다 처리 `type` 을 선언한다 (key 이름 = 데이터 이름). `type` 생략 시 패턴 확장자로
핸들러를 추론한다(`handler.Infer_type`); 추론 안 되는 확장자(txt 등)는 명시한다.

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

### 처리 흐름 (`Convert(stem_root, params_root)`)

1. `_Scan()` → `{stem: {name: src_path}}` (모든 key 매칭 = inner join, stem 은 `_extract_stem`)
2. stem 마다 컨테이너 `Data_Ref(type="stem")` 구성 — 각 `(name, src)` 에 대해:
   - `ref = _Ref(globs[name])` → `Data_Ref(type=type(생략 시 확장자 추론), format, info={dir})`
   - `frame.info[name] = handler.Save(stem_root, stem, name, ref, src)`
     - `image`/`array`: 복사 + 경로 파생 / `attr`: 내용 읽어 `info.value` 인라인 / `rle`: 인코딩
   - 객체(중첩 stem)는 없이 시작 — 하위 scope 는 pipeline(process/GUI)이 `info` 에 채운다.
3. `params` 도 동일하게 `handler.Save(params_root, None, name, ref, src)` (stem 없음 → 파일명 = name)
4. 반환 `(frames, params)`

key별 `type` → 핸들러 디스패치라 라벨 특수처리가 없다 — 라벨이 여러 개든 다른 종류(rle·array)든
동일 규칙으로 확장된다.

`globs`/`params` 값은 `{pattern, type?, dir?, format?}` dict 또는 패턴 문자열(type 은 확장자
추론, dir 기본)을 받는다.

---

## 확장

```python
# discover 계열 — 폴더 스캔 전략 추가
class My_Discover(Base_Converter):     # converter/discover/my.py
    def Convert(self, stem_root, params_root): ...

# 포맷 파서 — 정해진 포맷 직접 파싱
class Coco_Converter(Base_Converter):  # converter/coco.py
    def Convert(self, stem_root, params_root): ...
```