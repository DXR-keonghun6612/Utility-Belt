# data

LENS **데이터 계층** — 데이터가 어떤 모양으로 담기고, 어떻게 디스크와 오가는지를 소유한다.
`core` 의 두 축 중 **데이터**(다른 축은 계산 = [`../process`](../process)). 계산은 이 계층 위에서
값을 읽고 쓰기만 하고, 표현·영속의 책임은 여기 있다.

---

## 무엇을 담나 — 공유 primitive + 두 구체 스테이지

```text
data/
├── schema.py    공유 데이터 구조 — Data_Ref(재귀 노드) + Bucket_Store(forest 파사드)
├── handler/     Data_Ref 실체화 — type → payload load/save/… + Structure(구조 사이드카)
├── meta/        정본 store — Dataset_Meta(Bucket_Store) + 자기 영속(top·per-stem 사이드카)
└── sample/      파생 store — Sample_Set(Bucket_Store, 범주 = split)
```

> ingest·빌드(raw→정본, 정본→파생)는 data 밖 계산 계층이 소유한다 — [`../converter`](../converter)(Convert)·
> [`../sampler`](../sampler)(Sample). data 는 **표현·영속(store)만**. (구 `data/converter`·`data/sample` 의
> 빌더는 이 두 top-level 로 승격.)

- **`schema.py`** — 공유 데이터모델. 트리는 단일 재귀 타입 `Data_Ref`(leaf/컨테이너), forest 파사드는
  `Bucket_Store`. **디스크 I/O 를 모른다** — 그래서 영속·전이가 `store_io` 로 갈라진다.
- **`handler/`** — `data` 계층의 **유일한 I/O 게이트**. `Data_Ref.type` 이 핸들러를 골라 payload 를 실제
  파일로 오간다. 스키마·스테이지·소비자(process/converter/sampler)가 이 하나를 공유해 경로·인코딩 규칙이
  한곳에만 산다.
- **`meta/`·`sample/`** — 두 구체 store. `Bucket_Store` 를 상속해 `CATEGORIES` 만 고정하는 **thin 서브
  클래스**다(정본 = staging 상태, 파생 = 단일 작업 버킷). 영속·전이는 자기가 아니라 `store_io` 가, 빌드는
  자기가 아니라 계산 계층([`../converter`](../converter)·[`../sampler`](../sampler))이 한다.

---

## 원칙

- **표현(스키마)과 실체화(handler)는 분리** — `Data_Ref` 는 **서술자**만 들고, 실제 payload 는 `handler`
  가 파일로 오간다. inline(attr/rle/bbox, 값이 `info` 에)과 file-ref 는 `Data_Ref.Is_inline()` 이, leaf 와
  컨테이너는 `Is_stem()`(=`type=="stem"`)이 가른다.
- **I/O 는 이 계층 소유 — 바인더(`Pipeline`)는 계산 단계(Convert/Run)만.** 영속(구조 사이드카)·payload
  이동·전이·병합·내보내기는 **`store_io` 자유함수**가 store 를 받아 `handler`/`Structure` 로 수행하고(데이터
  모델 `Bucket_Store` 는 I/O 를 모름), 호출 측(GUI·학습 코드 등)이 `store_io.Move(meta, …)`/`Merge`/`Gather`
  를 직접 부른다.
- **구조 영속은 흩기(`Scatter`/`Save_item`) ↔ 모으기(`Gather`) 쌍** — top(params) + per-stem 사이드카로
  흩어 저장하고(증분: 한 stem = 한 파일 = `Save_item`), `Restore` 가 다시 모아 메모리로 올린다.
- **데이터 값 덤프는 `Extract`, 구조 직렬화는 `Serialize`** (`python_toolbox.data_schema` 상속) —
  I/O 를 새로 짜지 않고 재사용한다. `Serialize` 는 중첩 `Data_Ref` 를 재귀 직렬화한다.

---

## 이웃

- [`../process`](../process) — 계산 계층. 이 데이터 위를 순회하며 값을 읽고(resolve) 쓴다(route).
- [`../_base.py`](../_base.py) — 바인더 `Pipeline`. 스테이지를 조율하되 handler 는 안 만진다.
- 상위 설계·용어는 [`../README.md`](../README.md), 잔여 작업은 [`../TODO.md`](../TODO.md).
