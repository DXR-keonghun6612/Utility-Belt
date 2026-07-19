# TODO — core

완료 이력은 git, 최종 설계는 각 `README.md`. 여기엔 **폴더를 가로지르는 계획**만 — 폴더 안에서 닫히는
항목은 각 폴더 TODO 가 소유한다: [`port`](port/TODO.md) · [`store`](store/TODO.md) ·
[`process`](process/TODO.md).

---

## ★ 축 정리 잔여 — port 이름 · segmap 접기 · format/mask

축 정리(`format`·`codec`·`func` 를 top-level 로 분리 + **대표 포맷 제거** + bbox 1급 포맷)는 **코드에
들어왔고 계층 검사도 통과한다.** 그 설계는 [`port/README.md`](port/README.md) 와 [`format`](format)·
[`codec`](codec) 패키지 docstring 이 소유한다 — 여기엔 마무리 몇 조각만 남는다:

- [ ] **⑤ port 파사드 정리** — `scan.py`·`_structure.py`(`Structure`)를 port 밖 제자리로 옮길지.
      scan 은 fs 발견(pathlib 만), `Structure` 는 `Data_Ref` 트리 사이드카(codec 에 가깝다).
      **`port → domain` 개명은 미결** (❓ 아래).
- [ ] **segmap 접기** — `raster_domains.Segmap_Domain`(형제 도메인) → `mask` 도메인의 한 포맷.
      라벨맵은 mask 여럿을 겹쳐 담은 저장 표현일 뿐이라 카디널리티가 도메인을 안 가른다. 대표 포맷이
      있을 때 "라벨맵을 rle 로"가 정의 불가로 보였던 건 인자 받을 자리가 없어서였고, 이제 `Mask_of(맵,
      obj_id)` 로 선다. 남은 `int(id)+1`(store/meta·export·gui 렌더)을 이때 `func.mask` 단일 소유로.
- [ ] **`format/mask`** — `func/mask/instance.py`(라벨맵↔obj mask 합성)를 `format/mask/` 로.
      구조 연산이라 format 소속이 맞다(`func` 는 구조 무관 계산).
- [ ] **bbox 마이그레이션 검증** — 옛 `("bbox","list")` → `("region","bbox","xyxy")` 가 정본 데이터에
      남았는지 확인 (`scripts/migrate_format_taxonomy.py`).

## ★ `analysis/` 를 flow 로

계약은 죽였지만 **모듈 이사는 안 했다** — 계산 → `func/`, feature/cluster 두 flow 로. 다중 범주 순회는
준비됐다(carry 가 split 경계를 넘는다). → [`process/TODO.md`](process/TODO.md)

---

## 문서 소유권 (누가 무엇을 적는가)

**같은 사실을 두 곳에 쓰지 않는다.** `core/README.md` 가 내부를 중복 서술한 것이 지난번 문서가 썩은
원인이었다 — 사본만 조용히 거짓이 됐다. 지금 경계는 이렇다:

| 무엇 | 어디 |
|---|---|
| 트리 모델(BRANCH/LEAF, `bool(format)` 이 곧 kind) | [`schema.py`](schema.py) docstring — **한 심볼 안에서 닫힌다** |
| 데이터 **구조** + 그 연산 (bbox·polygon·rle, 대표 포맷 없음) | [`format`](format) 패키지 docstring |
| 포맷 단위 **직렬화** (raster·npy·inline·docs) | [`codec`](codec) 패키지 docstring |
| domain × format 디스패치 · 경로 규칙(kind-major) · `Route` · 발견 | [`port/README.md`](port/README.md) |
| 범주 = 구조 key · item 주소 · 사이드카 · 라이프사이클 | [`store/README.md`](store/README.md) |
| 엔진 · ctx 스코프 · port↔slot · carry/finalize · stream↔func 경계 | [`process/README.md`](process/README.md) |
| 계층 지도 · 의존 방향 · 바인더 | [`README.md`](README.md) — **내부는 안 적고 가리킨다** |

- **워크플로는 README 가 아니다** — 여러 단계에 걸친 흐름은 문서에 적으면 썩는다. `select/README.md` 의
  yaml 예시를 지운 이유다(내용은 이미 `gate.py`·`center.py` docstring 에 있었다).
- **결론 난 논의는 README 로 승격**하고 각 TODO 엔 포인터만 남긴다 — 지우면 **왜 그렇게 정했는지가
  증발한다.**

---

## ✅ 합의됨 — 부채

- [ ] **`DEFAULT_RATIOS`(0.8/0.1/0.1)가 한 번도 적용되지 않는다** — `Pipeline.Sample` 이
      `ratios=_cfg.get("ratios") or {}` 로 **빈 dict 를 명시 전달**해 dataclass 기본값이 늘 덮인다.
      `_norm_ratios({})` → 합 0 → **균등 1/3**(레시피에 `ratios` 가 없으면 항상). 검증에서 3 stem →
      train 0 / val 2 / test 4 로 관측. **리팩터 이전부터 그랬다** — 동작 보존을 위해 그대로 뒀다.
      고치면 split 배정이 바뀌어 기존 tasker 재빌드 시 데이터가 이동하므로 **의도적 결정이 필요**하다.
- [ ] **`Verify` 단계 구현** (`Pipeline.Verify`) — 바인더의 마지막 계산 단계, 아직 미구현.
- [ ] **`excluded` 큐레이션 영속** (파생 = 순수 재생성 + 솎아내기).
- [ ] **GUI end-to-end 런타임 검증** — 실제 데스크톱에서 Convert→Run→전이→Sample→뷰어 흐름.
- [ ] coco/yolo 포맷 ingest (glob 외 직접 파싱 경로).

---

## ❓ 논의 대상

- [ ] **`port → domain` 개명** — 세 축(format·codec·domain)이 밖으로 나간 지금 이 계층에 남는 건 "무엇으로
      읽나 + 검증·정책 + 디스패치"라 이름이 `domain` 에 가깝다. 코드는 개명 대신 `domain/` 을 port 하위에
      두고 port 를 파사드로 남기는 길로 갔다 — 이대로 굳힐지, 개명할지 미결.
- [ ] **`docs` 핸들러의 자리** — 중첩 구조(yaml/json)를 담는데 `Structure`(사이드카)와 역할이 겹친다.
      docs codec 인지, `Structure` 로 흡수되는지 → [`port/TODO.md`](port/TODO.md).
- [ ] **id_map 소유권** — id_map 은 detection 내보내기(파생) 소유인데 정본 `params` 에 얹혀 있어 계층과
      어긋난다. 정본은 class **이름**만 들게 두고 id_map 을 tasker 레시피로 내릴지 결정(내리면 gui 표시도
      sample 로 이동).
