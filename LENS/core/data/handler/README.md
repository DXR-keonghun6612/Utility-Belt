# handler

`Data_Ref` **실체화** — `data` 계층의 유일한 **I/O 게이트**. LEAF 의 `format[0]`(handler key)이 지목하는
핸들러가 payload(이미지·배열·마스크·값)를 실제 파일로 load/save/copy/move/delete 하고, BRANCH item 의
구조 사이드카(서브트리 JSON)는 `Structure` 핸들러가 read/write/delete/walk 한다.

스키마(`Data_Ref` 트리)는 **서술자**만 들고 실제 파일은 여기가 오간다. 스테이지·converter·process 가
전부 이 게이트를 공유해, 경로 파생·인코딩·인라인 규칙이 한곳에만 산다.

---

## 구성

```text
handler/
├── __init__.py    HANDLER_REGISTRY + 디스패치(Load/Save/Move/Copy/Delete/Route/Template) + 자동 등록
├── _base.py       Handler(추상) · File_Handler(디스크 파일 공통) — Data_Ref 는 ../data_ref.py 소유
├── _structure.py  Structure — 구조 사이드카({root}/.meta/<key-path>.json) read/write/delete/walk
├── image.py       image  — png/jpg 등 (cv2)
├── segmap.py      segmap — 단일채널 ID 라벨맵 (Image_Handler 특화)
├── array.py       array  — npy 배열
├── attr.py        attr   — 인라인 값(scalar·bbox 등)
└── rle.py         rle    — coco RLE mask (인코딩 코덱 소유)
```

`Data_Ref` 서술자는 [`../data_ref.py`](../data_ref.py) 소유다 — **데이터모델이 I/O 계층을 모르도록** 의존은
`handler → data_ref` 한 방향뿐이다(여기선 편의로 재노출). `Structure` 는 registry 에 안 올린다 — `format[0]`
으로 고르는 대상이 아니라 구조 사이드카면 항상 이거다.

핸들러 모듈을 떨구기만 하면 `__init__` 이 패키지를 순회해 `@HANDLER_REGISTRY.Register_module` 을
트리거한다 — 새 처리방법 추가에 `__init__` 손댈 필요 없다. 등록된 handler key 목록이 곧 GUI 데이터-추가
combobox(`Types()`)와 같은 진실원천이다.

---

## Handler 계약

핸들러는 **상태가 없다**(설정은 `Data_Ref.info` 에) — 그래서 `classmethod` 로, registry 가 든 클래스에서
인스턴스화 없이 바로 부른다. 계약(`Load`/`Save`/`Claims`/`INLINE` 등)의 시그니처·인자 의미는
[`_base.py`](_base.py) 의 `Handler` docstring 이 소유한다. 여기선 그 계약이 **왜 이 모양인지**만.

**값→서술자 규칙을 각 핸들러가 소유한다.** 값을 어떤 `Data_Ref` 로 담을지(handler·inline·format)를 중앙
테이블이 정하지 않는다 — 각 핸들러가 `INLINE`·`Default_format`·`Claims` 를 선언하고, `Template` 이
registry 전체에서 모아 결정한다. 그래서 새 handler(mesh·points3d …)는 파일 하나로 자기 규칙을 들고 붙고
중앙을 안 건드린다. `Claims` 가 `storage`·`params` 맥락을 함께 봐 **같은 ndarray 를 rle/array/image 로
가르는** 것이 이 설계의 요점.

**한 `Save` 가 두 생산자를 받는다** — converter 의 raw 파일 `Path` 든 process 의 in-memory payload 든,
핸들러가 자기가 이해하는 입력으로 해석한다. 파일 핸들러는 `File_Handler`(경로·복사/이동/삭제 공통)를
상속해 `_Read`/`_Write` 만 구현하고, `segmap` 은 `image` 를 상속해 단일채널·uint8 로 변주한다.

---

## handler 별 규약 (가이드)

| handler | 용도 | format detail | info | payload |
|---|---|---|---|---|
| `image` | frame·mask 등 이미지 | `png` `jpg` | `{dir}` | 디스크 |
| `segmap` | 단일채널 ID 라벨맵 | `png` | `{dir}` | 디스크 |
| `array` | npy 배열 | `npy` | `{dir}` | 디스크 |
| `attr` | class_id·bbox 등 값 | `str` `int` `xyxy` | `{value}` | 인라인 |
| `rle` | coco RLE mask | `rle` | `{value}` | 인라인 |

인라인(`attr`/`rle`)과 파일 참조는 핸들러의 `INLINE` 클래스 변수가 가른다 — 인라인은 값이 사이드카
안이라 파일 전이(Move/Copy/Delete)가 no-op 이다.

### 경로 규칙 (`File_Handler` 소유)

```text
{root}/<*path>/{name}.{ext}
```

`path` 는 store 가 넘기는 **key 시퀀스**(범주부터 item·객체까지 뭉친 것 — 예 `(staged, frame0, "0")`),
`name` 은 leaf 이름, `ext` 는 `format[1]`. 경로 파생은 `File_Handler` 소유라 호출 측(store 전이·converter·
flow)은 `root` 와 `path` 만 넘긴다 — 범주가 경로에 실려 있어 전이가 파일까지 함께 옮긴다.

---

## 쓰기 게이트 — `Route`

읽기(`Load`)·전이(`Move`/`Copy`/`Delete`)는 `format[0]` 으로 핸들러를 골라 디스패치할 뿐이라 설명이
필요 없다(시그니처는 [`__init__.py`](__init__.py) docstring). **개념이 있는 건 쓰기 경로다.**

sink 이 값을 저장하려면 세 가지를 정해야 한다 — 어떤 handler 로 담을지, 어디에 쓸지, 어떻게 인코딩할지.
`Route` 가 이 셋을 한 게이트로 모은다: `Template`(값+맥락 → `Data_Ref` 서술자) + `Save`(디스크 write).
그래서 sink 은 **store 위치만** 정하면 되고, ref 구성·경로 파생·인코딩은 전부 여기로 수렴한다.

`spec` = `{to: meta|storage, dir?, format?, type?}`. `type`/`format` 을 생략하면 `Claims` 가 값·맥락으로
정하고, 그래도 못 정하면 조용한 기본값 없이 실패한다(호출 측이 명시).

---

## 이웃

- [`../data_ref.py`](../data_ref.py) — `Data_Ref` 서술자를 정의(핸들러가 실체화).
- [`../bucket_store.py`](../bucket_store.py) — 전이(Move/Delete/Merge)가 이 게이트에 payload 를 위임.
- [`../../converter`](../../converter) — raw ingest 가 `handler.Save` 로 payload 를 떨군다.
