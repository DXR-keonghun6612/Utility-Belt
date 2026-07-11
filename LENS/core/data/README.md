# data

LENS **데이터 계층** — 데이터가 어떤 모양으로 담기고, 어떻게 디스크와 오가는지를 소유한다.
`core` 의 두 축 중 **데이터**(다른 축은 계산 = [`../process`](../process)). 계산은 이 계층 위에서
값을 읽고 쓰기만 하고, 표현·영속의 책임은 여기 있다.

---

## 1. 데이터모델 — `Data_Ref` 하나로 재귀하는 트리

노드 클래스가 없다. 트리 전체가 **단일 재귀 타입 `Data_Ref`** 로 표현되고, kind 는 **`format` 이 비었는지**로
갈린다 — 별도 타입 필드가 없다:

- **BRANCH** (`format` 비었음) — `info` 가 자식 `dict[str, Data_Ref]`. 재귀 컨테이너. 이름은 부모 `info` 의 key.
- **LEAF** (`format = (handler, detail)`) — payload 서술자. `info` 는 인라인 값(`{value}`) 또는 파일 위치(`{dir}`).
  실체화(read/write·경로 파생)는 `handler` 가 `format[0]` 로 디스패치한다.

**LEAF 는 디스패치용 handler 가 반드시 있어 `format` 이 비지 않고, BRANCH 는 없어 항상 빈다** — 그래서
`bool(format)` 이 곧 kind 다. class_id·bbox 같은 인라인 라벨도 특별한 종류가 아니라 그냥 `("attr", …)` LEAF 이고,
rgb 와 같은 층위의 데이터로 `info` 안에 산다.

---

## 2. 범주는 데이터가 아니라 **트리 구조 key**

`modified`/`staged`/`skipped`·`train`/`val`/`test` 같은 **범주**는 item 의 속성이 아니라 **트리에서의 위치**다.
`tree` 는 단일 BRANCH 이고, 그 최상위 `info` 키가 `params` + 범주들이다. 각 범주 branch 의 자식이 item 이다:

```
tree (BRANCH)
├─ params            # 범주 무관 root leaf (dataset-wide 값)
├─ modified          # ← 범주 = 최상위 key
├─ staged
│   └─ frame0        # item = staged/frame0 (BRANCH)
│       ├─ rgb       : LEAF (image,png)              # 프레임 payload
│       ├─ "0"       : BRANCH                        # 객체 0
│       │   ├─ seg      : LEAF (rle, …)
│       │   └─ class_id : LEAF (attr,str)  value=dog # 인라인 라벨도 그냥 데이터
│       └─ "1"       : BRANCH …
└─ skipped
```

- **범주 전이(`Move`) = 범주 key 사이 pop→push** — 데이터를 안 건드리고 트리 위치만 바꾼다.
- **한 item 은 한 범주에만** — 트리 key 유일성으로 자연히 성립(중복이 구조적으로 불가능).
- **export 는 서브트리 serialize** — 라이브 트리가 이미 범주별로 나뉘어 있어 group-by 파생이 필요 없다.

범주를 label(item 필드)이 아니라 구조로 둔 이유: 범주는 유저 편의를 위한 **분류**이고, 영속 경로가
**재귀 key 뭉치기**(→ 4절)라 범주 key 가 그 경로에 자연히 실린다.

---

## 3. 두 범위 — 노드(`Data_Ref`) vs 컬렉션(`Bucket_Store`)

경계는 "모델 vs I/O" 가 아니라 **"한 노드의 자기 범위 vs 전체 컬렉션·정책 범위"** 다.

- **`Data_Ref`** ([`data_ref.py`](data_ref.py)) — 한 노드가 자기 subtree 를 다루는 순수 트리 연산: 자식 CRUD·경로
  탐색·재귀 순회·복제·병합·inline 값·직렬화. **저장·정책을 모른다** — `handler` 를 import 조차 안 해서(단방향),
  데이터모델만 필요한 소비자가 cv2·registry 없이 이 파일 하나만 들일 수 있다(cv2-free 코어).
- **`Bucket_Store`** ([`bucket_store.py`](bucket_store.py)) — 어떤 항목이 무슨 범주로 있고 어떻게 저장·교환되나:
  범주 정책(진입·전이)·영속·병합. 트리 기계는 재구현 안 하고 `tree`(Data_Ref)의 재귀 연산을 쓴다.

payload I/O 는 `handler` 소유고, `Bucket_Store` 가 트리 순회(`Iter_leaves`)로 얻은 **key-path 를 handler 에 넘겨**
파일을 옮긴다 — 경로 파생은 handler 가, handler 선택·오케스트레이션은 store 가. `Data_Ref` 는 이 사이에 안 낀다.

---

## 4. 영속 — 재귀 key-path (경로 = 트리 위치)

디스크 레이아웃이 트리 위치를 그대로 반영한다 — 경로가 곧 root 부터 뭉친 key 시퀀스다:

```
{root}/.meta/<*keys>.json          # 구조 사이드카 — item.Serialize() (예: .meta/staged/frame0.json)
{root}/<*keys>/{name}.{ext}        # payload 파일 (예: staged/frame0/0/seg.rle) — 생산 때 handler 가 씀
{root}/bundle.json                 # Export — 범주별 자기완결 번들 (hand-off)
```

- **사이드카는 per-stem 백업** — item 하나가 파일 하나라, 20k+ 프레임에서 한 편집이 한 write 다(증분·크래시 내구).
- **payload 는 범주 경로 아래** — 전이(`Move`)가 payload 도 새 범주 경로로 함께 옮긴다(handler 가 `shutil` 이동).
  인라인 LEAF(attr/rle)는 값이 사이드카 안이라 파일 이동이 no-op.
- **복원은 `.meta` 트리 walk** — 경로 key 시퀀스가 곧 트리 위치라, walk 결과를 그 위치에 꽂으면 트리가 선다.

---

## 5. 두 구체 store

`Bucket_Store` 를 상속해 **범주 값 집합만** 고정하는 thin 서브클래스. 빌드(정본→파생)는 data 밖 계산 계층
([`../converter`](../converter)·[`../sampler`](../sampler))이 한다.

- **`Dataset_Meta`** (정본) — 범주 = staging 상태 `(modified, staged, skipped)`. [`meta/store.py`](meta/store.py)
- **`Sample_Set`** (파생) — 범주 = split `(train, val, test)`. [`sample/store.py`](sample/store.py)
  - `Classification_Set` / `Detection_Set` — task 별 트리 모양(`{class}/{sample}` vs `{image}/{object}`).

트리 **모양**(중첩 깊이)은 task(sampler sink)가 짓고, `Bucket_Store`/`Data_Ref` 는 그 깊이를 모른다 —
`info` 재귀가 임의 깊이를 흡수한다.

---

## 이웃

- [`handler/`](handler) — `Data_Ref` LEAF 를 실제 파일로 실체화하는 I/O 게이트 (`format[0]` 디스패치).
- [`../process`](../process) — 계산 계층. 이 데이터 위를 순회하며 값을 읽고(resolve) 쓴다(route).
- 상위 설계·용어는 [`../README.md`](../README.md), 잔여·열린 논의는 [`TODO.md`](TODO.md).
