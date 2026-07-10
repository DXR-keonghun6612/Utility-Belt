# sample (store)

파생(derived) 스테이지의 **데이터 구조·영속**만 소유한다 — `Sample_Set`(`Bucket_Store`, 범주 = split).
정본→파생 **빌드는 [`../../sampler`](../../sampler)** 가 한다(meta store↔converter 대칭으로 sample
store↔sampler). 공유 컨테이너·leaf 는 [`../schema.py`](../schema.py), payload I/O 는 [`../handler`](../handler).

---

## Sample_Set — 단일 작업 버킷 (split 도 depth 도 모른다)

`Bucket_Store`(forest 파사드)를 상속해 **범주(`CATEGORIES`) = 단일 작업 버킷(`WORKING`)** 하나만 고정한다.

- **split 은 store 범주가 아니라 내보내기 산출물이다.** 분석·class 재배정은 split 을 몰라도 되므로
  (class 이동뿐) 작업 store 는 버킷 하나만 두고, train/val/test 는 작업이 끝난 뒤 frame stem 해시로 갈라
  `{split}/…` 로 실체화한다([`../../sampler`](../../sampler) 의 `Sample_sink.Export`).
- root 규약 = `{dataset_root}/sample/{tasker}` (정본 root 아래 파생 서브트리, `SAMPLE_DIR`="sample").
  tasker(이름 붙은 파생) 목록·설정은 `{dataset_root}/sample/taskers.yaml` — 빌드·조율은 [`../../sampler`](../../sampler).
- 버킷 안의 **트리 모양은 task(sampler)가 정한다** — classification 은 class(그 안에 sample 중첩),
  detection 은 image(그 안에 object 중첩). `Sample_Set` 은 그 의미도 depth 도 모른다 — `Data_Ref` stem
  중첩이 임의 깊이를 흡수하고, 사이드카 영속이 그 중첩을 재귀 직렬화로 담는다.
- 영속(`Scatter`/`Save_item`/`Restore`)·전이·번들(`Gather`)은 전부 [`../store_io.py`](../store_io.py) 자유
  함수 — 정본과 **완전히 같은 per-item 사이드카 메커니즘**이라 sample 전용 영속 코드가 없다.

---

## 구성

```text
sample/
├── _base.py    Sample_Set(Bucket_Store) + SAMPLE_DIR·SPLITS (store 규약 상수)
└── __init__.py
```

빌드(누가 이 트리를 채우나)는 여기 없다 — [`../../sampler`](../../sampler)의 `Sample_sink[task]` 가
`process` Stage 엔진으로 staged 정본을 순회하며 배치한다. leaf 는 **A+ 역참조**(`source_stem`/`source_obj`)
가 기본이고, crop 체인을 끼우면 crop payload(`{split}/{dir}/{id}.png`)를 **실체화**해 `info["crop"]` 에
단다(재생성 가능한 파생 — class 등 정본 attr 은 여기서 안 씀).
