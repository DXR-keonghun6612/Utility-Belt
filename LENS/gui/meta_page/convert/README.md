# gui/meta_page/convert/

Converter 패널 — raw 소스를 탐색해 초기 `Dataset_Meta` 를 생성하는 설정 UI.

별도 다이얼로그(`page._Converter_dialog`)에 담긴다 — 부트스트랩(raw→meta)은 dataset 당
한 번 쓰는 단계라서다. `Pipeline.Convert()` 를 실행할 설정을 구성하고, `{"converter": {...}}`
(Pipeline_config 의 converter 섹션)로 직렬화한다.

핸들러·서술자 규약은 [`../../../core/port/README.md`](../../../core/port/README.md) 참조 (들이기 자체는
`meta.Import` — 라이프사이클은 store 소유).

---

## 패널 구성

```
Converter_panel
  ├── object_type     glob (현재 고정 — _CONVERTER_WIDGETS dict 등록 기반)
  └── _Glob_settings
        ├── sources   raw 소스 디렉터리 목록
        ├── globs     key → {pattern, ext?, type, format?}   (라벨 특수처리 없음)
        └── params    key → 파일 경로 (dataset-wide root leaf; id_map 등도 특수 필드 없이 여기로)
```

> `id_map`(class→정수) 은 converter 가 소유하지 않는다 — 파생(sample) 계층 소유이고 Convert 는
> 소비하지 않는다. 예전의 전용 id_map 입력은 제거했다(필요하면 제네릭 `params` 로 넣는다).

`globs` 행은 `종류(key) | stem 패턴 | 확장자(ext) | type | format`. **세 필드가 각각 다른 일을 한다:**

| 필드 | 하는 일 |
|---|---|
| `pattern` + `ext` | **파일을 찾는다** — 합쳐서 glob (`*_rgb` + `png` → `*_rgb.png`). `ext` 는 **소스** 확장자 |
| `type` | **핸들러** — **필수**. 확장자로 추론하지 않는다 |
| `format` | **서술자 detail** (선택) — 파일이면 비운다. 인라인(`attr`)은 `Save` 가 값의 파이썬 타입으로 채운다 |

**`type` 을 추론하지 않는 이유** — 같은 `png` 라도 `image`(색 이미지)일 수도 `segmap`(라벨맵)일 수도 있다.
추론은 **둘 중 하나를 말없이 고르는 것**이라 한 줄 더 쓰게 한다.

**`format` 을 파일에 주지 마라** — 저장은 복사(`shutil.copy2`)라 **변환이 아니다.** 소스가 `.jpg` 인데
`format: png` 를 주면 JPEG 바이트가 `.png` 이름으로 앉는다(깨진 파일). 비우면 소스 확장자를 그대로 쓴다.

**아무것도 못 찾으면 조용히 넘어가지 않는다** — 어느 종류가 몇 개 잡혔는지와 함께 실패한다. 예전엔 패턴이
틀려도 빈 목록만 떴다(무엇이 잘못됐는지 알 길이 없었다).

**저장 위치를 정하는 칸은 없다.** 경로는 트리 위치에서 파생된다(kind-major) — **종류 key 가 곧 폴더**이고
동시에 **process 가 ctx 에서 읽는 이름**이다(`frame` → `modified/frame/{stem}.png`, flow 의 process 가
`frame` 으로 받는다). 옛 `dir` 오버라이드는 없어졌다 — 두 곳이 위치를 정하면 어긋난다.

---

## 출력 (dict)

```python
{
    "converter": {
        "object_type": "glob",
        "sources": ["/path/to/raw"],
        "globs": {
            "frame":    {"pattern": "*_rgb",   "ext": "png", "type": "image"},
            "class_id": {"pattern": "*_label", "ext": "txt", "type": "attr"},   # 인라인 값
            "mask":     {"pattern": "*_mask",  "ext": "png", "type": "segmap"}, # png 지만 라벨맵!
        },
        "params": {"roi": "/path/to/roi.png"},
    }
}
```

이 dict 를 메인 보유 `Pipeline` 에 `set_converter` 로 주입한 뒤 그 위에서 `Convert()` 를 돌린다
(별도 throwaway Pipeline 없음). 완료 시 메인이 meta 뷰를 in-place 갱신한다. converter 설정
저장/불러오기는 다이얼로그 안에.

---

## 소유 ↔ 배치

패널은 콤보·상태 라벨·Convert 버튼을 소유(상태관리)하되, 배치는 호스트(다이얼로그)가
`format_combo()`/`status_label()`/`run_button()` 으로 가져가 한다. dataset_root 도 호스트가
관리하고, 패널엔 `get_pipeline` 콜백만 준다 — 실행 대상 Pipeline 은 그때그때 메인 것.
