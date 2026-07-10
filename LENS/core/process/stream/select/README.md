# select

object **선택/게이트** 유닛 — "이 obj 를 쓸까?"를 판정한다. 측정(`Center_distance`)과 선택(`Attr_gate`)을
가르고, 선택은 `Base_Process` 의 **"빈 dict 반환 = 이 unit 스킵"** 관례로 표현한다.

핵심 — gate 는 **Stage 엔진이 공유**되므로 Run·Sample 어디서든 동작한다(엔진이 gate 스킵 시 체인 break +
`emit` 스킵). 그래서 같은 `Attr_gate` 하나로 "obj0 만"과 "중심거리 ≤ 0.1"을 둘 다 처리한다.

```text
select/
├── center.py   Center_distance — 중심거리 측정(mask centroid/bbox center → center_dist attr) + 선택적 Run 게이트
├── gate.py     Attr_gate — 범용 값 게이트(ctx 값 조건: keep/max/min → 통과/스킵)
└── __init__.py
```

---

## 경계 — 측정은 Run(정본), 선택은 Sample(파생)

core 경계 규칙("task 바뀌어도 그대로 쓰나?")대로:

- **측정(`center_dist` 값)** = task-무관 기하 → **Run 에서 기록**(정본 obj attr, 전 obj 보존).
- **선택(obj0 / threshold)** = task-특화 → **Sample 에서 게이트**(정본은 손실 없이, 학습셋만 솎아냄).

값은 source 가 ctx 에 올린 것을 읽는다 — `obj_id`(양 source 주입) · 인라인 attr(`center_dist`·`class_id`;
Run=resolve, Sample=inline attr). gate 는 payload I/O 없이 판정한다(Sample A+ 경량 유지).

---

## 사용 예 — obj0 + 중심거리 ≤ 0.1 학습셋

```yaml
# ① Run flow: 중심거리 측정 → 정본 attr 기록 (전 obj)
flows:
  - object_type: measure
    unit: object
    processes:
      - object_type: center_distance                       # mask/bbox → center_dist
        outputs: {center_dist: {to: meta, level: object}}  # obj.info["center_dist"] attr

# ② Sample: obj0 이고 중심거리 ≤ 0.1 인 것만 학습셋에 (gate = 스킵)
sample:
  task: classification
  unit: object
  processes:
    - {object_type: attr_gate, key: obj_id, keep: ["0"]}   # obj0 만
    - {object_type: attr_gate, key: center_dist, max: 0.1} # 중심 근처만
```

두 `attr_gate` 는 나란히 두면 **AND**. gate 가 스킵하면 그 obj 는 `Sample_sink.emit` 이 호출되지 않아
학습셋 트리에 안 들어간다. Run flow 에 gate 를 두면(정본은 안 지우고) 그 obj 의 이후 처리만 멈춘다.

`Center_distance` 에 `max_dist` 를 주면 측정+게이트를 한 유닛에서 겸한다 — 단, Run 게이트는 정본 멤버십을
바꾸지 않으므로 "학습셋에서 빼기"는 Sample gate 로 한다.
