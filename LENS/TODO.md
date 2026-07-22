# TODO — LENS

core 와 gui 의 상세 잔여는 각 TODO 가 소유한다 — [`core/TODO.md`](core/TODO.md) ·
[`gui/TODO.md`](gui/TODO.md). 여기엔 **둘을 가로지르거나 제품 방향인 것**만. 완료 이력은 git,
최종 설계는 각 `README.md`.

## 진행 중 — 큰 갈래

- [ ] **★ 축 정리 잔여** (core) — port 파사드 정리 · `format/mask` · bbox 마이그레이션 검증 · `analysis/` → flow.
      (segmap 접기는 **완료**.) → [`core/TODO.md`](core/TODO.md).
- [ ] **gui 3티어 재편** (`widgets ← representation ← app`) + 폴리곤 편집기. → [`gui/TODO.md`](gui/TODO.md).
- [ ] **GUI end-to-end 런타임 검증** — Convert→Run→전이→Sample→뷰어 실제 구동(코드·import 는 서지만
      데스크톱에서 띄워 본 적 없음).
- [ ] **★ 테스트 재구성 — 지금 테스트가 하나도 없다.** 구조 정리 중 옛 모델 전제를 깔고 있던 검사들이
      계속 발목을 잡아 `core/test_layering.py`·`gui/test_surfaces.py` 를 **전부 걷었다**. 정리가 끝나면
      **하나씩** 다시 짓는다. 무엇이 사라졌고 왜 필요한지:

      | 잃은 검사 | 지키던 것 | 지금 상태 |
      |---|---|---|
      | `core/test_layering.py` | 계층 import 방향 · `port` 소비자=store · `schema` cv2-free | 산문만 (`core/README.md` 불변식 ①②③) |
      | `gui/test_surfaces.py` | offscreen 으로 전 surface 기동 → **죽은 store-API 호출** 검출 | 없음 — 직접 띄워야 안다 |

      재작성 시 gui 쪽 import 검사(`widgets ← representation ← app`)를 **layering 과 한 벌로** 짓는다
      (→ [`gui/TODO.md`](gui/TODO.md)). 검사가 없는 동안 진행하는 재배치는 **사람이 경계를 지켜야 한다.**

## 미구현 기능 (future)

- [ ] SAM3 multi-instance fan-out (1 frame → N 객체 stem)
- [ ] coco/yolo 포맷 ingest (glob 외 직접 파싱)
- [ ] 이미지 위 직접 편집(bbox 드래그 / mask 브러시) GUI — 폴리곤 편집기가 그 시작.
