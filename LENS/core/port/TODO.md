# TODO — port

완료 이력은 git, 최종 설계는 [`README.md`](README.md). 상위 계획은 [`../TODO.md`](../TODO.md) "★ 축 정리".

**이 계층의 계약** — 데이터 **하나**의 실체화(읽기/쓰기)와 외부 세계 발견. `schema` 만 안다.
**`store` 를 모르고, `store` 만이 부른다.** (불변식은 [`../README.md`](../README.md) 소유)

---

## ❓ 논의 대상

- [ ] **`docs` 핸들러의 자리** — id_map 같은 중첩 구조(yaml/json)를 담는데, payload 라기보다 **구조
      사이드카에 가깝다**(`_structure.py` 의 `Structure` 와 역할이 겹친다). docs 가 그 옆의 codec 인지,
      아니면 `Structure` 로 흡수되는지 미정. `Structure` 를 `codec/sidecar.py` 로 옮기면 질문의 절반이
      답이 된다(사이드카는 codec 이다). → [`../TODO.md`](../TODO.md) "★ 축 정리 잔여 ⑤".
