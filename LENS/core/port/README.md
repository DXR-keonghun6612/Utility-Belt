# port

**외부 세계와 닿는 유일한 지점.** 데이터 **하나**의 실체화(읽기/쓰기)와 외부 레이아웃의 **발견**.

`schema` 는 서술자만 들고, 실제 파일은 여기가 오간다. 아는 것은 **디스크와 포맷뿐** — `Bucket_Store` 를
모른다. **`store` 만이 여기를 부른다**(읽기/쓰기는 store 가 소유하고 위 계층은 요청한다). 이 방향과
"소비자는 store 하나"는 [`../README.md`](../README.md) 의 불변식 ②다.

각 심볼의 인자·반환은 그 심볼의 docstring 에 있다. 이 문서는 **심볼·계층 사이에 걸치는 것**만 다룬다.

> **이름 미결** — 아래 세 축이 밖으로 나간 지금 이 계층에 남는 건 "무엇으로 읽나 + 검증·정책 + 디스패치"라
> 이름이 `domain` 에 가깝다. `port → domain` 개명은 아직 정하지 않았다 → [`../TODO.md`](../TODO.md) "★ 축 정리".

---

## 세 축이 `format = (domain, format)` 을 나눠 든다

`port` 는 이제 **파사드**다 — 자기는 디스패치만 하고, 실체는 세 계층이 나눠 든다:

| 층 | 무엇 | 소유 |
|---|---|---|
| **domain** ([`domain/`](domain)) | *무엇으로 읽나* — 유효 포맷 검증(`Validate`) · 의미 보정(`Normalize`) · 포맷 편성(`To`) · 정책(`Claims`·`Blank`) | `domain/_base.py` docstring |
| **codec** ([`../codec`](../codec)) | *바이트 ↔ 값* — 어느 I/O 모듈이 싣나(cv2·numpy·yaml·인라인) | `codec` 패키지 docstring |
| **format** ([`../format`](../format)) | *값의 구조* — bbox·polygon·rle 와 그 사이 변환 **계산** | `format` 패키지 docstring |

*codec 은 바이트가 무슨 뜻인지 모르고, format 은 그게 어디 사는지 모르고, domain 만 둘 다 안다.* 그래서
새 구조는 **파일 하나**로 붙는다 — `format/` 에 구조를, `codec/` 에 I/O 를 떨구고 도메인 `FORMATS` 에 한
줄 더한다. SAM polygon 이 그렇게 붙었다.

**대표 포맷(정준형)은 없다.** 한때 도메인마다 포맷 하나를 대표로 정해 `Load` 가 전부 그리로 뭉갰다 —
그래서 `("mask", "polygon")` 을 읽으면 배열이 나왔고 폴리곤은 자기 구조를 지킬 수 없었다(편집기가 꼭짓점을
못 봤다). 이제 `Load` 는 **네이티브 구조를 그대로** 내고(도메인은 `Normalize` 로 의미만 보정), 배열이
필요한 소비처만 도메인의 `To(value, "npy")` 로 **명시적으로** 요청한다.

---

## 디스패치 — 도메인이 검증하고, codec 이 I/O 한다

`Data_Ref.format` 튜플이 라우팅을 정한다:

```text
format[0] = 도메인 이름     format[1] = codec 이 맡는 포맷 이름     (bbox 는 format[2] = style)
```

- `_domain(ref)` — `format[0]` 으로 도메인을 고른다. 등록된 도메인이 아니면(빈 칸 = 순수 파이썬 값,
  또는 아직 도메인이 없는 개념) `attr` 로 보낸다.
- `_codec(ref)` — **도메인이 `format[1]` 의 유효성을 먼저 검증**한 뒤(`Validate`) `Codec_for(format[1])`
  로 codec 을 고른다. 유효하지 않은 포맷·맡는 codec 없음은 조용히 넘기지 않고 실패한다.

`Load`/`Save`/`Move`/`Copy`/`Delete`/`Path_of`/`Can_visualize` 가 이 두 헬퍼로 실제 codec·domain 에
위임한다. **개념이 있는 건 쓰기 경로뿐**이다(읽기·전이는 `format[0]` 디스패치일 뿐) — 그래서 쓰기만
게이트를 둔다.

---

## 쓰기 게이트 — `Route` · `Template`

값을 저장하려면 셋을 정해야 한다 — 어떤 도메인으로 담을지, 어디에 쓸지, 어떤 포맷으로 인코딩할지.
`Route` 가 이 셋을 한 게이트로 모은다: `Template`(값+맥락 → 서술자) + `Save`(디스크 write). 호출 측은
**트리 위치만** 정하고 ref 구성·경로 파생·인코딩은 여기로 수렴한다.

- **도메인 확정 순서** — `spec.type` → `spec.format` 확장자 추론 → value+맥락 `Claims`(도메인마다
  `storage`·`params` 맥락을 봐 **같은 ndarray 를 mask(인라인)/image(파일)/array(params)로 가른다**).
  못 정하면 조용한 기본값 없이 실패한다.
- **`to` 는 요청이지 힌트가 아니다** — 그릇(`meta`=인라인 / `storage`·`trace`=파일)과 확정된 포맷의
  `INLINE` 이 어긋나면 실패한다. 같은 mask 라도 `to` 에 따라 rle(인라인)/png(파일)로 갈린다.
- **`Template_for_file` 은 그 자매다** — 담을 그릇을 정하는 일은 같고, ingest 는 값을 읽기 *전*이라
  **확장자가 아니라 `type`(도메인)을 필수로 명시**한다(png 하나가 image·mask 라 추론은 조용한 선택).

`spec` 스키마는 port 소유가 아니다 — `Stage._route`([`../process/_base.py`](../process/_base.py)) docstring 이
소유하고, 여기는 담을 그릇을 정하는 키(`to`·`type`·`format`)만 읽는다.

---

## 경로 규칙 — kind-major

```text
{root}/{범주}/{종류}/{stem}[_{나머지 key…}].{ext}
```

구현은 [`../codec/_base.py`](../codec/_base.py) `File_Codec._path` 하나다. store 가 넘기는 트리 key 시퀀스
(`(범주, stem, *안쪽 key)`)에서 **범주와 stem 만 성분으로 남기고**, 안쪽 key(객체 id 등)는 stem 에 `_` 로
병합한다. **종류(= leaf 이름)가 폴더**다:

```text
(modified, frame0)      + frame     →  modified/frame/frame0.png
(modified, frame0, "0") + seg       →  modified/seg/frame0_0.png
(params,)               + c0_stats  →  params/c0_stats.npy        # params 는 stem 이 없다
```

`{root}/modified/frame` 을 그대로 가리키면 그 범주의 이미지 전체라 외부 도구·dataloader 와 1:1 이다.
범주가 경로 앞머리라 전이(`Move`)가 **prefix 치환**으로 끝나고 payload 가 사이드카를 따라간다.

**위치는 서술자가 아니라 트리 위치가 정한다.** 값을 어디에 쓸지는 `Data_Ref` 에 안 적히고 `path`+leaf
이름에서 파생되므로, **같은 값이 두 위치를 가리키는 상태가 구조적으로 불가능하다.** 그래서 파일 LEAF 의
`info` 는 비어 있다. (학습 프레임워크 레이아웃 — ImageFolder·COCO — 은 **내보내기 산출물**이지 store
구조가 아니다.)

---

## 사이드카 · 발견

- **`_structure.py`** — `Structure` 는 payload 가 아니라 **`Data_Ref` 트리 자체**를 싣는 사이드카다.
  `format[0]` 으로 고르는 대상이 아니라(서술자 포맷은 하나뿐) registry 밖에 있다. → [`TODO.md`](TODO.md)
  ("사이드카 codec 으로 옮길지" 논의).
- **`scan.py`** — 외부 fs **발견**(glob)만. **발견과 등록은 다른 일이다** — `Scan` 은 *어떤 파일이 있나*
  (`{stem: {종류: 경로}}`)만 답하고, *어느 범주에 어떻게 넣나*는 [`store.Import`](../store/README.md) 가
  정한다. 그래서 store 는 glob 패턴을 모르고 port 는 범주를 모른다. 한 stem 이 선언된 glob key 를 **다
  갖출 때만** 그룹이 선다(inner join). scan 은 pathlib 만 알아 등록 순회에 안 걸린다.

---

## 자동 등록

도메인 모듈([`domain/`](domain))·codec 모듈([`../codec`](../codec))을 떨구기만 하면 각 패키지의 `__init__`
이 순회해 registry 에 등록한다 — 중앙 테이블을 안 건드린다. 등록된 도메인 목록이 곧 GUI 데이터-추가
combobox(`Types()`)의 진실원천이다.

> **이 순회는 eager 다 — 그리고 그래도 된다.** 문제였던 유일한 이유는 cv2-free 를 무력화한다는 것이었는데,
> `Data_Ref` 가 [`../schema.py`](../schema.py) 로 빠진 지금 **port 는 떳떳하게 무거워도 된다**(원래 디스크·
> 포맷 계층이다). 순수해야 하는 건 `schema` 한 모듈이지 이 계층이 아니었다.

---

## 이웃

- [`../schema.py`](../schema.py) — `Data_Ref` 서술자 (여기가 실체화한다). **재노출하지 않는다.**
- [`../format`](../format) · [`../codec`](../codec) — 구조와 I/O (port 가 딛고 서는 밑 계층).
- [`../store`](../store) — 이 게이트의 **유일한 소비자**.
- 잔여·열린 논의는 [`TODO.md`](TODO.md).
