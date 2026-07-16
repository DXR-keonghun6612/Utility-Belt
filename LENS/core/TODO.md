# TODO — core

완료 이력은 git, 최종 설계는 각 `README.md`. 여기엔 **폴더를 가로지르는 계획**만 — 폴더 안에서 닫히는
항목은 각 폴더 TODO 가 소유한다: [`port`](port/TODO.md) · [`store`](store/TODO.md) ·
[`process`](process/TODO.md).

---

## ★ core 4분할 — schema / port / store / process

계층은 하는 일이 아니라 **아는 타입**으로 갈린다.

```text
core/schema.py    Data_Ref — 서술. 아무것도 모른다 (의존 0 · 진짜 cv2-free). 모두가 쓴다.
core/port/        데이터 하나의 실체화(읽기/쓰기) + 외부 발견. schema 만 안다. store 만이 부른다.
core/store/       데이터 여럿의 관리(메모리 컬렉션) + 라이프사이클 API. 읽기/쓰기는 port 에 요청.
core/process/     연산과 결과의 흐름. 데이터는 store 에만 요청.
core/_base.py     Pipeline — 계산 단계 조율만.
```

**경계는 산문이 아니라 [`test_layering.py`](test_layering.py) 가 강제한다** — ① 아래 계층이 위 계층을
import 하면 실패 ② `core.schema` 만 들였을 때 cv2·numpy 가 안 딸려와야 통과. 이 검사가 있는 한 계층은
살아 있다. (왜 이 검사가 필요했는지는 [`store/TODO.md`](store/TODO.md) "cv2-free 경계" — 같은 경계를
두 바퀴 돌았다.)

**끝난 것 — 4분할 + 리팩토링 전부.**

- [x] source/sink 계약 해체(`88e5477`) → `Stage` 엔진 + 서브클래스 2개.
- [x] 재배치 — `schema`/`port`/`store`/`process`, `converter`·`sampler` 소멸, 계층 검사 도입.
- [x] **port** — `ingest.py` 해체(`Scan`→`scan.py`, `_spec_ref`→`Template_for_file`) + `handler/` 평탄화.
- [x] **store** — `Import` 추가(`Restore`/`Merge` 의 형제) · 죽은 메서드 삭제(`Export`·`Get_or_add`·
      `Iter`→`_iter`) · export → `sample/export/` **task 별 파일** + `Sample_Set.Export` ·
      읽기/쓰기 창구(`Resolve`/`Route`/`Param`/`Path_of`).
- [x] **process** — `port` 직접 호출 제거(전부 store 경유) · 죽은 `Analysis` 계약 삭제.

**남은 것**

- [ ] **`analysis/` 를 flow 로** — 계약은 죽였지만 **모듈 이사는 안 했다**. 계산 → `func/`, feature/cluster
      두 flow 로. 다중 범주 순회는 준비됐다(carry 가 split 경계를 넘는다). → [`process/TODO.md`](process/TODO.md)
- [ ] **`DEFAULT_RATIOS` 부채** (아래) — split 배정이 바뀌는 변경이라 의도적 결정이 필요하다.
- [ ] **문서 패스** (마지막) — 아래.

---

## ★ port 전면 재구성 + 생성/재표현 대응 — domain × format, 라벨 규약 단일화

두 갈래가 한 파일(`export`)에서 얽혀 **함께 간다.** 확정 결정 (2026-07-14).

### 경계 결정 — port ⟷ Data_Ref

- **port 의 인터페이스는 `Data_Ref` 다.** port 는 `Data_Ref`(+payload)로만 연산하고, 밖에서는
  `Data_Ref` 를 통해서만(= store 경유) port 를 부른다. **port 소비자는 여전히 store 하나** —
  `check_port_consumer` 도 gui 티어 규칙도 안 벼린다(이게 규칙을 하나도 안 굽히는 유일한 경계라 골랐다).
- **합성은 func.** 라벨맵↔객체(`Obj_label`·`Mask_of`·`Paint`·`Erase`·`Compose`)는 **맨 배열 연산이라
  `Data_Ref` 가 없다** → port 가 아니다. func 가 배열·박스·인스턴스 합성을 알고 process·gui·binder 가
  자유롭게 부른다. **port 는 obj_id 를 모른다** — 프레임 라벨맵도 port 엔 uint8 payload 일 뿐(semantics-blind).
- **codec 은 port handler**, `Data_Ref.format` 으로 디스패치. domain × format × (inline/storage) 는
  **port 내부 구조**다. 카디널리티가 도메인을 하나 더 가른다 — **단일 `mask`**(rle·polygon·array·raster,
  정준 = 이진 배열) vs **다객체 `segmap`**(라벨맵). 포맷 간 변환은 `Load(A)→정준→Save(B)` 로(관통 함수를
  bare 로 노출 안 함).
- **export 는 binder.** store 라이프사이클(전이·삭제·병합·pop)이 아니라 read+compute+external-write 라,
  func(gather/compose) + store(`Data_Ref` encode·`Path_of`) + 외부 레이아웃 쓰기를 조율한다.

*원칙: 표현 지식은 `Data_Ref` 로 표현돼 port 가 든다(codec). 배열↔배열 합성은 func. 둘을 잇는 것은 binder.*

### 단계 (① 완료)

- [x] **① func 가 id↔라벨 규약·합성 단일 소유** (`e7b9a06`) — `func.mask.instance` 에 `Obj_label`·
      `Obj_id_of`·`Mask_of`·`Paint`·`Erase`·`Compose`. 닿는 소비처(sample·SAM3·gui 편집) 갈아끼움.
      **남은 `int(id)+1`** (store/meta·export·gui 렌더)은 계층상 지금 func 에 못 닿아 ③에서 걷힌다.
- [x] **② port 내부를 domain × format 로 재조직** + 마이그레이션. `domain/`(무엇을 담나 — 유효 포맷 검증·
      정준형·정책) × `codec/`(어떻게 직렬화 — I/O). **I/O 범위가 도메인보다 작아** codec 이 도메인을 넘어
      재사용된다(`raster` 를 image·mask·segmap 이 공유). 새 처리 구조 = 파일 하나 + `FORMATS` 한 줄 —
      SAM polygon 이 그렇게 붙었다. → [`port/TODO.md`](port/TODO.md)
- [x] **③ export 해체 → binder** — `core/store/sample/export/` → [`core/export/`](export)(binder 계층).
      정본 **live** 읽기(스냅샷/STAGED 버그 해소, `d0c30e5`)·store repaint 벗기(`b1b8589`)에 이어, exporter 가
      `port` 직접 호출을 뗐다: `_obj_mask`→`func.Mask_of`, COCO RLE→`store.Encode`(inline codec 창구),
      crop 경로→`store.Path_of`. `Sample_Set.Export`→`export.Run_export`(binder). `check_port_consumer`·
      gui 티어 규칙 안 벼림 — export 는 func·store 만 안다. 스모크로 확인(det live·재라벨·seg RLE/mask).
- [x] **④ sample 객체 clone 제거**(`d0c30e5`) + **gui frame 뷰 = split→stem 목록**(정본 뷰어로 조준,
      class-트리 아님). detection·seg tasker 는 class-그룹 대신 split→stem 을 보이고 stem 선택이
      메인 meta 뷰어를 `refresh(keep=stem)` 로 조준한다(정본 뷰어가 객체·segment 를 그린다).
      → 생성/재표현 대응 완료.

---

## ★ 축 정리 — format(구조) · codec(I/O) · domain(뜻). **대표 포맷 제거** (2026-07-15)

**위 ② 를 이어받아 뒤집는 곳이 있다.** ② 는 `port` 를 domain × format 으로 갈랐지만, 축의 **뜻**이
아직 섞여 있었다 — 도메인이 **대표 포맷 하나**(정준형)를 정해 모든 포맷을 그리로 뭉갠다. 그래서
`("mask","polygon")` 이 폴리곤 구조를 못 지키고, 편집기는 꼭짓점을 **본 적이 없다**(`Polygon_Codec.Load`
가 `Decode_polygon` 으로 배열을 낸다). 폴리곤을 1급 편집 대상으로 두려면([`../gui/TODO.md`](../gui/TODO.md)
"폴리곤 편집기") 이 축부터 갈라야 한다.

### 두 축의 뜻을 다시 못박는다

- **format = 데이터 구조.** *어떻게 들고 있나* — bbox·polygon·rle·라벨맵. **자기가 무슨 뜻인지 모른다.**
- **domain = 그 구조를 무엇으로 읽나.** polygon 하나가 mask 도 polyline 도 된다 — 그 차이가 도메인이다.
- **codec = 그 구조의 입출력만.** 바이트가 무슨 뜻인지 모른다.

*codec 은 바이트가 무슨 뜻인지 모르고, format 은 그게 어디 사는지 모르고, domain 만 둘 다 안다.*

**정준형은 사라지고, 변환은 도착지가 든다** — 시작점(포맷)이 여럿이고 도착지(도메인의 뜻)가 하나면
도착지가 안다. 단 **고르는 것**만 도메인이고(폴리곤을 채울까 그을까) **계산**은 `format/` 이 든다.
그래야 polyline 도메인이 생겨도 같은 `polygon` 구조에 `stroke()` 를 고르는 것으로 끝난다.

`Canonicalize` 는 **남는다**(`Normalize` 로 개명) — 하는 일이 포맷 변환이 아니라 *같은 구조 안의 의미
보정*(3채널 png → 단일채널, 255 → 1)이라 도메인의 진짜 일이다. 이미 배열이 아닌 payload 는 통과시킨다.

### 목표 트리

```text
core/
  schema.py  typing  constant     0   횡단 primitive (의존 0 · cv2-free)
  format/                         0   데이터 구조 + 그 연산      bbox·polygon·rle·mask(+segmap)
  func/          ← process/func   0   순수 계산 (구조 무관)      cv·chroma
  scan.py        ← port/scan      0   외부 fs 발견 (pathlib 만)
  codec/         ← port/codec     1   직렬화                     raster(cv2)·npy·inline·sidecar
  domain/        ← port           2   무엇으로 읽나 + 검증·정책 + 디스패치
  store/  process/  export/       3+
```

- **`port` → `domain`.** I/O 가 codec 으로 나가면 남는 건 "무엇으로 읽나 + 검증·정책 + 디스패치"뿐이라
  이름이 역할과 어긋난다. `port.Load` → `domain.Load` 는 이름이 살짝 I/O 냄새를 내지만, 하는 일이
  "이 서술자를 무엇으로 읽어 무엇을 주나"라 도메인의 일이 맞다(실제 읽기는 codec 에 넘긴다).
- **`func` 는 이미 `process` 소속이 아니었다.** core 에서 아무것도 import 하지 않고(cv2·numpy 뿐), 정작
  당기는 쪽은 gui 3곳 + export + process 다. 위 ① 이 *"process·gui·binder 가 자유롭게 부른다"* 고 적어놓고
  `process` 밑에 뒀던 것 — 계층상 그 말이 거짓이었다. `raster_domains.py` 가 func 을 **docstring 으로만
  가리키는**(역방향이라 import 불가) 것도 같은 증상이고, 올라오면 풀린다.
- **`scan` 은 나가면 기형이 풀린다.** 지금 *"port 안의 어떤 것도 import 하지 마라 — 자동등록 순회가
  순환난다"* 는 제약과 `# noqa: E402` 를 지고 있는데, 그 제약의 유일한 근거가 **port 안에 있다는 것**뿐이다.
- **`Structure` → `codec/sidecar.py`.** 이름이 거짓말이었다 — 이제 "구조"는 format 을 뜻하는데 저건
  *사이드카*다. 실체는 **payload 가 아니라 `Data_Ref` 트리를 싣는 codec** 이고(자기 docstring 이 "그 대칭"
  이라 적었다), registry 에 없는 이유도 서술자 포맷이 하나뿐이라 고를 게 없어서다.
- **`segmap` 은 도메인이 아니라 mask 의 한 포맷.** ② 의 *"카디널리티가 도메인을 가른다"* (단일 `mask` vs
  다객체 `segmap`)를 **접는다**. 영역이 obj 별 rle·polygon 으로 내려가기로 한 이상 라벨맵은 **mask 여럿을
  겹쳐 담은 한 표현**일 뿐이라, 도메인은 `mask` 하나고 segmap 은 그 포맷(픽셀 = id+1 인 단일채널 배열)이다.
  `func/mask/instance.py` 가 이미 `mask/` 아래 살고 `Mask_of`·`Erase`·`Merge_into` 가 전부 "라벨맵에서
  mask 하나를 꺼내고 넣는" 일인 것이 그 증거. → `format/mask/`.
- **② 가 걱정한 "라벨맵을 rle 로"는 정의 불가가 아니라 인자가 필요한 변환이었다** — `Mask_of(맵, obj_id)`.
  대표 포맷이 있을 때는 변환이 **자동**이라 인자를 받을 자리가 없어 정의 불가로 보였을 뿐이다. 변환이
  요청이 되면(③) 인자 있는 변환도 자연히 선다 — 카디널리티 분할의 근거가 그렇게 먼저 사라진다.

### 단계 — 앞의 셋은 뒤를 안 기다린다

- [ ] **① `core/func` ← `core/process/func`** (`git mv`) + `test_layering.LAYER` 한 줄 + 소비처 7곳.
      순수 이동이라 독립적.
- [ ] **② `core/format` 신설 + `core/codec` ← `core/port/codec`** — 구조를 I/O 에서 뗀다.
      `func/mask/instance.py` → `format/mask/`. `Decode_polygon`/`Decode_rle` 도 codec 에서 여기로
      (폴리곤을 **채우는** 건 codec 의 지식이 아니다 — 구조는 자기가 면인지 선인지 모른다).
- [ ] **③ 대표 포맷 제거** — `Codec.Load` 가 네이티브를 낸다. `Canonicalize`→`Normalize`.
      도메인이 `format` 의 연산 중 하나를 **고른다**.
- [ ] **④ bbox 1급 포맷** — `codec/bbox.py`(inline) + `_domain()` 의 "개념 → ATTR" 우회 제거.
      `("bbox","list")` → `("mask","bbox")` 마이그레이션.
- [ ] **⑤ `port` → `domain`** + `scan`·`Structure` 이사. 티어 규칙에 `core.format`·`core.func` 허용
      추가(`core.store`·`core.domain` 은 계속 금지) → [`../gui/TODO.md`](../gui/TODO.md).

**소비처가 조용히 깨진다 — 이게 이 재편의 진짜 위험이다.** ③ 이후 mask payload 가 polygon dict 로 올 수
있는데 소비처가 전부 `isinstance(ndarray)` 가드라 **에러 없이 `None` 으로 사라진다**(`Mask_viewer.layer` ·
`_data_view._is_mask` · `export/mask.py` · `func/mask`). general.md "조용한 fallback 금지" 정면 위반이라,
③ 은 소비처 갈아끼움과 **같은 커밋**이어야 한다.

### ❓ 논의 대상 (이 재편이 정할 것)

- [ ] **`docs` 핸들러의 자리** (기존 [`port/TODO.md`](port/TODO.md)) — `Structure` 가 `codec/sidecar.py`
      로 가면 이 질문의 절반이 답이 된다(사이드카는 codec 이다). docs 가 그 옆의 codec 인지 여전히 미정.

---

## 문서 소유권 (누가 무엇을 적는가)

**같은 사실을 두 곳에 쓰지 않는다.** `core/README.md` 가 data 내부를 중복 서술한 것이 지난번 문서가 썩은
원인이었다 — 사본만 조용히 거짓이 됐다. 지금 경계는 이렇다:

| 무엇 | 어디 |
|---|---|
| 트리 모델(BRANCH/LEAF, `bool(format)` 이 곧 kind) | [`schema.py`](schema.py) docstring — **한 심볼 안에서 닫힌다** |
| payload 경로 규칙(kind-major) · handler 계약 · `Route` | [`port/README.md`](port/README.md) |
| 범주 = 구조 key · item 주소 · 사이드카 · 라이프사이클 | [`store/README.md`](store/README.md) |
| 엔진 · ctx 스코프 · port↔slot · carry/finalize · stream↔func 경계 | [`process/README.md`](process/README.md) |
| 계층 지도 · 의존 방향 · 바인더 | [`README.md`](README.md) — **내부는 안 적고 가리킨다** |

- **워크플로는 README 가 아니다** — 여러 단계에 걸친 흐름은 문서에 적으면 썩는다. `select/README.md` 의
  yaml 예시를 지운 이유다(내용은 이미 `gate.py`·`center.py` docstring 에 있었다).
- **결론 난 논의는 README 로 승격**했고 각 TODO 엔 포인터만 남겼다 — 지우면 **왜 그렇게 정했는지가
  증발한다.**

---

## ✅ 합의됨 — 부채

- [ ] **`DEFAULT_RATIOS`(0.8/0.1/0.1)가 한 번도 적용되지 않는다** — `Pipeline.Sample` 이
      `ratios=_cfg.get("ratios") or {}` 로 **빈 dict 를 명시 전달**해 dataclass 기본값이 늘 덮인다.
      `_norm_ratios({})` → 합 0 → **균등 1/3**(레시피에 `ratios` 가 없으면 항상). 검증에서 3 stem →
      train 0 / val 2 / test 4 로 관측. **리팩터 이전부터 그랬다** — 동작 보존을 위해 그대로 뒀다.
      고치면 split 배정이 바뀌어 기존 tasker 재빌드 시 데이터가 이동하므로 **의도적 결정이 필요**하다.
- [ ] **`excluded` 큐레이션 영속** (파생 = 순수 재생성 + 솎아내기).
- [ ] **GUI end-to-end 런타임 검증** — 실제 데스크톱에서 Convert→Run→전이→Sample→뷰어 흐름.
- [ ] coco/yolo 포맷 ingest (glob 외 직접 파싱 경로).

---

## ❓ 논의 대상

- [ ] **id_map 소유권** — id_map 은 detection 내보내기(파생) 소유인데 정본 `params` 에 얹혀 있어 계층과
      어긋난다. 정본은 class **이름**만 들게 두고 id_map 을 tasker 레시피로 내릴지 결정(내리면 gui 표시도
      sample 로 이동).
