# TODO — data

완료 이력은 git, 최종 설계는 [`README.md`](README.md). 여기엔 남은 것 + 열린 논의.

---

## ▶ 진행 중 — gui 소비처 sweep (core 는 끝)

core(process·converter·sampler·바인더)는 새 API 로 전환됐다. **gui 만 남았다** — `import gui` 는 되지만
런타임 코드가 옛 API 를 쓴다:

- `Data_Ref(type="stem"/"attr", …)` → `Data_Ref(info=…)` / `Data_Ref(format=("attr","str"))`.
- `.Is_stem()` → `.Is_branch()` (또는 `Leaves()`/`Branches()` — leaf/컨테이너 필터는 이제 `Data_Ref` 가 답한다).
- `.type == "segmap"` → `.format[:1] == ("segmap",)`.
- `Category_of`·`Category_root`·`Iter_category` 삭제 → `store.Find(key)` / `store.Bucket(cat)`, handler
  I/O 는 `(root, path_tuple, name, ref)`.
- `info["dir"]` 삭제 → 경로는 트리 위치에서 파생 (`handler.Path_of` 로 물어볼 수 있다).
- 없어진 것: `SAMPLE_SINKS`, `Classification_Set`/`Detection_Set` (파생 store 는 `Sample_Set` 하나).

**`sample/_sample_view` 는 의미가 바뀐다** — class 가 attr 이라 재분류가 파일 이동(crop 재저장 + 옛 파일
삭제 + 노드 이동 + 사이드카 2개 rewrite)이 아니라 **`ref.Set_attr("class_id", …)` + `Save(sample)`** 다.
트리도 class→sample 2단이 아니라 split 별 sample 목록(class 는 attr 로 group-by).

`WORKING` 은 이 sweep 이 끝나면 `constant.py`·`data/sample/__init__` 에서 제거한다 (모델엔 이미 없다).

---

## ✅ 합의됨 (진행 전)

### 마이그레이션 스크립트 — 옛 저장본 → 지금 레이아웃

- [ ] 사이드카 flat `.meta/{key}.json` → `.meta/{최상위}/{key}.json`, payload `{dir}/{key}.{ext}` →
      **kind-major** `{범주}/{종류}/{stem}.{ext}`. `Restore` 가 이제 모양 안 맞는 사이드카에 **fail-loud**
      하므로(조용히 안 버림), 옛 저장본은 이 스크립트 없이는 안 열린다.

---

## ✅ 결론 난 논의 — cv2-free 경계  → **`Data_Ref` 를 `core/schema` 로 승격** (2026-07-12)

**답이 나왔고, 이 진단이 core 4분할 전체의 근거가 됐다** — 상위 계획 [`../TODO.md`](../TODO.md) "★ core 4분할".

**오진이었던 것.** 아래 항목은 `handler/__init__` 의 eager 자동등록을 원인으로 지목했지만, 진짜 원인은
**cv2-free 를 잘못된 계층에 요구한 것**이다. 그건 `Data_Ref` **한 모듈**의 성질인데 `data/` **계층 전체**의
계약으로 승격시켰고, 그 결과 `Bucket_Store` 가 영속을 하면서 영속을 모르는 척해야 했다(→ 메서드 본문
안 handler 지연 import 5개). 이 위장의 어색함이 *"라이프사이클이 store 에 있으면 안 되나 보다"* 라는
2차 오진을 낳아 `store_io` 분리(`843975b`)→재흡수 왕복까지 갔다.

**처방 — 책임을 옮기지 말고 순수한 것을 꺼낸다.** `Data_Ref` → `core/schema.py`(의존 0). 그러면 cv2-free
소비자는 그것만 들이면 되고, `Bucket_Store` 는 `port` 를 **top-level 로** 당길 수 있다(지연 import 소멸).
**라이프사이클은 store 소유 그대로**다 — 규칙은 옳았다. (원칙: `claude-knowledge` 계층① "순수성은 모듈에
걸고 계층에 걸지 않는다".) 아래 "`Data_Ref` 재노출 중단"은 그 이동으로 자연히 달성된다.

<details><summary>원래 논의 (근거 보존)</summary>

### handler: `__init__` eager 자동등록이 cv2-free 경계를 무력화한다

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

</details>
