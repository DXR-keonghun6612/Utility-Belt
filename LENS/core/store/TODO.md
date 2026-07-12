# TODO — store

완료 이력은 git, 최종 설계는 [`README.md`](README.md). 상위 계획은 [`../TODO.md`](../TODO.md) "★ core 4분할".

**이 계층의 계약** — 데이터 **여럿**의 관리(메모리 컬렉션 + 범주·item 주소)와 **라이프사이클 API**.
읽기/쓰기는 [`../port`](../port) 에 **요청**한다(위임하되 소유는 안 넘긴다 — 호출 측은 `meta.Move(…)`).

> **`Bucket_Store` 를 "크기"를 이유로 쪼개지 마라.** 남는 메서드는 전부 같은 지식(범주 트리 + item 주소)을
> 다루므로 한 클래스가 맞다. 크기로 나누면 `store_io` **3바퀴째**가 된다(`843975b` → 재흡수 → …).
> 줄이는 방법은 나누는 게 아니라 **죽은 걸 지우는 것**이었다(`Export`·`Get_or_add` 는 호출처 0으로 확인돼
> 사라졌다). 파일이 길면 모듈은 나눠도 클래스는 하나로 — mixin 은 계층을 문법으로 흉내내는 것뿐이다.

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

## ✅ 결론 난 논의 — cv2-free 경계 (2026-07-12)

**→ README 로 승격됨.** 왜 `Data_Ref` 를 `core/schema` 로 꺼냈고 왜 라이프사이클은 store 소유 그대로인지는
[`../README.md`](../README.md) "왜 검사까지 두는가" 가 소유한다. 결론을 지키는 장치는
[`../test_layering.py`](../test_layering.py).
