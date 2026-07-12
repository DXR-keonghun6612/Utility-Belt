"""gui/meta_page — 정본(Dataset_Meta) 편집 갈래 (구성 축, 주입 수신).

Pipeline 객체 그래프(정본 `meta` 1 + tasker N)를 미러링하는 도메인 패키지. 하위 surface:

- `view`   — 정본 개관·편집 (stem 목록 3-상태 뱃지 + 데이터/객체 트리 + `Data_view` 캔버스/인스펙터)
- `convert`— 정본 생성 (raw → Dataset_Meta)
- `run`    — 정본 enrich (process flow)
- `sample` — 파생 갈래 (정본 입력 → 1:N named tasker)

`view` 의 값→표현·편집은 타입별 레지스트리 [`gui/viewer`](../viewer) 가 안다(core 의 `HANDLER_REGISTRY`
와 짝). core.data 접점은 이 갈래 내부에선 정당하고, 갈래 밖(app 연결층)으론 주입(`get_pipeline`)만
오간다. 설계는 `gui/TODO.md`.
"""
