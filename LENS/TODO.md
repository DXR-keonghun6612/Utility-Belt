# TODO — LENS

core 와 gui 의 상세 잔여는 각 TODO 가 소유한다 — [`core/TODO.md`](core/TODO.md) ·
[`gui/TODO.md`](gui/TODO.md). 여기엔 **둘을 가로지르거나 제품 방향인 것**만. 완료 이력은 git,
최종 설계는 각 `README.md`.

## 진행 중 — 큰 갈래

- [ ] **★ 축 정리 잔여** (core) — ⑤ port 파사드 정리 · segmap 접기 · `format/mask` · `analysis/` → flow.
      → [`core/TODO.md`](core/TODO.md).
- [ ] **gui 3티어 재편** (`widgets ← representation ← app`) + 폴리곤 편집기. → [`gui/TODO.md`](gui/TODO.md).
- [ ] **GUI end-to-end 런타임 검증** — Convert→Run→전이→Sample→뷰어 실제 구동(코드·import 는 서지만
      데스크톱에서 띄워 본 적 없음).

## 미구현 기능 (future)

- [ ] SAM3 multi-instance fan-out (1 frame → N 객체 stem)
- [ ] coco/yolo 포맷 ingest (glob 외 직접 파싱)
- [ ] 이미지 위 직접 편집(bbox 드래그 / mask 브러시) GUI — 폴리곤 편집기가 그 시작.
