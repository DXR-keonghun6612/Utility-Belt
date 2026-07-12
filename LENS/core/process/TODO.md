# TODO — process (+ 적층 소비처)

완료 이력은 git, 최종 설계는 [`README.md`](README.md). 여기엔 남은 것 + 열린 논의.

**core 는 산다.** nested-data sweep 은 core 전 계층(process·converter·sampler·바인더)에서 끝났고
`import core` → Convert → Run → 전이 → Sample → Export 가 실제로 돈다. 남은 건 아래 셋이다.

**구조 전제 (2026-07-12 갱신 — 옛 전제 폐기).** `converter`/`sampler` 는 `process` **하위로 가지 않는다.**
셋(Convert/Run/Sample)이 `Stage` 엔진을 공유하고 양 끝만 다르다는 관찰은 옳았지만, 결론이 틀렸다 — 그
양 끝을 **클래스로 세운 것**(`source`/`sink` 계약)이 문제였고, 녹이면 그 서브클래스를 담던 두 폴더가
**소멸한다.** Convert 는 engine 을 안 쓰므로(체인이 빔) `port`(입출력) 로 가고, engine 을 실제로 쓰는
Sample 만 `process` 에 남는다. 목표는 `schema` / `store` / `port` / `process` **4분할**.

상위 계획은 [`../TODO.md`](../TODO.md) **"★ core 4분할"** 이 소유한다 — 여기엔 그 아래 실행 항목만 남긴다.
아래 "논의 대상"은 **답이 나왔고**(녹인다), 옛 "합의됨 #2"(먼저 `git mv`)는 **순서가 거꾸로라 폐기**됐다.

---

## ✅ 결론 난 논의 — source/sink 계약이 남을 값을 하는가 → **녹인다**

**nested 재편이 이 계층의 일을 상당 부분 먹었다.** 지금은 새 API 로 돌아가게만 고쳐놓은 상태고, 계약
자체를 재검토해야 한다:

- **resolve** = `Data_Ref.Leaves()` + `handler.Load` — 자유함수 한 개(`source.resolve`)면 된다.
- **route** = `handler.Route` + `node.Push` — 그런데 tooling 원칙상 **라이프사이클은 store 소유**다.
- **iterate** = `store.Bucket(cat).items()` — 한 줄.

계약이 세 stage 중 **둘에만 맞는다**는 증거가 코드에 남아 있다:

1. `Stem_Block.units` 가 "공통 분해 골격"인데 `Raw_source` 는 통째 override 한다.
2. `Stem_Block` 의 `stem`/`frame`/`unit` 필드에 "Raw 는 없어도 된다" 는 주석이 달려 있다.
3. `Base_Sink.emit` 은 **체인이 비는 stage(Convert)** 를 위해서만 존재한다 (Run 에선 no-op).
4. `Unit.extra` 는 stage-특화 패스스루 **탈출구**다.

진짜 변주는 traversal 기계가 아니라 **양 끝이 무엇이냐**다 — Convert 만 fs glob(store 아님)이고, Run/Sample 은
"어느 store 의 어느 범주를, frame/object 중 무엇 단위로"가 다를 뿐이라 **클래스가 아니라 파라미터**다.
([`README.md`](README.md) 가 이미 flow 에 대해 같은 논지를 편다: "종류마다 클래스를 만들면 종류가 늘 때마다
코드가 는다.")

**결론(합의).** 녹인다. `Stem_Block`/`Unit` 골격 + `Meta_block`/`Frame_source`/`Meta_sink` 를 없애고 순회 =
`store.Bucket(범주)`, resolve = 자유함수, route = `port` 직접 호출로. `Stage` 엔진(체인·carry·finalize·
진행바·캐시·gate)은 **유지** — 거긴 진짜 일을 한다. block→unit 2단의 근거도 보존한다(프레임 leaf 를
객체마다 다시 안 읽는다 = "resolve 는 불변인 가장 넓은 스코프에서 1회"). 살아남는 건 `Raw_source`(fs
glob)뿐이고, 그건 `process` 가 아니라 **`port`** 로 간다.

- [ ] 실행 항목은 [`../TODO.md`](../TODO.md) "★ core 4분할" **1단계** 참조 (여기서 중복 관리하지 않는다).

---

## 합의됨

### 1. 빌드 `unit` ↔ 내보내기 task 의 짝을 config 가 검증하지 않는다

`unit=object` 로 빌드한 tasker 를 COCO 로 내보내려 하면 `Coco_exporter` 가 **실행 시점에** 거부한다
(sample 에 객체 자식이 없어 annotation 이 빈다 — 조용히 빈 manifest 를 내지 않게 막았다). 하지만 이건
레시피를 쓸 때 알았어야 하는 것이다.

- [ ] `Sample` 레시피 검증 — `task=detection` 이면 `unit=frame`, `task=classification` 이면 `unit=object`
      + crop 체인. GUI 프로필(`gui/meta_page/sample/_profile.py`)이 task 를 고르면 unit 을 따라오게 하거나,
      `Pipeline.Sample` 이 착수 전에 막는다.

### 2. ~~구조 이동 — converter·sampler → process 하위~~ (폐기)

**폐기 이유 — 순서가 거꾸로였다.** "로직 sweep 과 독립한 폴더 재배치"라는 전제가 틀렸다. `mv` 는 집합
보존 연산이라 **경계 변경을 표현할 수 없고**, 여기선 컴파일되는 제약이기도 하다: `converter/source.py` 가
`from ..process.source import ...` 를 하므로 계약을 녹이기 **전에** 옮기면 역방향 의존이 생긴다. 게다가
목적지도 틀렸다 — 두 폴더는 `process` 하위로 가는 게 아니라 **소멸한다**. 새 계획은 [`../TODO.md`](../TODO.md).

### 3. `WORKING` 상수 제거

`constant.py`·`data/sample/__init__` 의 `WORKING` 은 **데이터 모델엔 이미 없다**(split 이 범주). gui
(`_sample_view`)가 아직 참조해서 남겨뒀다 — gui sweep 완료 후 제거.

---

## 그 밖 (이번 범위 밖 — 참고)

- **gui 계층** — `import gui` 는 되지만 **런타임 코드가 옛 API 를 쓴다**: `Category_root`·`Category_of`·
  `Data_Ref(type=)`·`Is_stem`·`.type ==`·`info["dir"]`·`WORKING`, 그리고 없어진 `SAMPLE_SINKS`/
  `Classification_Set`. 특히 `sample/_sample_view` 는 **재분류가 파일 이동이 아니라 `Set_attr`** 로 바뀐다
  (class 가 attr). 별도 sweep(이미 작업 트리에서 진행 중).
- **`analysis/temp_crop_mask`** — stale (없는 `meta.schema` import). `import core` 체인엔 없어 즉시 안
  깨지나 흡수 시 정리 대상. `Pipeline.Tasker_root` 가 이제 `{root}/sample/{name}` 을 주고 crop 은
  `{split}/crop/*.png` 에 있으므로, mask 분석 입력 경로도 함께 고쳐야 한다.
  (잔여 analysis 부채는 [`../TODO.md`](../TODO.md).)
