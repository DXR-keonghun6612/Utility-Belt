# handler

`Data_Ref` **실체화** — `data` 계층의 유일한 **I/O 게이트**. `Data_Ref.type` 이 지목하는 핸들러가
payload(이미지·배열·마스크·값)를 실제 파일로 load/save/copy/move/delete 하고, `type="stem"` 컨테이너의
구조 사이드카(서브트리 JSON)는 `Structure` 핸들러가 read/write/move/delete 한다.

스키마(`Data_Ref` 트리)는 **서술자**만 들고 실제 파일은 여기가 오간다. 스테이지·converter·process 가
전부 이 게이트를 공유해, 경로 파생·인코딩·인라인 규칙이 한곳에만 산다.

---

## 구성

```text
handler/
├── __init__.py    HANDLER_REGISTRY + 디스패치(Load/Save/Move/Copy/Delete/Types/Infer_type) + 자동 등록
├── _base.py       Data_Ref(재귀 노드) · Handler(추상) · File_Handler(디스크 파일 공통)
├── _structure.py  Structure — 구조 사이드카({root}/.meta/{stem}.json) read/write/move/delete/stems
├── image.py       image  — png/jpg 등 (cv2)
├── segmap.py      segmap — 단일채널 ID 라벨맵 (Image_Handler 특화)
├── array.py       array  — npy 배열
├── attr.py        attr   — 인라인 값(scalar·bbox 등)
└── rle.py         rle    — coco RLE mask (인코딩 코덱 소유)
```

`Data_Ref` 서술자 자체가 `_base.py` 에 산다(트리 스키마가 handler 한 방향으로만 의존 → 순환 없음).
`Structure` 는 registry 에 안 올린다 — `type` 으로 고르는 대상이 아니라 stem 이면 항상 이거다.

핸들러 모듈을 떨구기만 하면 `__init__` 이 패키지를 순회해 `@HANDLER_REGISTRY.Register_module` 을
트리거한다 — 새 처리방법 추가에 `__init__` 손댈 필요 없다. 등록된 type 목록이 곧 GUI 데이터-추가
combobox(`Types()`)와 같은 진실원천이다.

---

## Handler 계약

핸들러는 **상태가 없다**(설정은 `Data_Ref.info` 에). 그래서 메서드가 `classmethod` 고, registry 가
저장한 클래스에서 바로 호출한다(인스턴스화 없음).

```python
class Handler(ABC):
    Load(cls, root, stem, name, ref, *, obj_id=None) -> Any          # dataset → payload
    Save(cls, root, stem, name, ref, src, *, obj_id=None) -> Data_Ref # src → dataset (갱신 ref 반환)
    Default_format(cls) -> str
    Extensions(cls) -> tuple[str, ...]   # ext→type 추론용. 인라인은 ()
    Can_visualize(cls) -> bool
    # ── 쓰기 기본 구성 선언 (Template 이 참조) ──
    INLINE: ClassVar[bool]               # 값을 info 인라인(attr/rle) vs 파일(image/array/segmap)
    Claims(cls, value, *, storage, params) -> int  # spec 이 type 미지정 시 value+맥락 담당 우선순위(0=미매칭)
```

### 쓰기 기본 구성 — 각 핸들러가 선언, `Template` 이 병합

값을 어떤 `Data_Ref` 서술자로 담을지(type·inline·format)는 **각 핸들러가 자기 규칙을 소유**한다 —
중앙 테이블이 아니라 `INLINE`·`Default_format`·`Claims` 선언을, `__init__` 의 `Template` 이 registry
전체에서 모아 결정한다. 새 type(mesh·points3d …)은 파일 하나로 자기 규칙을 들고 붙는다(중앙 수정 0).

- **`Claims`** — spec 이 `type`/`format` 을 안 줄 때 value→type 을 정하는 우선순위. `storage`(=spec.to
  =="storage")·`params`(위치 없는 dataset-wide) 맥락을 함께 봐 **같은 ndarray 를 rle/array/image 로
  가른다**. 현재 선언: `attr`=1(meta fallback) · `rle`=3(frame meta 2D+) · `array`=3(params ndarray) ·
  `image`=3(frame storage ndarray) · `segmap`=0(png 추론 불가 → 항상 `type: segmap` 명시).

- `Save` 의 `src` 는 핸들러가 이해하는 입력 — converter 의 raw 파일 `Path` **또는** process 의
  in-memory payload(ndarray·값). 한 `Save` 가 두 생산자를 다 받는다.
- 파일 핸들러(`image`/`array`)는 `File_Handler` 를 상속해 경로 파생·복사/이동/삭제 공통을 받고
  `_Read`/`_Write` + `Extensions` 만 구현한다. `segmap` 은 `Image_Handler` 를 상속해 png I/O 를
  재사용하고 단일채널·uint8 로 변주한다.

---

## type 별 규약 (가이드)

| type | 용도 | format | info | payload |
|---|---|---|---|---|
| `image` | frame·mask 등 이미지 | `png` `jpg` | `{dir}` | 디스크 |
| `segmap` | 단일채널 ID 라벨맵(인스턴스/클래스) | `png` | `{dir}` | 디스크 |
| `array` | npy 배열 | `npy` | `{dir}` | 디스크 |
| `attr` | class_id·bbox 등 값 | `str` `int` `xyxy` | `{value}` | 인라인 |
| `rle` | coco RLE mask | `rle` | `{value}` | 인라인 |

인라인(`attr`/`rle`)과 파일 참조는 `Data_Ref.Is_inline()`(위치 키 `dir` 유무)이 가른다 — 내보낼 때
leaf 처리(inline → 값 그대로 / file → 핸들러)를 결정한다.

### 경로 규칙 (`File_Handler` 소유)

```text
{root}/{info.dir 또는 name}/{stem 또는 name}[_{obj_id}].{format}
```

- 디렉토리: `info.dir` 가 비면 `name`(디스크립터 키). 파일명: `stem` 우선, 없으면(params) `name`.
- 객체 payload 는 `_{obj_id}` 가 붙는다. 경로 파생은 `File_Handler` 소유 — 호출 측(store 전이·converter·
  flow)은 `root` 만 넘긴다. staging 은 store 가 `{root}/{state}` 를 `root` 로 넘겨 상태별로 가른다.

---

## API (디스패치 — 모듈 함수)

```python
from core.data import handler

handler.Load(root, stem, name, ref, *, obj_id=None) -> Any          # ref.type 핸들러로 로드
handler.Save(root, stem, name, ref, src, *, obj_id=None) -> Data_Ref
handler.Move(src_root, dst_root, stem, name, ref, *, obj_id=None)   # 상태 전이 (인라인 no-op)
handler.Copy(src_root, dst_root, stem, name, ref, *, obj_id=None)   # 병합 (원본 보존)
handler.Delete(root, stem, name, ref, *, obj_id=None)               # 인라인 no-op
handler.Types() -> list[str]                                        # 등록 목록
handler.Infer_type(ext) -> str | None                              # 확장자 → type (없으면 None=명시)
# ── 쓰기 게이트 (spec → 템플릿 → 저장; sink 가 위치만 정하면 나머지는 여기서) ──
handler.Template(spec, value, *, params=False) -> Data_Ref          # 값+맥락 → Data_Ref 서술자
handler.Route(root, stem, name, spec, value, *, obj_id=None, params=False) -> Data_Ref  # Template + Save
```

`Route` 는 sink(`Meta_sink`/`Sample_sink`)이 store 위치만 정하면 ref 구성·인코딩·경로 파생을 전부
받는 단일 쓰기 게이트다 — 구 `_data_ref`/`_params_ref`/`_attach_crop`/`_set_param` 이 여기로 수렴.
`spec` = `{to: meta|storage, level?, dir?, format?, type?}`.

`stem` 은 Optional — params 는 stem 없이 `None`(파일명 = name). `Infer_type` 은 조용한 기본값을 두지
않는다(추론 안 되면 호출 측이 type 명시).

---

## 이웃

- [`../schema.py`](../schema.py) — `Data_Ref` 서술자를 정의(핸들러가 실체화).
- [`../meta/store.py`](../meta) — 구조 전이(Move/Delete/Merge)가 이 게이트에 payload 를 위임.
- [`../converter`](../converter) — raw ingest 가 `handler.Save` 로 payload 를 떨군다.
