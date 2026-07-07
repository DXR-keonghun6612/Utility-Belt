# TODO — LENS

백엔드(core: data · converter · process/flow · pipeline binder + CLI)는 **flat `Data_Ref` 스키마로
재작성 완료** (sample 계층 제외). 완료 이력은 git, 최종 설계는 각 `README.md`. 잔여 상세는
[`core/TODO.md`](core/TODO.md).

## 남은 작업

- [ ] **sample 파생 flat 재설계** — `sample/`·`Pipeline.Sample()`·id_map 복구 ([`core/TODO.md`](core/TODO.md))
- [ ] **gui 런타임 검증** — 코드·import 완료(flat `Dataset_Meta`/pipeline 기준). 실제 띄워 end-to-end
      확인이 남음 ([`gui/TODO.md`](gui/TODO.md))
- [ ] **`analysis/` → `core/` 흡수** + **Verify** 단계 구현 (`Pipeline.Verify`)
- [ ] config 스키마 갱신 (`flows:` · 모델 nested · converter globs) — 옛 config 복원은 안 함

## 미구현 기능 (future)

- [ ] SAM3 multi-instance fan-out (1 frame → N 객체 stem)
- [ ] coco/yolo 포맷 converter (glob 외 직접 파싱)
- [ ] 이미지 위 직접 편집(bbox 드래그 / mask 브러시) GUI
