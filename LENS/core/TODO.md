# TODO — core

완료 이력은 git, 최종 설계는 각 `README.md`. 여기엔 **폴더를 가로지르는 계획**만 — 폴더 안에서 닫히는
항목은 각 폴더 TODO 가 소유한다: [`port`](port/TODO.md) · [`store`](store/TODO.md) ·
[`process`](process/TODO.md).

---

## ★ core 4분할 — schema / port / store / process

계층은 하는 일이 아니라 **아는 타입**으로 갈린다.

```text
core/schema.py    Data_Ref — 서술. 아무것도 모른다 (의존 0 · 진짜 cv2-free). 모두가 쓴다.
core/port/        데이터 하나의 실체화(읽기/쓰기) + 외부 발견. schema 만 안다. store 만이 부른다.
core/store/       데이터 여럿의 관리(메모리 컬렉션) + 라이프사이클 API. 읽기/쓰기는 port 에 요청.
core/process/     연산과 결과의 흐름. 데이터는 store 에만 요청.
core/_base.py     Pipeline — 계산 단계 조율만.
```

**경계는 산문이 아니라 [`test_layering.py`](test_layering.py) 가 강제한다** — ① 아래 계층이 위 계층을
import 하면 실패 ② `core.schema` 만 들였을 때 cv2·numpy 가 안 딸려와야 통과. 이 검사가 있는 한 계층은
살아 있다. (왜 이 검사가 필요했는지는 [`store/TODO.md`](store/TODO.md) "cv2-free 경계" — 같은 경계를
두 바퀴 돌았다.)

**끝난 것 — 4분할 + 리팩토링 전부.**

- [x] source/sink 계약 해체(`88e5477`) → `Stage` 엔진 + 서브클래스 2개.
- [x] 재배치 — `schema`/`port`/`store`/`process`, `converter`·`sampler` 소멸, 계층 검사 도입.
- [x] **port** — `ingest.py` 해체(`Scan`→`scan.py`, `_spec_ref`→`Template_for_file`) + `handler/` 평탄화.
- [x] **store** — `Import` 추가(`Restore`/`Merge` 의 형제) · 죽은 메서드 삭제(`Export`·`Get_or_add`·
      `Iter`→`_iter`) · export → `sample/export/` **task 별 파일** + `Sample_Set.Export` ·
      읽기/쓰기 창구(`Resolve`/`Route`/`Param`/`Path_of`).
- [x] **process** — `port` 직접 호출 제거(전부 store 경유) · 죽은 `Analysis` 계약 삭제.

**남은 것**

- [ ] **`analysis/` 계산을 `func/` 로** — 계약은 죽였지만 **모듈 이사는 안 했다**. 계산(align·features·
      polar·stats) → `func/`, chroma 진단 → params 읽는 자유함수, shape 군집 → 산출물 소비자.
      소비처가 gui(`sample/_tab.py`)라 gui sweep 과 함께 가는 게 안전하다. → [`process/TODO.md`](process/TODO.md)
- [ ] **gui 가 아직 `port` 를 직접 부른다** (`_overlay`·`_segment`·`_sample_view`) — `store.Resolve`/
      `store.Path_of` 로 옮긴다. 계층 검사는 `core/` 만 보므로 안 잡힌다. → [`store/TODO.md`](store/TODO.md)
- [ ] **문서 패스** (마지막) — 아래.

---

## 문서 소유권 (누가 무엇을 적는가)

**같은 사실을 두 곳에 쓰지 않는다.** `core/README.md` 가 data 내부를 중복 서술한 것이 지난번 문서가 썩은
원인이었다 — 사본만 조용히 거짓이 됐다. 지금 경계는 이렇다:

| 무엇 | 어디 |
|---|---|
| 트리 모델(BRANCH/LEAF, `bool(format)` 이 곧 kind) | [`schema.py`](schema.py) docstring — **한 심볼 안에서 닫힌다** |
| payload 경로 규칙(kind-major) · handler 계약 · `Route` | [`port/README.md`](port/README.md) |
| 범주 = 구조 key · item 주소 · 사이드카 · 라이프사이클 | [`store/README.md`](store/README.md) |
| 엔진 · ctx 스코프 · port↔slot · carry/finalize · stream↔func 경계 | [`process/README.md`](process/README.md) |
| 계층 지도 · 의존 방향 · 바인더 | [`README.md`](README.md) — **내부는 안 적고 가리킨다** |

- **워크플로는 README 가 아니다** — 여러 단계에 걸친 흐름은 문서에 적으면 썩는다. `select/README.md` 의
  yaml 예시를 지운 이유다(내용은 이미 `gate.py`·`center.py` docstring 에 있었다).
- **결론 난 논의는 README 로 승격**했고 각 TODO 엔 포인터만 남겼다 — 지우면 **왜 그렇게 정했는지가
  증발한다.**

---

## ✅ 합의됨 — 부채

- [ ] **`DEFAULT_RATIOS`(0.8/0.1/0.1)가 한 번도 적용되지 않는다** — `Pipeline.Sample` 이
      `ratios=_cfg.get("ratios") or {}` 로 **빈 dict 를 명시 전달**해 dataclass 기본값이 늘 덮인다.
      `_norm_ratios({})` → 합 0 → **균등 1/3**(레시피에 `ratios` 가 없으면 항상). 검증에서 3 stem →
      train 0 / val 2 / test 4 로 관측. **리팩터 이전부터 그랬다** — 동작 보존을 위해 그대로 뒀다.
      고치면 split 배정이 바뀌어 기존 tasker 재빌드 시 데이터가 이동하므로 **의도적 결정이 필요**하다.
- [ ] **`excluded` 큐레이션 영속** (파생 = 순수 재생성 + 솎아내기).
- [ ] **GUI end-to-end 런타임 검증** — 실제 데스크톱에서 Convert→Run→전이→Sample→뷰어 흐름.
- [ ] coco/yolo 포맷 ingest (glob 외 직접 파싱 경로).

---

## ❓ 논의 대상

- [ ] **id_map 소유권** — id_map 은 detection 내보내기(파생) 소유인데 정본 `params` 에 얹혀 있어 계층과
      어긋난다. 정본은 class **이름**만 들게 두고 id_map 을 tasker 레시피로 내릴지 결정(내리면 gui 표시도
      sample 로 이동).
