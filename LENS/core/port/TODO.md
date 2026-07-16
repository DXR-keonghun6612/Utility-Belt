# TODO — port

완료 이력은 git, 최종 설계는 [`README.md`](README.md). 상위 계획은 [`../TODO.md`](../TODO.md) "★ core 4분할".

**이 계층의 계약** — 데이터 **하나**의 실체화(읽기/쓰기)와 외부 세계 발견. `schema` 만 안다.
**`store` 를 모르고, `store` 만이 부른다.** ([`../test_layering.py`](../test_layering.py) 가 강제)

---

## ✅ 결론 난 논의 — `pkgutil` eager 자동등록 → **문제 아님** (2026-07-12)

**→ README 로 승격됨** ([`README.md`](README.md) "구성"). eager 가 문제였던 유일한 이유는 cv2-free 를
무력화한다는 것이었고, `Data_Ref` 가 `schema` 로 빠진 지금 port 는 떳떳하게 무거워도 된다.

---

## ✅ 완료 — port 를 domain × format 로 재조직 (2026-07-14)

> **⚠ 절반이 뒤집혔다 (2026-07-15)** — [`../TODO.md`](../TODO.md) "★ 축 정리". 축을 **가른 것**은 남고,
> 축의 **뜻**이 바뀐다: 도메인이 대표 포맷 하나(정준형)를 정해 뭉개던 것을 걷고, 구조(`core/format`)와
> I/O(`core/codec`)가 port 밖으로 나가며 `port` 자체가 `domain` 이 된다. 아래는 **그때의 근거**로 남긴다
> — 특히 "정준형 경유 변환"이 왜 합리적으로 보였는지가 뒤집는 결정의 배경이다.

**→ README 로 승격 대상** (문서 패스에서). 결정과 결과:

- **경계** — port 의 인터페이스는 `Data_Ref` 다(밖에선 `Data_Ref` 경유로만; **소비자는 store 하나** 유지).
  순수 codec 을 bare 함수로 밖에 노출하지 않는다 — 포맷 간 변환은 `Load(A)→정준형→Save(B)`.
  *(→ 뒤집힘: `Load` 가 네이티브를 내고, 변환은 도착지인 도메인이 `format/` 의 연산을 **골라서** 한다.
  "bare 노출 안 함"의 취지는 `core/format` 이 구조와 그 연산을 소유하는 것으로 대신 선다.)*
- **축 둘** — `format = (domain, format)`.
  - `domain/` = *무엇을 담나* — 유효 포맷 검증 + 정준형(`Canonicalize`) + 정책(`Claims`·`Blank`).
  - `codec/`  = *어떻게 직렬화하나* — **I/O 의 실제 범위는 도메인보다 작다**(png 읽는 법은 사진이든
    마스크든 같다). 그래서 codec 이 도메인을 넘어 재사용된다 — `raster` 하나를 image·mask·segmap 이 공유.
- **카디널리티가 도메인을 가른다** — 단일 `mask`(rle·polygon·png·npy) vs 다객체 `segmap`(라벨맵). 섞으면
  "라벨맵을 rle 로" 같은 정의 불가 변환이 생긴다. 라벨↔id 합성은 port 가 아니라 `func.mask`(배열 계산).
  *(→ 뒤집힘: `segmap` 은 도메인이 아니라 mask 의 한 포맷이다. "정의 불가"로 보였던 건 **대표 포맷이
  있어 변환이 자동**이라 인자를 받을 자리가 없었기 때문 — 실은 `Mask_of(맵, obj_id)` 로 인자가 필요한
  변환이었을 뿐이고, 변환이 요청이 되면 자연히 선다.)*
- **새 처리 구조 = 파일 하나 + 한 줄** — codec 떨구고 도메인 `FORMATS` 에 이름 추가. SAM polygon 이 그렇게
  붙었다(`codec/polygon.py`) — 폴리곤을 바로 내는 생산자도 mask 배열을 내는 생산자와 같은 도메인에 들어온다.
- **마이그레이션** — [`scripts/migrate_format_taxonomy.py`](../../scripts/migrate_format_taxonomy.py)
  (`("rle","rle")` → `("mask","rle")`. 나머지 첫 칸은 이미 도메인 이름이라 무변경).

## ❓ 논의 대상

- [ ] **`docs` 핸들러의 자리** — id_map 같은 중첩 구조(yaml/json)를 담는데, 이건 payload 라기보다
      **구조 사이드카에 가깝다**(`Structure` 와 역할이 겹친다). 둘의 경계를 정한다 — 위 domain × format
      재조직이 이걸 정할 자리다(docs = 중첩구조 도메인의 한 포맷인지, 아니면 `Structure` 로 흡수되는지).
