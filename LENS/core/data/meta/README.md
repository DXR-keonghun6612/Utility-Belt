# meta

정본(canonical) 스테이지 — raw 에서 뽑은 **정본 annotation** 을 담고 디스크와 오간다.
데이터 구조(`Dataset_Meta`)와 그 영속·전이를 소유한다.

`data` 계층의 두 구체 스테이지 중 정본 쪽(파생은 [`../sample`](../sample), 현재 보류). 공유 컨테이너·
노드는 [`../schema.py`](../schema.py), payload/구조 I/O 는 [`../handler`](../handler), raw 수집은
[`../converter`](../converter) 가 각각 소유한다.

---

## 구성

```text
meta/
├── store.py   Dataset_Meta(Bucket_Store) — CATEGORIES + staging 편의
└── __init__.py
```

`Dataset_Meta` 는 별도 `schema.py` 없이 `store.py` 에 산다 — 영속·전이는 `Bucket_Store` 상속이라, 여기
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

## 영속·전이 (Bucket_Store 인스턴스 메서드)

`Bucket_Store` 가 forest 영속을 소유한다 — 구조 사이드카는 `Structure` 핸들러, payload 는 `handler` 위임.

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

### API

| 메서드 | 축 | 역할 |
|---|---|---|
| `Dataset_Meta.Load(root)` | 구조(read) | top + 상태별 사이드카를 읽어 복원 (root 는 위치에서 주입) |
| `Scatter()` | 구조(write) | 전체 흩기 — top + 전 사이드카 |
| `Save_item(stem)` | 구조(write) | 그 항목 사이드카 하나만 (증분) |
| `Save_top()` | 구조(write) | params(top)만 |
| `Gather(categories=["staged"]) → path` | 구조(write) | 선택 범주를 한 파일로 뭉친 자기완결 번들 |
| `Move(stem, to_state)` | 전이 | payload 이동(handler) + 버킷 이동 + 사이드카 재배치 |
| `Copy(stem, to_state)` | 전이 | **비파괴** — 원본 유지 + payload 복사(handler.Copy) + 깊은 사본 사이드카 |
| `Delete(stem)` | 전이 | payload·사이드카·버킷 제거 |
| `Merge(other, *, override=False)` | 전이 | 다른 meta 를 상태 보존해 병합 (payload 복사 + params 병합) |
| `Merge_conflicts(other) → list[str]` | 조회 | 병합 전 stem 중복 목록 (GUI 질의용) |

---

## 라이프사이클 — raw → 학습 annotation

```text
① Convert   raw 탐색 → modified 에 stem 등록      (../converter + Scatter)
② Run       flow 로 mask/segment/bbox 채움         (../process, modified)
③ Verify    GUI 검수·수정 → 맞으면 staged 로       meta.Move(stem, "staged")
④ Gather    staged 를 뭉쳐 annotation.json 생성    meta.Gather()
⑤ 학습      annotation 로드 → 트리 순회 → handler  Load + handler.Load
```

⑤ 소비 — annotation 을 로드해 각 leaf `Data_Ref` 를 `handler.Load` 로 실제 payload 로 푼다. class 이름 →
정수 id 는 sample 의 id_map 이 맡는다(보류).

조율(Convert/Run/Verify)은 바인더(`Pipeline`, [`../../_base.py`](../../_base.py))가 하고, meta 는
데이터·영속만 소유한다.
