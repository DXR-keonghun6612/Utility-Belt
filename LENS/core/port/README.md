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

단 이 순회는 **eager** 라, `handler` 를 조금이라도 건드리면 전 핸들러의 무거운 의존(cv2·numpy)이 딸려온다
— 위 `data_ref` 단방향 의존이 약속하는 cv2-free 를 소비처가 실제로는 못 누린다. 열린 논의는
[`../TODO.md`](../TODO.md).

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
| `image` | frame·mask 등 이미지 | `png` `jpg` | `{}` | 디스크 |
| `segmap` | 단일채널 ID 라벨맵 | `png` | `{}` | 디스크 |
| `array` | npy 배열 | `npy` | `{}` | 디스크 |
| `docs` | id_map 등 중첩 구조 | `yaml` `json` | `{}` | 디스크 |
| `attr` | class_id·bbox 등 값 | `str` `int` `xyxy` | `{value}` | 인라인 |
| `rle` | coco RLE mask | `rle` | `{value}` | 인라인 |

인라인(`attr`/`rle`)과 파일 참조는 핸들러의 `INLINE` 클래스 변수가 가른다 — 인라인은 값이 사이드카
안이라 파일 전이(Move/Copy/Delete)가 no-op 이다. **파일 LEAF 의 `info` 는 비어 있다** — 위치를 서술자에
적지 않고 경로에서 파생하기 때문이다(아래).

### 경로 규칙 — kind-major (`File_Handler._path` 소유)

```text
{root}/{범주}/{종류}/{stem}[_{나머지 key…}].{ext}
```

`path`(store 가 넘기는 트리 key 시퀀스 `(범주, stem, *안쪽 key)`)에서 **범주와 stem 만 성분으로 남기고**,
그 안쪽 key(객체 id 등)는 stem 에 `_` 로 병합한다. **종류(= leaf 이름)가 폴더**다:

```text
(modified, frame0)      + rgb       →  modified/rgb/frame0.png
(modified, frame0, "0") + seg       →  modified/seg/frame0_0.png
(params,)               + c0_stats  →  params/c0_stats.npy      # params 는 stem 이 없다
```

`{root}/modified/rgb` 를 그대로 가리키면 그 범주의 이미지 전체라, 외부 도구·dataloader 와 1:1 이다(ML
관행). 범주가 경로 앞머리라 전이(`Move`)는 여전히 prefix 치환으로 끝나고, payload 가 사이드카를 따라간다.

**위치는 서술자가 아니라 트리 위치가 정한다.** 값을 어디에 쓸지는 `Data_Ref` 에 적히지 않고 `path`+leaf
이름에서 파생되므로, 같은 값이 두 위치를 가리키는 상태가 구조적으로 불가능하다. (학습 프레임워크가 원하는
레이아웃 — ImageFolder `{class}/{sample}.png`, YOLO `images/`+`labels/` — 은 **Export 산출물**이지 store
구조가 아니다. task 마다 축이 다르므로 store 는 축 하나만 고른다.)

---

## 쓰기 게이트 — `Route`

읽기(`Load`)·전이(`Move`/`Copy`/`Delete`)는 `format[0]` 으로 핸들러를 골라 디스패치할 뿐이라 설명이
필요 없다(시그니처는 [`__init__.py`](__init__.py) docstring). **개념이 있는 건 쓰기 경로다.**

sink 이 값을 저장하려면 세 가지를 정해야 한다 — 어떤 handler 로 담을지, 어디에 쓸지, 어떻게 인코딩할지.
`Route` 가 이 셋을 한 게이트로 모은다: `Template`(값+맥락 → `Data_Ref` 서술자) + `Save`(디스크 write).
그래서 sink 은 **store 위치만** 정하면 되고, ref 구성·경로 파생·인코딩은 전부 여기로 수렴한다.

**`spec` 은 handler 소유가 아니다** — 스키마는 `Base_Sink.route`(`core/process/sink.py`) docstring 이
소유하고, 여기는 그중 `to`·`type`·`format` **세 키만** 읽는다(`Template`). 나머지(`level` = 트리 위치)는
sink 이 해석해 `path` 로 넘기므로 핸들러는 모른다 — 경로를 서술자가 아니라 트리 위치에서 파생한다는
위 규칙의 귀결이다. `type`/`format` 을 생략하면 `Claims` 가 값·맥락으로 정하고, 그래도 못 정하면 조용한
기본값 없이 실패한다(호출 측이 명시).

---

## 이웃

- [`../data_ref.py`](../data_ref.py) — `Data_Ref` 서술자를 정의(핸들러가 실체화).
- [`../bucket_store.py`](../bucket_store.py) — 전이(Move/Delete/Merge)가 이 게이트에 payload 를 위임.
- [`../../converter`](../../converter) — raw ingest 가 `handler.Save` 로 payload 를 떨군다.
