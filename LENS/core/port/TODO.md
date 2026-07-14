# TODO — port

완료 이력은 git, 최종 설계는 [`README.md`](README.md). 상위 계획은 [`../TODO.md`](../TODO.md) "★ core 4분할".

**이 계층의 계약** — 데이터 **하나**의 실체화(읽기/쓰기)와 외부 세계 발견. `schema` 만 안다.
**`store` 를 모르고, `store` 만이 부른다.** ([`../test_layering.py`](../test_layering.py) 가 강제)

---

## ✅ 결론 난 논의 — `pkgutil` eager 자동등록 → **문제 아님** (2026-07-12)

**→ README 로 승격됨** ([`README.md`](README.md) "구성"). eager 가 문제였던 유일한 이유는 cv2-free 를
무력화한다는 것이었고, `Data_Ref` 가 `schema` 로 빠진 지금 port 는 떳떳하게 무거워도 된다.

---

## ✅ 합의됨 — port 를 domain × format 로 재조직 (→ [`../TODO.md`](../TODO.md) "★ port 전면 재구성")

**경계 확정** — port 의 인터페이스는 `Data_Ref` 다(밖에선 `Data_Ref` 경유로만, store 소비자 하나 유지).
순수 codec 을 bare 함수로 밖에 노출하지 않는다 — 포맷 간 변환은 `Load(A)→정준→Save(B)`.

- [ ] 핸들러를 `domain/format/{inline,storage}` 로 재배치 — 카디널리티(**단일 `mask`** = rle·polygon·
      array·raster / **다객체 `segmap`** = 라벨맵) × 도메인 × 포맷. 각 포맷 핸들러는 **도메인 정준형**
      (mask = 이진 배열)으로 encode/decode 만 하고, inline/storage 는 payload 가 어디 사는가일 뿐(직교).
- [ ] **`format[0]` 이 handler 이름이 아니라 도메인**이 된다 — `("segmap","png")`→도메인 첫 칸. 이러면
      `Infer_type('png')` 거짓말이 풀린다(도메인이 image/mask 를 가른다, 확장자가 아니라).
- [ ] **`format[0]` 마이그레이션** — 사이드카에 영속된 옛 format → 새 taxonomy. store 의 flat→kind-major
      마이그레이션([`../store/TODO.md`](../store/TODO.md))과 **함께 태운다**(옛 저장본이 안 열린다).

## ❓ 논의 대상

- [ ] **`docs` 핸들러의 자리** — id_map 같은 중첩 구조(yaml/json)를 담는데, 이건 payload 라기보다
      **구조 사이드카에 가깝다**(`Structure` 와 역할이 겹친다). 둘의 경계를 정한다 — 위 domain × format
      재조직이 이걸 정할 자리다(docs = 중첩구조 도메인의 한 포맷인지, 아니면 `Structure` 로 흡수되는지).
