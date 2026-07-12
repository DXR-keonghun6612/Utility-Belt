# TODO — port

완료 이력은 git, 최종 설계는 [`README.md`](README.md). 상위 계획은 [`../TODO.md`](../TODO.md) "★ core 4분할".

**이 계층의 계약** — 데이터 **하나**의 실체화(읽기/쓰기)와 외부 세계 발견. `schema` 만 안다.
**`store` 를 모르고, `store` 만이 부른다.** ([`../test_layering.py`](../test_layering.py) 가 강제)

---

## ✅ 결론 난 논의 — `pkgutil` eager 자동등록 → **문제 아님** (2026-07-12)

**→ README 로 승격됨** ([`README.md`](README.md) "구성"). eager 가 문제였던 유일한 이유는 cv2-free 를
무력화한다는 것이었고, `Data_Ref` 가 `schema` 로 빠진 지금 port 는 떳떳하게 무거워도 된다.

---

## ❓ 논의 대상

- [ ] **`docs` 핸들러의 자리** — id_map 같은 중첩 구조(yaml/json)를 담는데, 이건 payload 라기보다
      **구조 사이드카에 가깝다**(`Structure` 와 역할이 겹친다). 둘의 경계를 정한다.
