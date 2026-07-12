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


## ✅ 결론 난 논의 — gui sweep 완료 (2026-07-12)

gui 는 이제 새 API 만 쓴다. **경로를 gui 가 모른다** — `meta.Load(stem, key)` / `meta.Route(…)` /
`sset.Load(sid, "crop")` 에 **요청**하고, 파일이 어디 있는지는 store 가 트리 위치에서 파생한다.
gui 가 아는 건 "이 stem 이 어느 범주인가"(`Category_of`, 상태 뱃지용)뿐이다.

**의미가 바뀐 곳은 하나였다** — `sample/_sample_view`. class 가 구조 key 에서 **attr** 이 되면서 재배정이
"crop 재저장 + 옛 파일 삭제 + 노드 이동 + 사이드카 2개 rewrite" 에서 **attr 갱신 두 줄**이 됐다(정본
write-back + 파생 attr). **파일이 안 움직인다.** 트리의 class 그룹도 저장 구조가 아니라 표시용 group-by 다.

`WORKING` 상수는 제거됐다 (마지막 참조가 gui 였다).

---

## ✅ 결론 난 논의 — cv2-free 경계 (2026-07-12)

**→ README 로 승격됨.** 왜 `Data_Ref` 를 `core/schema` 로 꺼냈고 왜 라이프사이클은 store 소유 그대로인지는
[`../README.md`](../README.md) "왜 검사까지 두는가" 가 소유한다. 결론을 지키는 장치는
[`../test_layering.py`](../test_layering.py).
