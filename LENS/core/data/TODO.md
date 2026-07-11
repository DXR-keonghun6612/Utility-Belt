# TODO — data

완료 이력은 git, 최종 설계는 [`README.md`](README.md). 여기엔 남은 것 + 열린 논의.

---

## 합의됨 — 소비처 sweep (core/data 밖: gui·process·sampler·converter)

nested 재편이 backward-incompat 라 소비처가 아직 옛 API 를 쓴다 — 함께 고쳐야 앱이 산다. 대표 잔재:

- `Data_Ref(type="stem", …)` → `Data_Ref(info=…)` (``type`` 필드 없음), `.Is_stem()` → `.Is_branch()`.
- `.type=="attr"/"segmap"` → `.format[:1]==(...)`.
- 없어진 것: `Category_of`·`Category_root`·`Iter_category`(→`Bucket`)·`Gather`(→`Export`)·`Map_payload`.
  범주 조회는 `store.tree.Locate(key)`, handler I/O 시그니처는 `(root, path, name, ref)`.
- `sample/__init__` 의 `SPLITS`/`WORKING` re-export 는 소비처 편의 — `WORKING` 은 레거시(제거 대상).

호출부: gui(`_adapter`, `edit/*`, `sample/_sample_view`), process(`source`·`sink`·`stream/*`),
sampler(`source`·`sink/*`·`stage`), `converter/sink`, `analysis/temp_crop_mask`(stale — 없는 `meta.schema` import).

---

## 합의됨 — 마이그레이션 스크립트

- [ ] 옛 저장본 → nested 레이아웃. flat `.meta/{key}.json`(옛 `_state`/CATEGORY 노드, `{dir}/{key}` payload)
      → `{root}/.meta/{category}/{key}.json` + `{root}/{category}/{key}/{name}.{ext}` payload. 재사용 스크립트로.

---

## 열린 논의 — data 모델 자체

- **`Sample_Set` subclass(Classification/Detection) 유지 여부** — 트리 모양(`{class}/{sample}` vs
  `{image}/{object}`)만 다른데 그 모양은 이미 key 재귀가 흡수한다. 합칠 여지 — 근거가 sampler(빌드)에 있어 거기서 판단.

---

## 열린 논의 — handler: `__init__` eager 자동등록이 cv2-free 경계를 무력화한다

`handler/__init__` 이 `pkgutil` 로 패키지 내 전 핸들러 모듈을 **import 시점에 통째로** 올린다
(`image`→cv2, `array`→numpy …). `README` 가 약속하는 *"데이터모델만 필요한 소비자는 cv2 없이
`data_ref.py` 만 들인다"* 를 스스로 깬다:

- `handler` 를 **조금이라도** 건드리면(단일 handler 디스패치, 심지어 `Data_Ref` 재노출만 써도) 전
  핸들러의 무거운 의존이 딸려온다.
- 실제로 거의 모든 소비처가 `Data_Ref` 를 **`from core.data.handler import Data_Ref`** 로 당긴다
  (gui·process·sampler 다수) → cv2-free 는 이론으로만 존재한다.

**방향(후보, 배타적 아님).**
- **지연 등록** — `__init__` 이 전 모듈을 즉시 import 하지 않고, `Get`/`Infer_type` 이 처음 불릴 때
  해당 핸들러 모듈만 로드. "handler key X 를 쓰는데 핸들러 Y 의 의존이 안 딸려온다" 가 종료 조건.
- **`Data_Ref` 재노출 중단** — 소비처가 `data_ref` 에서 직접 가져오게 해 handler 를 우회. 재노출은
  편의였을 뿐(계약상 `Data_Ref` 는 `data_ref` 소유).

순수 트리 코어(`data_ref`)는 이미 handler 무의존이라 이 항목과 무관하게 성립 — 이건 **소비처가 그
cv2-free 를 실제로 누리게** 하는 문제다. (이 항목이 풀리면 `Bucket_Store` I/O 메서드의 handler 지역
import 도 top-level 로 승격할 수 있다.)
