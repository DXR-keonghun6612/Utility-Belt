# port

**외부 세계와 닿는 유일한 지점.** 데이터 **하나**의 실체화(읽기/쓰기)와 외부 레이아웃의 **발견**.

`schema` 는 서술자만 들고, 실제 파일은 여기가 오간다. 아는 것은 **디스크와 포맷뿐** — `Bucket_Store` 를
모른다. **`store` 만이 여기를 부른다**(읽기/쓰기는 store 가 소유하고 위 계층은 요청한다).

각 심볼의 인자·반환은 그 심볼의 docstring 에 있다. 이 문서는 **심볼 사이에 걸치는 것**만 다룬다.

---

## 구성

```text
port/
├── __init__.py    HANDLER_REGISTRY + 디스패치(Load/Save/Move/Copy/Delete/Route/Template) + 자동 등록
├── _base.py       Handler(추상) · File_Handler(디스크 파일 공통)
├── _structure.py  Structure — 구조 사이드카 read/write/delete/walk
├── image.py       png/jpg 등 (cv2)      ├── attr.py   인라인 값 (scalar·bbox)
├── segmap.py      단일채널 ID 라벨맵     ├── rle.py    coco RLE mask (코덱 소유)
├── array.py       npy 배열              ├── docs.py   id_map 등 중첩 구조 (yaml/json)
└── scan.py        외부 fs 발견 (glob) — pathlib 만 안다
```

핸들러 모듈을 떨구기만 하면 `__init__` 이 패키지를 순회해 `@HANDLER_REGISTRY.Register_module` 을
트리거한다 — 새 처리방법 추가에 `__init__` 을 손댈 필요가 없다. 등록된 handler key 목록이 곧 GUI
데이터-추가 combobox(`Types()`)와 같은 진실원천이다.

> **이 순회는 eager 다 — 그리고 그래도 된다.** 문제였던 유일한 이유는 cv2-free 를 무력화한다는 것이었는데,
> `Data_Ref` 가 [`../schema.py`](../schema.py) 로 빠진 지금 **port 는 떳떳하게 무거워도 된다**(원래
> 디스크·포맷 계층이다). 순수해야 하는 건 `schema` 한 모듈이지 이 계층이 아니었다.
>
> 다만 **등록 대상이 아닌 모듈(`scan.py`)은 port 내부를 import 하면 안 된다** — 순회가 도는 중이라
> 순환이 난다. `scan.py` 가 pathlib 만 아는 이유가 이것이다.

`Structure` 는 registry 에 안 올린다 — `format[0]` 으로 고르는 대상이 아니라, 구조 사이드카면 항상 이거다.

---

## Handler 계약 — 왜 이 모양인가

핸들러는 **상태가 없다**(설정은 `Data_Ref.info` 에). 그래서 `classmethod` 로, registry 가 든 클래스에서
인스턴스화 없이 바로 부른다. 계약(`Load`/`Save`/`Claims`/`INLINE` …)의 시그니처는 [`_base.py`](_base.py) 의
`Handler` docstring 이 소유한다.

**값→서술자 규칙을 각 핸들러가 소유한다.** 값을 어떤 `Data_Ref` 로 담을지(handler·inline·format)를 중앙
테이블이 정하지 않는다 — 각 핸들러가 `INLINE`·`Default_format`·`Claims` 를 선언하고 `Template` 이 registry
전체에서 모아 결정한다. 그래서 새 handler(mesh·points3d …)는 **파일 하나로** 자기 규칙을 들고 붙고 중앙을
안 건드린다. `Claims` 가 `storage`·`params` 맥락을 함께 봐 **같은 ndarray 를 rle/array/image 로 가르는**
것이 이 설계의 요점.

**빈 payload 도 핸들러가 만든다**(`Blank` — segmap=2D uint8 영배열 · image=BGR 영배열 · 미래 points3d=(0,3)…).
"빈 것이 무엇인가"는 payload 표현이라 여기 산다 — gui '빈 데이터 추가'(빈 mask 로 나서 캔버스에서 그린다)가
shape·dtype 을 손으로 짓지 않고 `port.Blank(type, size)` 로 **요청만** 한다(`store` 에 타입 스위치를 안 심는다).

**한 `Save` 가 두 생산자를 받는다** — ingest 의 raw 파일 `Path` 든 process 의 in-memory payload 든, 핸들러가
자기가 이해하는 입력으로 해석한다. 파일 핸들러는 `File_Handler`(경로·복사/이동/삭제 공통)를 상속해
`_Read`/`_Write` 만 구현하고, `segmap` 은 `image` 를 상속해 단일채널·uint8 로 변주한다.

**인라인(`attr`/`rle`)과 파일 참조는 `INLINE` 클래스 변수가 가른다** — 인라인은 값이 사이드카 안이라 파일
전이(Move/Copy/Delete)가 no-op 이다. 그래서 **파일 LEAF 의 `info` 는 비어 있다**: 위치를 서술자에 적지 않고
경로에서 파생하기 때문이다(아래).

**등록된 handler 가 아닌 첫 칸은 전부 `attr`(인라인)로 간다.** LEAF format 은 `(개념, detail)` 인데, 인라인
값은 대개 개념이 없어 첫 칸이 비고 detail 이 파이썬 타입이다(`("","str")`·`("","int")`·`("","list")`).
개념이 있을 때만 첫 칸이 찬다(`("bbox","list")`). 개념은 **표현**(gui viewer)이 가르는 것이라 여기 핸들러가
없고, 그래서 **개념을 더해도 port 는 안 고친다**. detail 은 `Save` 가 **값의 실제 파이썬 타입으로 정정**한다
— 서술자가 타입을 두고 거짓말할 수 없다.

---

## 경로 규칙 — kind-major (`File_Handler._path` 소유)

```text
{root}/{범주}/{종류}/{stem}[_{나머지 key…}].{ext}
```

store 가 넘기는 트리 key 시퀀스(`(범주, stem, *안쪽 key)`)에서 **범주와 stem 만 성분으로 남기고**, 그 안쪽
key(객체 id 등)는 stem 에 `_` 로 병합한다. **종류(= leaf 이름)가 폴더**다:

```text
(modified, frame0)      + frame     →  modified/frame/frame0.png
(modified, frame0, "0") + seg       →  modified/seg/frame0_0.png
(params,)               + c0_stats  →  params/c0_stats.npy        # params 는 stem 이 없다
```

`{root}/modified/frame` 을 그대로 가리키면 그 범주의 이미지 전체라 외부 도구·dataloader 와 1:1 이다(ML
관행). 범주가 경로 앞머리라 전이(`Move`)가 **prefix 치환**으로 끝나고 payload 가 사이드카를 따라간다.

**위치는 서술자가 아니라 트리 위치가 정한다.** 값을 어디에 쓸지는 `Data_Ref` 에 안 적히고 `path`+leaf
이름에서 파생되므로, **같은 값이 두 위치를 가리키는 상태가 구조적으로 불가능하다.**

(학습 프레임워크가 원하는 레이아웃 — ImageFolder `{class}/{sample}.png`, COCO `images/`+json — 은
**내보내기 산출물**이지 store 구조가 아니다. task 마다 축이 달라 store 는 축 하나만 고른다.)

---

## 쓰기 게이트 — `Route`

읽기(`Load`)·전이(`Move`/`Copy`/`Delete`)는 `format[0]` 으로 핸들러를 골라 디스패치할 뿐이라 개념이 없다.
**개념이 있는 건 쓰기 경로다.**

값을 저장하려면 셋을 정해야 한다 — 어떤 handler 로 담을지, 어디에 쓸지, 어떻게 인코딩할지. `Route` 가
이 셋을 한 게이트로 모은다: `Template`(값+맥락 → 서술자) + `Save`(디스크 write). 그래서 호출 측은
**트리 위치만** 정하면 되고 ref 구성·경로 파생·인코딩은 전부 여기로 수렴한다.

**`spec` 스키마는 port 소유가 아니다** — `Stage._route`([`../process/_base.py`](../process/_base.py))
docstring 이 소유하고, 여기는 그중 담을 그릇을 정하는 키(`to`·`type`·`format`)만 읽는다. 나머지(`level` =
트리 위치)는 호출 측이 이미 `path` 로 풀어 넘기므로 핸들러는 모른다 — 경로를 트리 위치에서 파생한다는 위
규칙의 귀결이다. `type`/`format` 을 생략하면 `Claims` 가 정하고, 그래도 못 정하면 **조용한 기본값 없이
실패**한다.

**`Template_for_file` 은 그 자매다** — 담을 그릇을 정하는 일은 같고 무엇으로 고르느냐만 다르다:
`Template` 은 **값**으로, 저건 **확장자**로. ingest 처럼 값을 읽기 *전에* 서술자가 필요한 자리를 위한 것이다.

---

## 발견 — `scan.py`

**발견과 등록은 다른 일이다.** `Scan` 은 *어떤 파일이 있나*(`{stem: {종류: 경로}}`)만 답하고, *어느 범주에
어떻게 넣나*는 [`store.Import`](../store/README.md) 가 정한다. 그래서 **store 는 glob 패턴을 모르고 port 는
범주를 모른다.**

한 stem 이 선언된 glob key 를 **다 갖출 때만** 그룹이 선다(inner join) — 한 종류가 빠진 프레임은 반쪽짜리라
들이지 않는다.

---

## 이웃

- [`../schema.py`](../schema.py) — `Data_Ref` 서술자 (여기가 실체화한다). **재노출하지 않는다.**
- [`../store`](../store) — 이 게이트의 **유일한 소비자**.
- 잔여·열린 논의는 [`TODO.md`](TODO.md).
