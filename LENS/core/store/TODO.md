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

---

## ❓ 논의 대상 — 파생이 도메인을 바꾸나(새 데이터냐)가 뷰어·복제·export 를 가른다

**판별자는 "새 파일을 만드나"가 아니라 "정본에 없던 새 도메인의 데이터를 만드나"다.** 포맷·표현만 바꾸는
것은 생성이 아니다 — 예: polygon 으로 든 geometry 를 segmentation 이미지로 렌더해도 **같은 도메인**(그
객체의 geometry)이라 새 데이터가 아니고, 정본이 이미 든 것을 다른 표현으로 재인코딩한 것뿐이다. (그
변환이 **정확히 일치하냐**는 변환 **함수의 correctness** 문제지 sampling 결과 모니터링의 대상이 아니다 —
함수 테스트가 잡는다.)

> `Sample_stage._materialize`(=`bool(processes)`, [`../process/sample.py`](../process/sample.py))는 **거친
> proxy** 일 뿐이다 — 표현만 바꾸는 체인도 `processes` 가 있어 True 로 잡힌다. 진짜 축은 **도메인 변경**이다.

| | sample 이 소유 | 뷰어 | export 픽셀 출처 |
|---|---|---|---|
| **도메인 변경(생성)** — 예: classification=per-object crop | 새 payload | **전용 뷰어** | sample payload |
| **도메인 유지(재표현·참조)** — 예: detection·instance-seg | `(source_stem, split)` 참조 | 없음 — 정본 stem 뷰어 | 정본에서 live |

판별 한 줄: **출력이 정본에 없는 도메인인가.** per-object crop 이미지는 정본에 없다(프레임뿐) → 새 도메인 →
생성. bbox·mask 는 정본 geometry(segment/bbox)의 표현일 뿐 → 재표현(도메인 유지).

**지금 어긋난 곳 (도메인 유지인데 생성처럼 군다)** — detection/seg:
- `Sample_stage._sample_ref` 가 정본 객체를 **clone** 해 담는다(스냅샷 복제) — 새로 만드는 건 split 뿐인데.
- export([`sample/export/coco.py`](sample/export/coco.py))가 bbox·class 는 그 클론(스냅샷)에서, segment 는
  정본(live)에서 읽어 **불일치** — 재라벨하면 박스 옛것·마스크 새것.
- `gui/meta_page/sample/_sample_view` 의 class-그룹 트리는 생성형 전용인데 재표현형에도 씌운다
  (frame 마다 객체가 달라 안 맞음).

**방향(합의되면 README 승격)** — 도메인 유지 sample 은 정본 위 **참조/split-index** 로:
- 빌드: 객체 clone 없이 `(source_stem, split)` 만.
- export: 객체(bbox·class)도 정본에서 live(segment 와 같은 출처) → 불일치 제거.
- 뷰: split별 stem 목록 → 메인 meta 뷰어로 stem 조준(이미 객체·segment 그린다). gui 소비는
  [`../../gui/TODO.md`](../../gui/TODO.md) B.

*원칙: 파생이 **새 도메인**으로 만든 것만 파생이 소유(전용 뷰어)하고, 정본 도메인의 재표현은 참조한다 —
재표현의 정확도는 변환 함수가 책임지지 sampling 모니터링이 아니다.*
