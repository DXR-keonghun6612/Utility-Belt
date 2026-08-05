# TODO — LENS

core·gui 안에서 닫히는 것은 각 TODO 소유 — [`core/TODO.md`](core/TODO.md) · [`gui/TODO.md`](gui/TODO.md).
여기엔 **둘을 가로지르거나 제품 방향인 것**만. 설계는 각 `README.md`, 이력은 git.
헤더는 `##`(상태) · `###`(주제) · `####`(세부) 셋뿐.

갈래는 **결정 상태**로 가른다 — 활동량이 아니다:

| 갈래 | 뜻 | 빠져나가는 길 |
|---|---|---|
| `논의 대상` | 답이 아직 없다 | 답이 나오면 합의 사항으로 (설계 결정은 README 승격) |
| `합의 사항` | 무엇을 할지 정해졌다 | 착수 순서가 잡히면 진행 계획으로 |
| `진행 계획` | 지금 무엇을 어떤 순서로 하는가 | 끝나면 삭제 |

## 진행 계획

1. **데이터 모델 세 층 확정** → `format`+`domain` 합치기 · `port` 해체 · `codec` → `io` · `Claims` 제거
2. **`Data_Ref` 순수화** — ①과 순서를 바꾸면 두 번 옮긴다
3. **`io`·`database` 를 밖으로** (목적지는 논의 대상)
4. **테스트 재작성** — layering + surface 를 한 벌로
5. **gui 3티어 재편** → [`gui/TODO.md`](gui/TODO.md)

④를 ③ 뒤에 두는 이유: 검사를 먼저 지으면 재배치 내내 빨간 채로 방치된다.

## 합의 사항

### 데이터 모델 — 층은 셋

| 층 | 물음 | 예 |
|---|---|---|
| **도메인** | 무엇을 뜻하나 | `region` · `image` · `pose` · `id_map` |
| **포맷** | 어떤 표현인가 | `cartesian` · `radial` · `polygon` · `bbox(xyxy)` · `quat` |
| **직렬화** | 어떤 바이트인가 | `rle` · `png` · `npy` · `npz` · `yaml` · `json` · inline |

**층 사이는 N:M — 위가 아래를 소유하지 않는다.** 도메인은 자기가 받는 포맷을, 포맷은 자기가 받는
직렬화를 **선언**만 한다.

- **포맷은 도메인에 안 묶인다** — `cartesian`(직교 격자)은 `region` 이든 `image` 든 같은 좌표계다.
  같은 표현을 도메인마다 다시 짓지 않는다.
- **`mask` 는 `region` 이다** — 둘 다 "영역이 어디인가"고, 다른 건 표현뿐이다:
  `bbox`(사각) · `polygon`(다각) · `cartesian`(픽셀 격자) · `radial`(광선).
- `radial_rle` = `region` · `radial` · `rle`. 지금은 이름 하나에 셋이 뭉쳐 있다.
- `rle` 은 `cartesian` 에도 걸린다(COCO RLE) — 직렬화가 포맷과 직교라야 표현된다.

#### 지금 어긋난 자리

| 지금 | 왜 틀렸나 | 이 모델에서 |
|---|---|---|
| `mask` 와 `region` 이 다른 도메인 | 둘 다 "영역이 어디인가" — 다른 건 표현뿐 | 한 도메인 `region`, 포맷이 `bbox`·`polygon`·`cartesian`·`radial` |
| `("mask","rle")` ↔ `("mask","png")` 가 같은 칸 | 하나는 직렬화, 하나는 포맷+직렬화 | `region·radial·rle` / `region·cartesian·png` |
| `("region","bbox","xyxy")` 만 셋째 칸 | 축이 모자라 뚫은 구멍 | `xyxy` 는 포맷의 파라미터 (`core/format/bbox.py` 가 이미 그렇게 적음) |
| `attr` 도메인 `FORMATS=(str,int,float,list)` | 파이썬 타입은 뜻도 표현도 아니다 | 도메인 아님 — inline 직렬화의 세부 (`schema.py` 가 이미 첫 칸을 비워 쓴다) |
| `docs` 도메인 | 읽고 쓰기가 전부 | 도메인 아님 — 직렬화군 |
| `radial_rle` = `{"type":"array","format":"npy"}` | 도메인이 `array` — 뭔지 모른다 | `region·radial`. 접기(`outline`·`signed`)가 갈 자리가 생긴다 |
| `cartesian` 격자 개념이 도메인마다 따로 | `region` 의 직교 격자 = `image` 의 직교 격자 | 포맷 하나를 둘이 고른다 |

#### 도메인 승격 규칙

> **고유 연산이 있으면 도메인, 없으면 값.**
> `id_map`(합치기·지우기·번호 압축) → 도메인. `profile_spec`·`analysis_recipe`(읽고 쓰기뿐) → `docs` 값.

#### 포맷 변환은 포맷 층이 소유

포맷이 도메인에서 풀려났으니 변환도 따라 내려간다 — `cartesian → radial` 은 **좌표 재표집**이라
그 격자가 영역인지 영상인지 안 봐도 된다.

- 변환마다 CPU/GPU 를 고른다 — 지금 접기가 `torch_toolbox` 에 있는 자리.
- 값의 전제(이진인가 강도인가)는 **직렬화가 든다** — `rle` 이 이진을 전제하지 변환이 전제하지 않는다.
- 유효 조합은 각 층이 선언 — 도메인이 `{받는 포맷}`, 포맷이 `{받는 직렬화}`.
  지금 `FORMATS` 한 줄이 하던 검증이 두 층으로 갈린다.

#### 폴더 배치

```text
database/format/<포맷>.py     표현 · 포맷 간 변환      cartesian · radial · polygon · bbox · quat
database/domain/<도메인>.py   뜻 · 받는 포맷 선언      region · image · pose · id_map
func/format/<포맷>.py         그 표현 위의 순수 계산 (배열↔배열)
```

- **포맷-major 다** — 도메인별로 폴더를 파면 `cartesian` 이 `region/` 과 `image/` 에 두 벌 생긴다.
- `func/` 는 모양만 따라간다 — lv0(core 를 모름)은 그대로.

#### routing spec 도 세 층을 적는다 — `Claims` 제거

| spec 키 | 세 층에서 | 예 |
|---|---|---|
| `to` | 그릇 (인라인 / 파일) | `meta` · `storage` · `trace` |
| `type` | 도메인 | `array` · `docs` · `mask` |
| `format` | 직렬화 | `npy` · `npz` · `json` · `png` |
| — | **포맷** | 자리 없음 |

`port.Template` 의 도메인 확정 순서 = `spec.type` → `format` 확장자 추론 → `Claims`(값 보고 추측).
셋째가 도는 건 `type`·`format` 둘 다 없는 spec 뿐:

| 미지정 spec | 자리 | |
|---|---|---|
| `{"to": "storage"}` | `core/process/sample.py:59` (crop) | 죽은 갈래 — 함께 사라진다 |
| `{"to": TO_META}` | `gui/…/analysis/_dialog.py:230` | 살아 있음 — `attr` 이 claim |

- [ ] **`Claims` 제거** — 안 적힌 spec 은 추측이 아니라 실패. 위 한 자리에 도메인을 명시하면
      `Claims` 와 `storage`/`params` 맥락 인자가 함께 사라진다.
- [ ] spec 에 **포맷 자리**를 낸다 — 지금은 leaf 이름(`radial_rle`)이 그 역할을 대신한다.

#### `mask` → `region` 마이그레이션

저장된 `format` 튜플 첫 칸이 바뀐다. bbox 때와 같은 모양의 일회성 스크립트
(`scripts/migrate_format_taxonomy.py`).

- 규모: 정본 사이드카 40파일 표본에서 `"mask"` 145 · `"region"` 72 (둘 다 실제로 박혀 있다).
- ⚠ **`"mask"` 는 도메인 이름이자 leaf 이름이다** — `obj.Get("mask")` · `outputs=("mask",)` ·
  `obj.Attr("mask")`. 일괄 치환하면 트리 이름까지 바뀐다. 바꾸는 건 **format 튜플 첫 칸만**이고,
  leaf 이름은 그대로 둔다(`schema.py`: *"이름에서 종류를 되짚지 않는다"*).

### 패키지 재편 — `io` + `database`

축 정리(`format`·`codec`·`func` 분리 + 대표 포맷 제거 + bbox 1급)는 코드에 들어왔으나 선이 안 지켜진다.

#### 진단 — 실측

| 관측 | 자리 |
|---|---|
| `domain` 이 `format` 을 직접 import | `port/domain/mask.py` → `format.polygon`·`format.rle` |
| 도메인 파일이 껍데기 (`FORMATS` 한 줄 + `Claims → 0`) | `pose.py` 37줄 · `region.py` 41줄 · `raster_domains.py` 44줄 |
| 구조 하나 추가에 파일 셋 | `format/pose` + `port/domain/pose` + `codec/inline.Formats()` |
| 경로 규칙은 port 문서, 구현은 codec | `codec/_base.py::_path` ↔ `port/README.md` |
| gui 가 port 를 직접 부른다 (위반 4곳) | `port.Types()`·`port.Blank()` — 둘 다 도메인 어휘 |
| `Structure` 소비처 9곳 전부 store · `Scan` 1곳 store | port 가 서로 다른 넷을 한 이름에 모아 둠 |
| `codec/docs` 가 `python_toolbox.file` 을 감쌈 | 같은 디스패치가 두 겹 (확장자→handler / format→codec) |
| `class_id` 가 int(flow) / str(store·gui) | `gui/viewer/attr.py::_Choice_row` 가 문자열 비교로 방어 |
| 같은 format 튜플이 손으로 9개 파일에 | `("region","bbox","xyxy")` · `("mask","rle")` |
| 객체 컨테이너 생산자 넷이 같은 세 줄 복사 | `separate` · `_objects` · `detect/_base` · `segment/_base` |
| 어떤 attr 이 진실이고 어떤 게 파생인지 안 적혀 있다 | `Mask_center` 는 `center` 를 쓰고 `_normalize` 는 걷는다 — 상반된 생산자 |

#### 목표 구조

```text
io/          바이트 ↔ 값 · 경로 파생(kind-major) · 디스패치 · 폴더 스캔
database/    데이터 모델 — io 를 부른다 (한 방향)
  schema       추상 트리 `Data_Ref` — 의존 0 유지
  format/      표현 + 포맷 간 변환 — 도메인을 모른다
  domain/      뜻 + 받는 포맷 선언 — region · image · pose · id_map
  store        범주·주소·라이프사이클 + 사이드카(`Structure`)
```

- `stem`·`obj`·`params` 는 층이 아니다 — `Data_Ref` 트리의 쓰임새를 사람이 구분하려고 붙인 이름.
- `Data_Ref` 는 추상 트리만 — 새는 둘을 꺼낸다: `PYTHON_TYPES`(인라인 어휘 → 직렬화) ·
  `Attr`/`Set_attr`(리프 `info["value"]` payload 규약).

#### `port` 해체 — 넷

| 조각 | 소비처 | 간다 |
|---|---|---|
| `Types`·`Blank`·`Infer_type`·`To` | gui 5곳 (core 0) | 도메인 — gui 위반 4곳이 사라진다 |
| 디스패치 · `Load`/`Save`/`Route`/`Path_of` | store 경유 전부 | io — 경로 파생이 이미 거기 |
| `_structure.py` (사이드카 트리) | store 9곳 | store — 리프 값이 아니라 트리 문서 |
| `scan.py` (폴더 스캔) | store 1곳 (`Import`) | **io** — fs 를 걷는 일이다 |

- *"store 만이 port 를 부른다"* 를 검사로 박는 대신 어길 대상을 없앤다.
- 진입점 하나(`Load(root, path, name, ref)` — 인라인·파일 동시 처리)는 io 에 남긴다.
- **스캔은 io 다** — 데이터 모델 관리자가 폴더를 하나하나 보는 게 층 위반이다. store 는 "무엇이
  있나"를 io 에 묻고, "어느 범주에 어떻게 등록하나"만 정한다 (`bucket_store.py:456` 의
  *"발견은 port, 등록은 store"* 가 이미 그 선 — 그 port 조각이 io 로 간다).

#### 밖으로 낸다 — `io` 와 데이터모델 통째로

- `io`·`database` 전부 LENS 밖으로. 부품 도메인(region·image·pose·id_map)도 남기지 않는다.
- 근거: mask 를 rle 로 적는 일도, kind-major 로 경로를 파는 일도 이 프로젝트 고유 지식이 아니다.
  **올려야 다른 곳이 가져다 쓴다.**
- LENS 에 남는 것 = 그것을 쓰는 층(`process`·`export`·`analysis`·`gui`)과 이 프로젝트의 config.
  도메인을 더하는 일도 밖의 작업이 된다.

### staged → split 직행

| | |
|---|---|
| 끝난 것 | `Split_dialog` 가 중간 store 없이 **정본 → 산출 폴더 한 걸음** |
| 죽은 배선 | `gui/app/_main.py` 는 `meta_page.split` 만 import — **`meta_page.sample` 소비처 0** |
| 남은 것 | 스타일(format) 연결 · tasker 잔해 · 검사 surface 1급화 |

#### 스타일(format)이 화면에 안 연결됨

| 있는 것 | 화면 |
|---|---|
| `EXPORTERS[(task, format)]` — imagefolder · coco · yolo · mask | `_dialog.py:35` *"format 은 coco 고정"* |
| `Formats_for(task)` — *"GUI 가 유효 조합만 제시하게"* | 소비처 0 |
| `TASKS` 셋 (classification · detection · segmentation) | `_TASKS` 둘 — `classification` 없음 |

- [ ] split 화면에 **format 선택** 추가 — `Formats_for(task)` 로 유효 조합만, 기본 format 이 맨 앞.
- [ ] `_TASKS` 를 `TASKS` 에서 끌어온다 — 지금 설명 문구가 복제라 두 곳을 고쳐야 한다.

#### 걷을 잔해

- [ ] `Pipeline.Sample`(`core/_base.py:193`) · `Sample_stage` · `Sample_Set` ·
      `Pipeline.Verify`(`core/_base.py:394`, `NotImplementedError`) · `gui/meta_page/sample/`.
- [ ] `core/split.py` 에서 남길 것 가리기 — `_split_for` 의 해시 결정적 배정은 갈래와 무관하게 쓴다.
- [ ] `gui/meta_page/__init__.py` docstring 이 아직 `sample` 을 surface 로 열거.

#### 검사(형상 적합성)를 1급 surface 로

- sample 탭에서 빠져 독립 surface 가 된다. 라벨링은 Meta 뷰어 편집 + 이 평가 surface 양쪽.
- 상세 → [`core/process/TODO.md`](core/process/TODO.md) *"검사를 process 밖으로"* ·
  [`core/analysis/TODO.md`](core/analysis/TODO.md).

### 테스트 재구성 — 지금 테스트가 하나도 없다

구조 정리 중 옛 모델 전제를 깔고 있던 검사들이 발목을 잡아 전부 걷었다. 정리가 끝나면 하나씩 다시 짓는다.

| 잃은 검사 | 지키던 것 | 지금 |
|---|---|---|
| `core/test_layering.py` | 계층 import 방향 · `port` 소비자=store · `schema` cv2-free | 산문만 (`core/README.md` 불변식 ①②③) |
| `gui/test_surfaces.py` | offscreen 으로 전 surface 기동 → 죽은 store-API 호출 검출 | 없음 — 직접 띄워야 안다 |

- gui import 검사(`widgets ← representation ← app`)를 layering 과 **한 벌로** 짓는다.
- 검사가 없는 동안의 재배치는 사람이 경계를 지킨다.

### 그 밖

- [ ] **GUI end-to-end 런타임 검증** — Convert→Run→전이→split→뷰어 실제 구동(코드·import 는 서지만
      데스크톱에서 띄워 본 적 없음).
- [ ] **id_map `extra` 편집 불가** — 편집기는 `부속` 열로 보여주기만
      (`gui/meta_page/view/_id_map_dialog.py:176`). 구조는 이미 맞다
      (`core/format/id_map.py` = 고정은 번호·이름 둘, 나머지는 `extra` 로 통째).
- [ ] **gui 3티어 재편**(`widgets ← representation ← app`) + 폴리곤 편집기 → [`gui/TODO.md`](gui/TODO.md).

## 논의 대상

### 데이터 모델

- **직교 포맷의 이름** — `cartesian`(radial 과 짝) vs `grid`. `raster` 는 직렬화 쪽 말이라 회피.
- **유효 조합을 어디에 적나** — 도메인이 `{받는 포맷}`, 포맷이 `{받는 직렬화}` 를 선언하는 건
  정했는데, 그 선언이 클래스 필드인지 한 곳의 조합표인지는 미정. 지금 `FORMATS` 는 전자다.
- **`image` 가 도메인으로 남나** — 승격 규칙("고유 연산이 있으면")으로 재면 `image` 는 연산이 없다.
  `region` 과 같은 `cartesian` 격자를 쓰고 값만 강도인데, 그 차이가 도메인을 가를 만한지.

### 이관 목적지

`python_toolbox` 는 이미 **축이 둘로 갈려 있다** (실측 — cv2 의존 0 · numpy 의존 0):

| 축 | 파일 |
|---|---|
| 데이터 | `data_schema.py`(직렬화) · `file/`(확장자 디스패치 I/O) |
| 범용 | `registry.py` · `log.py` · `system.py` · `project/` |

| 안 | 중복(`file/`↔`codec/`) | 의존 격리 | 대가 |
|---|---|---|---|
| ① 기존 `python_toolbox` 병합 | 해소 | ✘ — 가벼운 lib 가 cv2·numpy 를 떠안는다 | 없음 |
| ② 신규 toolbox (LENS 것만) | **남는다** | ○ | 디스패치가 계속 두 겹 |
| ③ **`data_toolbox` 로 재편** | 해소 | ○ | `python_toolbox` 소비처의 import 경로가 바뀐다 |

③ = `python_toolbox` 에서 데이터 축(`data_schema` · `file/`)을 뜯어내 LENS 의 `io`·`database` 와
한 패키지로 세우고, 범용 축만 `python_toolbox` 에 남긴다. 두 지표를 다 만족하는 유일한 안이다.
`data_toolbox → python_toolbox`(Registry) 한 방향 의존은 남는다.

- **정할 것**: ③의 대가(다른 프로젝트의 import 경로)를 감당할지. `python_toolbox` 쪽
  `TODO.md`·`ROADMAP.md` 와 함께 봐야 한다.
