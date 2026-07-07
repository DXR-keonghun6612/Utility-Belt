# sample

> ⚠️ **보류 (v0.0.1).** 이 계층은 아직 flat `Data_Ref` 스키마로 재설계·마이그레이션되지 **않았다** —
> `store.py`/`sampler.py` 는 옛 `Node` API 기준이라 현재 import 체인에서 빠져 있고, `Pipeline.Sample()`
> 은 `NotImplementedError` 다. 아래는 **타깃 설계 스케치**이며, 실제 코드는 flat 전환 후 복구 대상.

파생(derived) 스테이지 — **staged 정본(`Dataset_Meta`)을 소비해 task별 학습셋으로 파생**한다.
데이터 구조(`Sample_Set`)와 그 영속(`store`) + 정본→파생 빌드(`sampler`)를 소유한다.

`data` 계층의 두 구체 스테이지 중 파생 쪽(정본은 [`../meta`](../meta)). 공유 컨테이너·leaf 는
[`../schema.py`](../schema.py), payload I/O 는 [`../handler`](../handler).

---

## 구성

```text
sample/
├── store.py     Sample_Set(Bucket_Store) + 영속(Load/Scatter) + Place/Iter_samples
├── sampler.py   Task_Sampler(계약) + Classification_Sampler (staged meta → Sample_Set)
└── __init__.py
```

---

## Sample_Set — split → class → sample 중첩

`Bucket_Store`(= root `Node`)를 상속해 **범주(`CATEGORIES`) = split** 을 고정하고, 트리를 3단으로
중첩한다.

```python
class Sample_Set(Bucket_Store):
    CATEGORIES = ("train", "val", "test")   # split = top children
```

- **split**(top) → **class**(split 의 children) → **sample**(class 의 children, leaf).
- **class 는 sample 의 위치**(부모 key)로 산다 — classification 의 class 폴더 구조
  (`{root}/{split}/{class}/{id}`)와 1:1. sample leaf 는 payload + `(stem, obj_id)` **정본 역참조**만
  `data` 로 든다(원본 진실은 정본에만).
- `Place(split, class, sample_id, node)` 가 class 노드를 on-demand 생성하며 3단에 꽂고,
  `Iter_samples()` 가 `(split, class, sample_id, Node)` 로 순회한다. 주소는 `Search((split, class,
  sample_id))`(중첩 leaf). 구조 조작(Search/Push/Pop, Bucket/Category_root, Iter_refs)은 `Bucket_Store` 상속.

### 영속 — manifest 한 장

정본과 달리 파생은 **순수 재생성(A+) + `excluded` 큐레이션**이라, 증분 사이드카가 아니라 **단일
manifest** 로 족하다.

```text
{root}/samples/sample_set.json    전체 트리(split→class→sample) 한 장
{root}/samples/{split}/{class}/…  sample payload (crop 등, handler)
```

- `store.Load(dataset_root)` — `samples/sample_set.json` 복원(없으면 빈 Sample_Set).
- `store.Scatter(sset)` — 전체 트리를 manifest 한 장으로 기록.

---

## Task_Sampler — 정본 → Sample_Set 빌드

`Build(meta)` 가 staged 순회·배치를 소유하고, **task 서브클래스는 `Assign` 만 변주**한다.

```python
class Task_Sampler(ABC):
    unit: str = "object"          # frame | object — 순회 단위
    def Assign(self, stem, obj_id, node) -> (split, class, sample_id, sample) | None: ...
    def Build(self, meta) -> Sample_Set: ...   # staged 순회 → Assign → Place (재생성)
```

- **`Classification_Sampler`** — 단위(object|frame)마다 한 sample. class = 단위의 `class_id`,
  split = sample_id 해시로 `ratios` 에 **결정적 배정**(재실행 안정). sample 은 `(stem, obj_id)` 역참조.

---

## Pipeline 단계

`Pipeline` 은 `self.meta`(정본) + **`self.sample`(파생)** 을 함께 들고, 파생을 한 **단계**로 돌린다:

```text
Convert → Run → [staging 전이는 store] → Sample() → Verify
```

`Pipeline.Sample()` = `Task_Sampler.Build(staged meta)` → `Sample_Set` 재생성 → `store.Scatter`.
설정은 `Pipeline_config.sample`(task·split ratio), 빌드는 `_build_sampler` 팩토리(converter 대칭).

---

## 미구현 (다음 단계)

- **crop 실체화** — 지금 sample 은 `(stem, obj_id)` 역참조만 든다. `Base_Process` 체인
  (`frame_crop`/`normalize`)을 재사용해 crop 을 `{split}/{class}/{id}`(handler)로 떨궈 `sample.data`
  에 `crop` ref 를 넣는 단계가 남았다.
- **`excluded` 큐레이션** 영속 (A+ = 재생성 + 솎아내기).
- detection/seg task sampler (classification 다음).
