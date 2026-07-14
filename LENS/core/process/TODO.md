# TODO — process

완료 이력은 git, 최종 설계는 [`README.md`](README.md). 상위 계획은 [`../TODO.md`](../TODO.md) "★ core 4분할".

**이 계층의 계약** — **연산**과 **결과의 흐름**. 데이터는 [`../store`](../store) 에만 요청한다.

> **`func` 가 객체 id↔라벨맵 규약·인스턴스 합성을 소유한다**(`func.mask.instance` — `Obj_label`·`Mask_of`·
> `Paint`·`Erase`·`Compose`, ★ 재구성 ①). func 는 `Data_Ref` 를 모르는 **맨 배열** 계층이라 이게 여기 산다
> — port(= `Data_Ref` codec)와 갈린다. → [`../TODO.md`](../TODO.md) "★ port 전면 재구성".

---

## ▶ 진행 중 — `analysis/` 해체 → 계산은 `func/`, 나머지는 flow

**"엔진에 안 접힌다"던 판단은 철회됐다.** 근거였던 *"재군집하려면 파이프라인을 다시 돌려야 한다"* 는
**feature 를 leaf 로 route 해 영속하면** 성립하지 않는다. flow 를 둘로 가르면 된다:

| flow | per-unit | finalize | 비용 |
|---|---|---|---|
| **feature** | crop → `shape_feat` (array leaf 로 route) | — | 비싸다. 한 번만 |
| **cluster** | 영속된 `shape_feat` 를 carry 에 누산 | umap/hdbscan → `params` | 싸다. **파라미터 바꿔 재실행** |

지금보다 **낫다** — 현재 `shape/batch.py` 는 **export 산출물 폴더를 glob** 해서 내보내기를 해야만 분석이
된다. flow 는 store 에서 바로 읽는다. (다중 범주 순회는 구현·검증 완료 — `carry` 가 split 경계를 넘는다.)

**이사 지도**

```text
계산 → func/                       유닛 → stream/                  소멸
  mask/align.py    (PCA 정렬)        mask/shape.py    feature        chroma/io.py     (누산기는 store.Param)
  mask/shape.py    (Fourier)         mask/cluster.py  finalize       shape/batch.py   (폴더 glob → flow)
  mask/embed.py    (umap/hdbscan)    chroma/diagnose.py finalize     shape/__main__.py
  chroma/stats.py  (per_pixel·IQR)                                   sample_extractor · compare_misdetect
```

- [ ] 계산 모듈을 `func/` 로 (배열만 알게).
- [ ] `stream/` 유닛 3개 + flow config.
- [ ] **`report`·`figure` 는 계산이 아니다** — `matplotlib` 를 `func/` 에 들이지 마라. `process/__init__` 이
      유닛을 eager import 하므로 **모든 process import 가 matplotlib 를 끌고 온다**(오늘 두 번 고친 그 병).
      flow 는 **숫자 결과만 `params` 로 route** 하고, report/figure 는 그걸 읽는 **소비처(gui/CLI)** 로.
- [ ] **`umap`/`hdbscan`/`sklearn` 도 같은 함정** — `func/mask/embed.py` 를 `func/mask/__init__` 이 eager
      import 하면 동일하게 오염된다. `__init__` 이 안 건드리게 두거나 유닛이 지연 import 한다.
- [ ] **vestigial `window` 제거** — `Robust_mean_std` 는 안 받는데 `stats`·`analyze`·`_result` 가 아직
      인자로 나른다(지금은 **조용히 무시된다**). 이사하면서 걷어낸다.
- [ ] `gui/meta_page/sample/_tab.py` 가 `core.process.analysis.mask.shape` 를 깊게 직접 import 한다 —
      함께 손본다(gui sweep 중이라 부담은 적다).
- [ ] `Pipeline.Verify` 재설계 — "stream/analysis 두 종류를 다 소비"라는 전제는 무너졌다(계약은 죽었다).

## ✅ 합의됨 — 빌드 `unit` ↔ 내보내기 task 의 짝을 config 가 검증하지 않는다

`unit=object` 로 빌드한 tasker 를 COCO 로 내보내면 exporter 가 **실행 시점에** 거부한다(객체 자식이 없어
annotation 이 빈다). 레시피를 쓸 때 알았어야 하는 것이다.

- [ ] `task=detection` → `unit=frame`, `task=classification` → `unit=object` + crop 체인.
      GUI 프로필(`gui/meta_page/sample/_profile.py`)이 task 를 고르면 unit 이 따라오게 하거나,
      `Pipeline.Sample` 이 착수 전에 막는다.

## ✅ 합의됨 — 부채

- [ ] **`analysis/chroma` 의 vestigial `window`** — 옛 mode-window 추정기의 잔재. `Robust_mean_std` 는
      받지 않는데 `stats.py`·`analyze.py`·`_result.py` 가 여전히 인자로 나른다. 크래시는 고쳤으나
      **지금은 조용히 무시된다.** report 까지 걷어내야 한다.
- [ ] **라벨맵 `uint8` 한계** — `func/mask/instance.py` 의 `segment` 와 재라벨 LUT 가 `uint8` 이라 인스턴스
      255개를 넘으면 **조용히 wrap** 한다. `uint16` 승격은 `segmap` 핸들러의 PNG 저장과 얽힌다.
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
- [ ] **`_sam3.py` 의 자리** — **상태를 든 런타임**이라 스트리밍 유닛도 자유함수도 아니다. 계층이 하나
      부족하다는 신호. 소비처가 `process.stream.model._sam3`·`process.func.cv.filter` 를 깊게 직접 import
      하는 것과 함께 푼다(모델 런타임의 자리 + `func` primitive 의 공개 경로).
- [ ] **재-convert 덮어쓰기/교차상태 중복** — `Import` 가 이미 있는 stem 을 건드리지 않는 건 정했지만,
      staged/skipped stem 의 재수집 정책은 아직 합의가 없다.
- [ ] **chroma n채널 일반화** — 현재 2채널 고정(명도 버림). 누산·통계 키를 per-channel(`c0_acc`)에서
      배열 단일 키로 재설계. 기존 config 키 마이그레이션 필요.
