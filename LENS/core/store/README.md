# store

**무엇이 어느 범주로 있나 + 라이프사이클.** 데이터 **여럿**의 관리(메모리 컬렉션)와, 그 컬렉션에 일어나는
일(들이기·전이·삭제·병합·영속·내보내기)을 소유한다.

트리 기계는 [`../schema.py`](../schema.py) 가, payload 실체화는 [`../port`](../port) 가 든다 — 여기는
**어떤 항목이 무슨 범주로 있고 어떻게 오가나**만 안다. 읽기/쓰기는 port 에 **요청**한다(`Resolve`/`Route`).

각 심볼의 인자·반환은 그 심볼의 docstring 에 있다. 이 문서는 **심볼 사이에 걸치는 것**만 다룬다.

---

## 1. 범주는 데이터가 아니라 **트리 구조 key**

`modified`/`staged`/`skipped` · `train`/`val`/`test` 같은 **범주**는 item 의 속성이 아니라 **트리에서의
위치**다. `tree` 는 단일 BRANCH 이고 그 최상위 key 가 `params` + 범주들이다. 각 범주 branch 의 자식이 item:

```text
tree
├─ params            # 범주 무관 root leaf (dataset-wide 값)
├─ modified          # ← 범주 = 최상위 key
├─ staged
│   └─ frame0        # item = staged/frame0
│       ├─ frame     : LEAF (image,png)               # 프레임 payload (base)
│       ├─ segment   : LEAF (segmap,png)              # 모든 객체 mask 한 장 (픽셀 = obj_id+1)
│       ├─ "0"       : BRANCH                         # 객체 0 — attr 만 (payload 없음)
│       │   ├─ class_id : LEAF (attr,str) value=dog   # 인라인 라벨도 그냥 데이터
│       │   └─ bbox     : LEAF (attr,xyxy)
│       └─ "1"       : BRANCH …
└─ skipped
```

- **전이(`Move`) = 범주 key 사이 pop→push** — 데이터를 안 건드리고 트리 위치만 바꾼다.
- **한 item 은 한 범주에만** — 트리 key 유일성으로 자연히 성립(중복이 **구조적으로** 불가능하다).
- **범주별 조회에 group-by 가 없다** — 라이브 트리가 이미 범주로 나뉘어 있다.
- **객체는 payload-free** — geometry 는 frame-level `segment` 한 장(픽셀 = obj_id+1)이 소유하고, 객체
  BRANCH 는 인라인 attr(class_id·bbox)만 든다. per-obj mask 는 segment 에서 파생한다(`process.sample._obj_mask`).
  obj_id ↔ segment 라벨 정합은 삭제 때 `Dataset_Meta.Remove_object`(라벨 0, 구멍)가, 압축(재부여)은
  `Pipeline.Order`(process)가 지킨다.

범주를 label(item 필드)이 아니라 구조로 둔 이유: 영속 경로가 **재귀 key 뭉치기**라 범주 key 가 그 경로에
자연히 실린다(→ 3절). 즉 구조 하나가 조회·전이·경로를 동시에 만족시킨다.

---

## 2. item 이 유일한 주소 단위

**item = 범주 branch 의 직속 자식.** key 단위 API(`Find`/`Has`/`Save`/`Move`/`Delete`)는 정확히 그 자리에서만
찾는다 — item *안쪽*(객체·leaf)은 트리 내부 구조라 store 가 bare key 로 주소지정하지 않는다(그건 `Data_Ref`
몫이다). 이름이 우연히 겹쳐도 item 으로 오인하지 않는다.

**경계가 여기인 이유는 영속이다** — 사이드카·전이·조회가 전부 item 단위라, item 의 자리가 안 정해지면 그
셋이 서로 어긋난다(실제로 어긋나 있었다: 삭제한 항목이 복원 때 되살아났다).

**store 가 고정하는 건 item 의 자리까지고, item 안쪽 모양은 자유다** — `info` 재귀가 임의 깊이를 흡수하므로
`Bucket_Store` 는 그 안을 모른다. task 마다 sample 깊이가 달라도 store 타입이 안 갈리는 이유다.

---

## 3. 영속 — 경로는 트리 위치에서 파생

```text
{root}/.meta/{최상위}/{key}.json     # 구조 사이드카 — item.Serialize()  (예: .meta/staged/frame0.json)
{root}/{범주}/{종류}/{stem}.{ext}    # payload — kind-major (경로 규칙은 port 소유)
{root}/params/{종류}.{ext}           # params payload — 범주 무관이라 stem 축이 없다
```

`{최상위}` = 범주 **또는 `params`** — 둘은 트리에서 나란한 최상위 key 라 영속 경로에서도 같은 자리를 쓴다.
`Restore` 가 아는 최상위는 이 둘뿐이다.

- **사이드카는 item 하나 = 파일 하나** — 20k+ 프레임에서 한 편집이 한 write 다(증분·크래시 내구).
  그래서 `Save(key)` 가 first-class 이고 "하나 바뀌었다고 전체 내보내기"가 없다.
- **전이는 prefix 치환** — 범주가 경로 앞머리라 payload 가 사이드카를 따라 새 범주로 함께 옮겨진다.
  인라인 LEAF(attr/rle)는 값이 사이드카 안이라 파일 이동이 no-op.
- **복원은 `.meta` walk** — 경로 key 가 곧 트리 위치라 walk 결과를 그 자리에 꽂으면 트리가 선다.
  모양이 안 맞는 사이드카는 **조용히 버리지 않고 실패**한다 — 옛 저장본이면 마이그레이션([`TODO.md`](TODO.md)).

payload 경로 규칙(kind-major)은 [`../port/README.md`](../port/README.md) 가 소유한다.

---

## 4. 라이프사이클은 store 가 든다

호출 측은 `meta.Move(…)` 를 **직접** 부른다 — 오케스트레이터(바인더)를 거치지 않는다. 구조를 아는 놈이
처리까지 하면 호출 측이 한 줄로 끝나기 때문이다.

**`소유` 는 API 표면이지 구현 위치가 아니다** — store 가 port 에 위임하는 것은 위반이 아니다. 금지되는
것은 라이프사이클이 **호출 측으로 새어나가는 것**이다(`port.Move(store, key)` 를 호출 측이 부르는 순간
규칙이 깨진다).

**외부와 오가는 네 방향이 한 축의 형제다:**

| | 어디서 → 어디로 |
|---|---|
| `Restore` | 자기 레이아웃(`.meta`) → 트리 |
| `Import` | **외부 raw** → 트리 (port 가 발견, store 가 등록) |
| `Merge` | 다른 store → 트리 (충돌은 skip/overwrite/merge) |
| `Export` | 트리 → **학습 프레임워크 레이아웃** (파생만) |

`Import` 는 이미 있는 stem 을 **건드리지 않는다** — 재수집이 검수 이력(staged/skipped)을 덮어써서는 안
되므로 존재 검사가 payload write **앞**에 온다.

**읽기/쓰기 창구** — `Resolve`(leaf → 값) · `Route`(값 → leaf) · `Param` · `Path_of`. 위 계층(process)이
port 를 직접 부르지 않게 하는 자리이고, 그래서 **store 가 port 를 아는 유일한 계층**이다.

---

## 5. 두 구체 store

`Bucket_Store` 를 상속해 **범주 값 집합만** 고정하는 thin 서브클래스 — 타입이 곧 트리 모양 보장이라 병합이
같은 타입끼리만 성립한다.

- **`Dataset_Meta`** (정본) — 범주 = staging 상태 `(modified, staged, skipped)`. 새 항목과 **내용이 바뀐**
  항목은 `modified` 로 진입한다: 검수는 내용에 대한 것이라 내용이 달라지면 다시 받아야 한다.
- **`Sample_Set`** (파생) — 범주 = split `(train, val, test)`. split 은 **빌드가** 배정한다(범주가 곧 split
  이라 배치 시점에 정해져야 한다). 같은 프레임에서 나온 sample 은 한 split → leakage 방지.

**task 별 store 타입은 없다.** 빌드는 "무엇을 뽑나"(`unit`·crop 여부)만 정하고, task 는 **내보낼 때** 비로소
의미를 갖는다 — ImageFolder(class-major)든 COCO(kind-major)든 학습 프레임워크 레이아웃은 **내보내기
산출물**이지 store 구조가 아니다. task 마다 축이 배타적이라 store 가 하나를 고르면 다른 하나를 못 섬긴다.

그래서 **task 축은 파생 안쪽에만 산다** — [`sample/export/`](sample/export) 에 task 하나 = 파일 하나.
class 도 구조가 아니라 sample 의 `class_id` **attr** 이다: 폴더로도 표현하면 같은 사실이 두 곳에 살고,
재분류(라벨링 도구의 핵심 상호작용)가 attr 갱신이 아니라 파일 이동이 된다.

---

## 이웃

- [`../schema.py`](../schema.py) — 트리 노드 `Data_Ref` (BRANCH/LEAF 모델은 그 docstring 소유).
- [`../port`](../port) — payload 실체화·외부 발견. 여기가 **유일한 소비자**다.
- [`../process`](../process) — 이 데이터 위를 순회하며 값을 요청한다.
- 상위 지도는 [`../README.md`](../README.md), 잔여·열린 논의는 [`TODO.md`](TODO.md).
