# TODO — core

**core 폴더를 가로지르는 것만.** 한 폴더 안에서 닫히면 그 폴더 TODO 소유 —
[`port`](port/TODO.md) · [`store`](store/TODO.md) · [`process`](process/TODO.md) ·
[`analysis`](analysis/TODO.md). core 와 gui 를 가로지르거나 제품 방향이면 루트
[`TODO.md`](../TODO.md).

설계는 [`README.md`](README.md), 이력은 git. 갈래(`논의 대상 → 합의 사항 → 진행 계획`)의 뜻과
빠져나가는 길은 루트 [`TODO.md`](../TODO.md) 가 소유한다.
헤더는 `##`(상태) · `###`(주제) · `####`(세부) 셋뿐.

## 진행 계획

없음. 데이터 모델·패키지 재편의 순서는 루트 [`TODO.md`](../TODO.md) 가 든다 — 그 결과가 core 밖으로
나가므로 계획도 거기 산다.

## 합의 사항

### 축 정리 잔여

루트의 *데이터 모델 — 층은 셋* 이 서면 함께 정리되는 것들. **core 안에서 파일이 움직이는 것만** 여기 둔다.

- [ ] `func/mask/instance.py`(라벨맵↔obj mask 합성) → `region` 도메인 안으로. 구조 연산이라 소속이 맞다.
- [ ] **bbox 마이그레이션 검증** — 옛 `("bbox","list")` 가 정본에 남았는지
      (`scripts/migrate_format_taxonomy.py`). `schema.py` docstring 예시도 옛 format.
- [ ] **leaf·params 이름 흩어짐** — `frame`·`segment`·`roi`·`radial_rle`·`id_map`…
      `profile.LEAF` 상수는 임시방편.
- [ ] **`class_id` 타입 확정** — flow int / store·gui str (`store.py:156` 주석의 의도는 str).
      정하면 `gui/viewer/attr.py::_Choice_row` 의 문자열 비교 방어가 사라진다.

## 논의 대상

없음.

## 미구현 기능

- [ ] **SAM3 multi-instance fan-out** — 1 frame → N 객체 stem.
- [ ] **coco/yolo 포맷 ingest** — glob 외 직접 파싱 경로.
