# TODO — gui/

dataset_meta 중심 재구성 완료 — 보유 `Pipeline` 하나(meta 단일 소스), 본문은 stem 목록(상태 뱃지)과
임베드 `Stem_editor`, id_map/params. Converter·flow 는 비모달 창. 구조는 [`README.md`](README.md).

## 후속 기능

- [ ] Run "중단" 협조적 처리 — `Pipeline.Run` 이 stop flag 를 받도록 core 보강 (현재 없음)
- [ ] `shared` dict 값 타입 보존 (현재 문자열만 입력됨)
- [ ] 새 converter 타입(coco/yolo 등) UI — `_CONVERTER_WIDGETS` 등록
