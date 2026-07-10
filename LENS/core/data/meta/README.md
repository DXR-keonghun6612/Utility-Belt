# meta

정본(canonical) 스테이지 — raw 에서 뽑은 **정본 annotation** 을 담는 데이터 구조(`Dataset_Meta`)를 든다.
그 영속·전이(디스크 I/O)는 여기가 아니라 [`../store_io.py`](../store_io.py) 자유함수가 수행한다.

`data` 계층의 두 구체 스테이지 중 정본 쪽(파생은 [`../sample`](../sample), 현재 보류). 공유 데이터모델은
[`../schema.py`](../schema.py), 그 I/O 는 [`../store_io.py`](../store_io.py), payload/구조 핸들러는
[`../handler`](../handler), raw 수집은 [`../converter`](../converter) 가 각각 소유한다.

---

## 구성

```text
meta/
├── store.py   Dataset_Meta(Bucket_Store) — CATEGORIES + staging 편의
└── __init__.py
```

`Dataset_Meta` 는 별도 `schema.py` 없이 `store.py` 에 산다 — 영속·전이는 `store_io` 자유함수라, 여기
남는 건 `CATEGORIES` 고정 + staging 용어 편의뿐이다.

---

## Dataset_Meta — staging 3-버킷

`Bucket_Store`(forest 파사드)를 상속해 **범주만 고정**한다.

```python
class Dataset_Meta(Bucket_Store):
    CATEGORIES = META_STATES        # ("modified", "staged", "skipped")
```

- **`modified`** (작업) — flow 출력·외부 가져오기가 들어오는 working 버킷.
- **`staged`** (검수) — 검수 완료(그대로 학습 annotation 으로 나감).
- **`skipped`** (보류) — 작업 대상 외. 지우지 않고 치워둔 것(되돌리기 가능). **모든 파이프라인에서 자연히
  제외**된다 — Convert/Run 은 `modified` 만, Sample/Export 는 `staged` 만 지목하므로 skipped 는 어디에도 안 걸림.
- 한 stem 은 **한 버킷에만** 있고, 버킷 멤버십이 곧 상태(라벨 필드 없음). 상태 전이 = 버킷 이동 (`Move`).
  상태 추가는 `core/constant.py` `META_STATES` 한 줄 + GUI 뱃지(`gui/meta_view/_stem_list._BADGE`) 한 줄이면
  된다 — store·전이·순회는 `CATEGORIES` 제네릭이라 자동.
- 항목(stem)은 컨테이너 `Data_Ref`(`type="stem"`), 그 `info` 의 자식 stem 이 객체(obj_id = key). class 는
  `info["class_id"]` attr(`schema.Attr`/`Set_attr`). class→정수 id 매핑(`id_map`)은 meta 가 아니라 파생
  (sample)이 소유한다 — meta 는 class **이름**만 든다.

범주 조회·순회(`Bucket`/`Category_of`/`Find`/`Iter_category`/`Iter_all`/`Iter_refs`)와 staging 편의
(`State_of`/`State_root`/`modified`/`staged`/`Get`/`Has`)는 `Bucket_Store` 범주 API 위의 얇은 래퍼다.

---

## 영속·전이 (`store_io` 자유함수)

`store_io` 가 forest 영속을 수행한다(store 인자) — 구조 사이드카는 `Structure` 핸들러, payload 는 `handler`
위임. 데이터모델 `Bucket_Store` 는 I/O 를 모른다(호출측이 `store_io.X(meta, …)` 를 직접 부른다).

**구조(JSON).** stem 서브트리(`Serialize`)를 top(params) + per-stem 사이드카로 **분산** 저장한다(항목을
사이드카로 흩어, 20k+ 프레임에서 한 stem 편집이 한 파일 즉시 쓰기가 되게).

**payload(파일).** 이미지·배열 등 실제 payload 의 이동/복사/삭제는 `handler` 가 한다. 전이는 payload op
(handler) + 버킷 조정 + 구조 재저장(`Save_item`)을 엮는다.

```text
{root}/.meta/dataset_meta.json     top — params(범주 무관 root leaf)
{root}/{state}/.meta/{stem}.json   per-stem 사이드카 — 그 stem 서브트리 (구조)
{root}/{state}/{dir}/{stem}.png    payload — handler 가 경로 파생 (dir=info 키 or info.dir)
{root}/annotation.json             Gather — staged 를 뭉친 자기완결 번들
```

`store_io` 는 두 축으로 나뉜다 — **구조 write**(`Scatter`/`Save_item`/`Save_top`/`Gather`, 전량 vs 증분
vs 번들)와 **전이**(`Move`/`Copy`/`Delete`/`Merge`, 버킷을 바꾸며 payload·사이드카를 함께 옮김). `Restore`
는 역방향(디스크 → 메모리). 각 함수의 인자·동작은 [`../store_io.py`](../store_io.py) docstring 이 소유한다.

핵심은 이 함수들이 **store 를 인자로 받는 자유함수**라는 것 — 데이터모델이 I/O 를 모르고, 호출 측(GUI·
학습 코드)이 `store_io.Move(meta, …)` 를 직접 부른다. 증분 저장(`Save_item`)이 first-class 라 20k+
프레임에서 한 stem 편집이 한 파일 write 로 끝난다("하나 바뀌었다고 전체 내보내기" 없음).

---

## 라이프사이클 — raw → 학습 annotation

```text
① Convert   raw 탐색 → modified 에 stem 등록      (../converter + store_io.Scatter)
② Run       flow 로 mask/segment/bbox 채움         (../process, modified)
③ Verify    GUI 검수·수정 → 맞으면 staged 로       store_io.Move(meta, stem, "staged")
④ Gather    staged 를 뭉쳐 annotation.json 생성    store_io.Gather(meta)
⑤ 학습      annotation 로드 → 트리 순회 → handler  Restore + handler.Load
```

⑤ 소비 — annotation 을 로드해 각 leaf `Data_Ref` 를 `handler.Load` 로 실제 payload 로 푼다. class 이름 →
정수 id 는 sample 의 id_map 이 맡는다(보류).

조율(Convert/Run/Verify)은 바인더(`Pipeline`, [`../../_base.py`](../../_base.py))가 하고, meta 는
데이터 구조만 든다(영속·전이 I/O 는 [`../store_io.py`](../store_io.py)).
