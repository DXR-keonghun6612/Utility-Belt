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
├── _base.py       Handler(추상) · File_Handler(디스크 파일 공통) — Data_Ref 는 ../schema.py 소유
├── _structure.py  Structure — 구조 사이드카({root}/.meta/{stem}.json) read/write/move/delete/stems
├── image.py       image  — png/jpg 등 (cv2)
├── segmap.py      segmap — 단일채널 ID 라벨맵 (Image_Handler 특화)
├── array.py       array  — npy 배열
├── attr.py        attr   — 인라인 값(scalar·bbox 등)
└── rle.py         rle    — coco RLE mask (인코딩 코덱 소유)
```

`Data_Ref` 서술자는 [`../schema.py`](../schema.py) 소유다 — **데이터모델이 I/O 계층을 모르도록** 의존은
`handler → schema` 한 방향뿐이다(여기선 편의로 재노출). 그래서 데이터모델만 필요한 소비자는 cv2·핸들러
registry 없이 `schema.py` 만 들일 수 있다.
`Structure` 는 registry 에 안 올린다 — `type` 으로 고르는 대상이 아니라 stem 이면 항상 이거다.

핸들러 모듈을 떨구기만 하면 `__init__` 이 패키지를 순회해 `@HANDLER_REGISTRY.Register_module` 을
트리거한다 — 새 처리방법 추가에 `__init__` 손댈 필요 없다. 등록된 type 목록이 곧 GUI 데이터-추가
combobox(`Types()`)와 같은 진실원천이다.

---

## Handler 계약

핸들러는 **상태가 없다**(설정은 `Data_Ref.info` 에) — 그래서 `classmethod` 로, registry 가 든 클래스에서
인스턴스화 없이 바로 부른다. 계약(`Load`/`Save`/`Claims`/`INLINE` 등)의 시그니처·인자 의미는
[`_base.py`](_base.py) 의 `Handler` docstring 이 소유한다. 여기선 그 계약이 **왜 이 모양인지**만.

**값→서술자 규칙을 각 핸들러가 소유한다.** 값을 어떤 `Data_Ref` 로 담을지(type·inline·format)를 중앙
테이블이 정하지 않는다 — 각 핸들러가 `INLINE`·`Default_format`·`Claims` 를 선언하고, `Template` 이
registry 전체에서 모아 결정한다. 그래서 새 type(mesh·points3d …)은 파일 하나로 자기 규칙을 들고 붙고
중앙을 안 건드린다. `Claims` 가 `storage`·`params` 맥락을 함께 봐 **같은 ndarray 를 rle/array/image 로
가르는** 것이 이 설계의 요점 — 우선순위 값은 각 핸들러 코드가 든다.

**한 `Save` 가 두 생산자를 받는다** — converter 의 raw 파일 `Path` 든 process 의 in-memory payload 든,
핸들러가 자기가 이해하는 입력으로 해석한다. 파일 핸들러는 `File_Handler`(경로·복사/이동/삭제 공통)를
상속해 `_Read`/`_Write` 만 구현하고, `segmap` 은 `image` 를 상속해 단일채널·uint8 로 변주한다.

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

## 쓰기 게이트 — `Route`

읽기(`Load`)·전이(`Move`/`Copy`/`Delete`)는 `ref.type` 으로 핸들러를 골라 디스패치할 뿐이라 설명이
필요 없다(시그니처는 [`__init__.py`](__init__.py) docstring). **개념이 있는 건 쓰기 경로다.**

sink 이 값을 저장하려면 세 가지를 정해야 한다 — 어떤 type 으로 담을지, 어디에 쓸지, 어떻게 인코딩할지.
`Route` 가 이 셋을 한 게이트로 모은다: `Template`(값+맥락 → `Data_Ref` 서술자) + `Save`(디스크 write).
그래서 sink(`Meta_sink`/`Sample_sink`)은 **store 위치만** 정하면 되고, ref 구성·경로 파생·인코딩은
전부 여기로 수렴한다(구 `_data_ref`/`_params_ref`/`_attach_crop`/`_set_param` 이 이 하나로).

`spec` = `{to: meta|storage, level?, dir?, format?, type?}`. `type`/`format` 을 생략하면 `Claims` 가
값·맥락으로 정하고, 그래도 못 정하면 조용한 기본값 없이 실패한다(호출 측이 명시).

---

## 이웃

- [`../schema.py`](../schema.py) — `Data_Ref` 서술자를 정의(핸들러가 실체화).
- [`../meta/store.py`](../meta) — 구조 전이(Move/Delete/Merge)가 이 게이트에 payload 를 위임.
- [`../converter`](../converter) — raw ingest 가 `handler.Save` 로 payload 를 떨군다.
