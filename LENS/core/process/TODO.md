# TODO — process

완료 이력은 git, 최종 설계는 [`README.md`](README.md). 상위 계획은 [`../TODO.md`](../TODO.md) "★ core 4분할".

**이 계층의 계약** — **연산**과 **결과의 흐름**. 데이터는 [`../store`](../store) 에만 요청한다.

> **`func` 가 객체 id↔라벨맵 규약·인스턴스 합성을 소유한다**(`func.mask.instance` — `Obj_label`·`Mask_of`·
> `Paint`·`Erase`·`Compose`, ★ 재구성 ①). func 는 `Data_Ref` 를 모르는 **맨 배열** 계층이라 이게 여기 산다
> — port(= `Data_Ref` codec)와 갈린다. → [`../TODO.md`](../TODO.md) "★ port 전면 재구성".

---

## ▶ 진행 중 — 분석을 두 단계로 가르고 `core/analysis/` 로

"검사/분석" 으로 뭉쳐둔 게 실은 **무엇을 아는가로 갈리는 두 단계**다(섞여서 "미리 조립"처럼 보였다):

- **① 결과 생성 = `layer/`** — 입력(staged 0번 mask) → **학습이 쓰는 transform layer** 통과 →
  geometry embedding(feature). transform·mask 만 알고 grouping 을 모른다. **per-sample·reference-free·
  결정적**(입력+고정 config→결과). 이 프로젝트의 출발점("학습 transform layer 로 통과") 그 자체다.
- **② 분석 = `cluster/`·`report/`** — 생성된 feature → 임베딩·군집·(A)/(B) 판정·리포트. feature·
  grouping 만 알고 mask·transform 을 모른다. **cross-sample·탐색적**(파라미터 바꿔 재실행 → flow 아님).

**자리 — `core/analysis/`** (임시 거처 `core/process/analysis/mask/shape/` 를 벗어난다). `func/` 와
구분: func 은 범용 배열 계산(도메인 타입만), analysis 는 분석용 표현 생성·평가다.

```text
core/analysis/
├── layer/     ① source(folder | dataset_meta staged 0번) + transform(공유 config →
│              Build_from_registry) + embedding(batch 적용 → feature 행렬)
├── cluster/   ② UMAP embed + HDBSCAN + register(잔차) + (A)/(B) 판정
└── report/    ② report + visualize        (조율 binder·CLI 는 analysis/ 루트)
```

**경계 판별**: per-sample·reference-free = **layer** (예: `Centroid_Frame` 4-fold 정준화, torch_toolbox) ·
cross-sample·코호트 집계 필요 = **analysis** (예: `register` 는 class 평균 프로파일 대비 잔차 → cluster).
`register` 는 numpy(LENS-local)이지 torch_toolbox 가 아니다 — layer 의 `r_outer` 를 소비하는 분석이다.

**검사의 내용 — 0번 코호트 형상 적합성.** 프레임별 **0번 객체**(이미지 중심 → mask centroid 거리
오름차순, GT는 ann[0]로 구움)만 모아 class 별 형상 일관성을 본다(0번=중심 최근접=카메라 기하 왜곡
최소). 두 실패 모드를 **per-stem 으로** 낸다(집계 purity 만으론 "어느 stem" 이 안 나온다):

- **(A) class 내 형상 이상** — 피처 중심/`register` 잔차 기준 이상치 → 마스크·세그멘테이션 불량.
- **(B) 오분류** — class↔cluster/최근접중심 불일치 → 라벨 오류.

- [ ] **folder 소스** — 지금 `analysis.Source_Spec` 은 store 만 본다. 폴더 배치(batch)를 같은 계약으로
      먹이려면 입력 배선이 store 밖도 가리킬 수 있어야 한다.
- [ ] `Pipeline.Verify` 가 `analysis` 진입점 셋을 부르는 형태로. 지금은 `NotImplementedError` 다.
- [ ] `gui/meta_page/sample/_tab.py` 의 깊은 직접 import 정리 (`core.process.analysis.mask.shape`).
- [ ] **라벨링** = Meta 뷰어 편집 + 평가 surface 양쪽(class·category 확인·수정).
- [ ] **register 배선** — 지금 primitive 로만 있고 미배선. (A) 판정의 class 평균 프로파일 대비 잔차로 엮는다.

**★ 토큰 전환은 `core/analysis` 에서 끝났다.** 도메인별 native feature(scalar `(dim,)` / sequence
`(NT, K)`)를 병합 없이 다루고, 그 목록·성질·저장 그릇을 추출기 계약(`analysis.Extract_Spec`)이 든다.
flat `(N, D)` 전제와 `Cohort_Result`·`persist` 는 사라졌다 — 남은 항목은 표현 쪽뿐이다:

- [ ] **class 도 밴드로** — 지금 class 극좌표는 radial_outer/inner 선, 표본만 밴드. GUI 재빌드와 함께 통일
      (→ [`../analysis/TODO.md`](../analysis/TODO.md) "GUI 전면 재빌드").

**남은 process 쪽 정리**

- [ ] `chroma/stats` 계산을 `func/` 로 (배열만 알게).
- [ ] **`report`·`figure` 는 계산이 아니다** — `matplotlib` 를 `func/` 에 들이지 마라.
      `process/__init__` 이 유닛을 eager import 하므로 **모든 process import 가 matplotlib 를 끌고 온다**.
      숫자 결과만 `params` 로 route 하고, report/figure 는 그걸 읽는 소비처(gui/CLI)로.
- [ ] **`umap`/`hdbscan`/`sklearn`/`torch` 도 같은 함정** — 검사 패키지를 분리해도 eager import 는
      막아야 한다. (형상 계산은 `torch` 를 끌고 온다 — 지연 import 필수.)
- [ ] **vestigial `window` 제거** — `Robust_mean_std` 는 안 받는데 `stats`·`analyze`·`_result` 가 아직
      인자로 나른다(지금은 **조용히 무시된다**).

**끝난 것** — 형상 계산을 `torch_toolbox` 로 승격했다. 학습이 쓰는 것과 **같은 모듈**이어야 분석이
학습과 같은 것을 본다. numpy 사본(`sample_extractor` · `align.py` · `shape/polar.py` ·
`shape/features.py` · `compare_misdetect`)은 426차원·`fill_holes` 버전이라 inner 계열 70차원이 죽은
채였다(표본 56%에 관통 구멍인데 처리 후 1%만 잔존) — 전부 삭제했다.

## ✅ 합의됨 — 빌드 `unit` ↔ 내보내기 task 의 짝을 config 가 검증하지 않는다

`unit=object` 로 빌드한 tasker 를 COCO 로 내보내면 exporter 가 **실행 시점에** 거부한다(객체 자식이 없어
annotation 이 빈다). 레시피를 쓸 때 알았어야 하는 것이다.

- [ ] `task=detection` → `unit=frame`, `task=classification` → `unit=object` + crop 체인.
      GUI 프로필(`gui/meta_page/sample/_profile.py`)이 task 를 고르면 unit 이 따라오게 하거나,
      `Pipeline.Sample` 이 착수 전에 막는다.

## ✅ 합의됨 — `segment` 에 point + mask_input 프롬프트 모드

`Reflection_gate`(stream/mask/reflect.py) + `extract_reflection_by_lowfreq` flow 가 반사 후보를
object(bbox) 로 낸다. 다음은 이 seed 를 SAM3 로 정제하는 것 — 단 반사 **하이라이트 영역만** 원하므로
box(물체 전체를 물어옴) 대신 **DT 최댓점 양성 point + 반사 blob 을 mask_input(288)** 으로 줘야 한다.

- [ ] `stream/model/segment` 에 프롬프트 모드 추가 — 지금 `Segment` 는 box 전용(`_segment_box`).
      point_coords/point_labels/mask_input 경로는 `Sam3_runner.run` 이 이미 `predict_inst` 로 넘긴다
      (검증 완료). mask_input 은 SAM3 `mask_input_size`=288(=256 아님)이라 그 크기로 리샘플.
- [ ] object 에서 seed point(내부 확실점) 를 어떻게 나를지 — bbox 만으론 point 가 안 나온다.
      split_objects 가 segment(라벨맵)를 내므로 라벨별 DT 최댓점을 seed 로 뽑을 수 있다.
- [ ] 반사 정제 후 contour→polygon 은 gui 라벨링 쪽 소비(기존 `update_mask_polygon_from_mask`).
- [ ] 광원 누수 false blob(게이트 경계) — raw 기준 허용. 조이려면 gate 임계·형태학 파라미터.

## ✅ 합의됨 — 부채

- [ ] **`*_rt_cfg.yaml` 의 `layout` 이 재-export 때 날아간다** — cfg 는 변환 툴이 매번 **생성**하는
      산출물인데 LENS 가 쓰는 `layout` 을 거기 손으로 얹었다. 재생성이 지우는 게 당연하다(관측됨 —
      `detection_FP32_rt_cfg.yaml` 이 덮어써져 그 파일을 못 쓰게 됐다). *레시피를 산출물에 적은 것.*
      **방향** — 변환 툴이 cfg 에 `layout` 까지 적게 하는 게 첫째(파일이 자기를 설명한다는 설계가
      유지된다). 툴을 못 고치면 LENS 가 소유하는 사이드카로 뺀다. 툴 쪽 사정을 보고 정한다.
- [ ] **`analysis/chroma` 의 vestigial `window`** — 옛 mode-window 추정기의 잔재. `Robust_mean_std` 는
      받지 않는데 `stats.py`·`analyze.py`·`_result.py` 가 여전히 인자로 나른다. 크래시는 고쳤으나
      **지금은 조용히 무시된다.** report 까지 걷어내야 한다.
- [ ] **transient 라벨맵 `uint8` 한계** — `func/mask/instance.py` 의 라벨맵 산술(`Compose`·`Split_components`
      등)과 `export/mask.py` 의 내보내기 라벨맵이 `uint8` 이라 인스턴스 255개를 넘으면 **조용히 wrap** 한다.
      (저장 라벨맵은 사라졌으니 이제 이건 **계산 중간물·내보내기 레이아웃** 한계일 뿐, 정본 한계가 아니다.)
      **근본 해소 방향** — 프레임 raster 라벨맵을 **obj 폴리곤 집합**으로 승격하면 255 한계와 **겹침**(픽셀당
      라벨 하나)이 동시에 사라진다(→ [`../../gui/TODO.md`](../../gui/TODO.md) "폴리곤 편집기" deferred).
      마이그레이션은 미룸.
- [ ] **`analysis/temp_*.py`** — 기능별 병합용 임시 스크립트. `temp_crop_mask` 는 없는 `meta.schema` 를
      import 해 stale. 흡수하거나 옮길 자리를 정한다.
- [ ] `_base` 데코레이터·라우팅 단위 테스트.

---

## ❓ 논의 대상

- [ ] **결과/디버그 분리** — `outputs` 게이트가 세 의도를 겸한다: flow 의 **산출 계약**(다음 스테이지가
      소비) · **관찰용 디버그**(지워도 돈다) · `object: {}` 같은 **구조 선언**. flow 의 산출 계약이 어디에도
      선언되지 않아 무엇이 결과인지 config 를 끝까지 읽어야 안다.
      관측된 실해 — 디버그 산출물(`flood_mask`·`sam3_seg`)이 정본 버킷에 살아 **staging 전이 때 정본을
      따라 움직인다**(무엇을 지워도 되는지 파일시스템에 근거가 없다).
      **방향** — 선언 위치가 의미를 정한다: `process` 에 붙은 `outputs` = 디버그(관찰), `flow` 에 붙은
      `outputs` = 결과(산출 계약). 목적지도 갈린다(결과=정본 버킷, 디버그=별도 root, 통째 삭제 가능).
      *원칙: 영속은 계약이고 관찰은 부산물이다.*
- [ ] **출력 선언 대칭화** — `outputs=` 튜플 제거, `Run` **반환 어노테이션**에서 OUTPUTS 유도(입력과 대칭).
      `{}`(스킵 관례)는 "출력 없음"과 구분해 보존. → block+wiring(노드 그래프) 준비.
- [ ] **모델 런타임(`stream/model/onnx`·`torch`)의 자리** — **상태를 든 런타임**이라 스트리밍 유닛도
      자유함수도 아니다. 계층이 하나 부족하다는 신호. 소비처가 `func.cv.filter` 를 깊게 직접 import
      하는 것과 함께 푼다(모델 런타임의 자리 + `func` primitive 의 공개 경로).
      backend 를 `onnx`(파일을 들여옴) / `torch`(코드를 들여옴) 로 가른 것은 이 안에서의 정리일 뿐,
      **이 층에 있어야 하느냐는 아직 열려 있다.**
- [ ] **재-convert 덮어쓰기/교차상태 중복** — `Import` 가 이미 있는 stem 을 건드리지 않는 건 정했지만,
      staged/skipped stem 의 재수집 정책은 아직 합의가 없다.
- [ ] **chroma n채널 일반화** — 현재 2채널 고정(명도 버림). 누산·통계 키를 per-channel(`c0_acc`)에서
      배열 단일 키로 재설계. 기존 config 키 마이그레이션 필요.
