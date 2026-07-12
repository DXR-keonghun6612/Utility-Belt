# TODO — store

완료 이력은 git, 최종 설계는 [`README.md`](README.md). 상위 계획은 [`../TODO.md`](../TODO.md) "★ core 4분할".

**이 계층의 계약** — 데이터 **여럿**의 관리(메모리 컬렉션 + 범주·item 주소)와 **라이프사이클 API**.
읽기/쓰기는 [`../port`](../port) 에 **요청**한다(위임하되 소유는 안 넘긴다 — 호출 측은 `meta.Move(…)`).

---

> **경고 — "크기"를 이유로 더 쪼개지 마라.** 남는 메서드(`Set`/`Set_param`/`Find`/`Has`/`Bucket`/
> `Conflicts`/`Import`/`Save`/`Restore`/`Move`/`Delete`/`Merge`)는 전부 같은 지식(범주 트리 + item 주소)을
> 다루므로 한 클래스가 맞다. 크기로 나누면 `store_io` **3바퀴째**가 된다(`843975b` → 재흡수 → …).
> 줄이는 방법은 나누는 게 아니라 **죽은 걸 지우는 것**이었다(`Export`·`Get_or_add` 호출처 0으로 확인).
> 파일이 길면 모듈은 나눠도 클래스는 하나로 — mixin 은 계층을 문법으로 흉내내는 것뿐이다.

---

## ✅ 합의됨 — 마이그레이션 스크립트 (옛 저장본 → 지금 레이아웃)

- [ ] 사이드카 flat `.meta/{key}.json` → `.meta/{최상위}/{key}.json`, payload `{dir}/{key}.{ext}` →
      **kind-major** `{범주}/{종류}/{stem}.{ext}`. `Restore` 가 모양 안 맞는 사이드카에 **fail-loud** 하므로
      (조용히 안 버림), 옛 저장본은 이 스크립트 없이는 안 열린다.

---

## ✅ 합의됨 — gui 가 아직 `port` 를 직접 부른다

계층 규정상 읽기/쓰기는 store 가 소유하고 위 계층은 **요청**한다. core 는 끝났지만(검사가 강제) gui 는
`core/` 밖이라 검사에 안 잡힌다.

- [ ] `gui/…/edit/_overlay.py`·`edit/_segment.py`·`sample/_sample_view.py` 의 `port.Load`/`port.Path_of`
      → **`store.Resolve(path, node)`** / **`store.Path_of(path, name, ref)`** (이미 있다).

---

## ▶ 진행 중 — gui 소비처 sweep

`import gui` 는 되지만 **런타임 코드가 옛 API 를 쓴다** (core 는 끝났다):

- `Data_Ref(type="stem"/"attr", …)` → `Data_Ref(info=…)` / `Data_Ref(format=("attr","str"))`.
- `.Is_stem()` → `.Is_branch()` (또는 `Leaves()`/`Branches()`).
- `.type == "segmap"` → `.format[:1] == ("segmap",)`.
- `Category_of`·`Category_root`·`Iter_category` 삭제 → `store.Find(key)` / `store.Bucket(cat)`.
- `info["dir"]` 삭제 → 경로는 트리 위치에서 파생 (`port.Path_of` 로 물어볼 수 있다).
- `meta.Gather(…)` → **삭제**(위 참조). `Get_or_add` → 삭제.

**`sample/_sample_view` 는 의미가 바뀐다** — class 가 attr 이라 재분류가 파일 이동이 아니라
**`ref.Set_attr("class_id", …)` + `Save(sample)`** 다. 트리도 class→sample 2단이 아니라 split 별 sample
목록(class 는 attr 로 group-by). 끝나면 `WORKING` 상수 제거.

(import 경로는 이미 정정됨 — `core.schema` / `core.store` / `core.port`.)

---

## ✅ 결론 난 논의 — cv2-free 경계 → **`Data_Ref` 를 `core/schema` 로 승격** (2026-07-12)

> README 승격 대기 (문서 패스). 이 진단이 core 4분할 전체의 근거다.

**오진이었던 것.** 원인으로 지목됐던 건 `handler/__init__` 의 eager 자동등록이었지만, 진짜 원인은
**cv2-free 를 잘못된 계층에 요구한 것**이다. 그건 `Data_Ref` **한 모듈**의 성질인데 `data/` **계층 전체**의
계약으로 승격시켰고, 그 결과 `Bucket_Store` 가 영속을 하면서 영속을 모르는 척해야 했다(메서드 본문 안
handler 지연 import 5개). 그 위장의 어색함이 *"라이프사이클이 store 에 있으면 안 되나 보다"* 라는 2차
오진을 낳아 `store_io` 분리(`843975b`)→재흡수 왕복까지 갔다.

**처방은 책임 이동이 아니라 순수한 것의 승격.** `Data_Ref` → `core/schema.py`(의존 0). 그러면 cv2-free
소비자는 그것만 들이면 되고, `Bucket_Store` 는 `port` 를 **top-level 로** 당길 수 있다.
**라이프사이클은 store 소유 그대로** — 규칙은 옳았다.
