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
        ├── globs     key → {pattern, type?, dir?, format?}   (라벨 특수처리 없음)
        └── params    key → 파일 경로 (dataset-wide root leaf; id_map 등도 특수 필드 없이 여기로)
```

> `id_map`(class→정수) 은 converter 가 소유하지 않는다 — 파생(sample) 계층 소유이고 Convert 는
> 소비하지 않는다. 예전의 전용 id_map 입력은 제거했다(필요하면 제네릭 `params` 로 넣는다).

`globs` 행은 `key | pattern | type | dir | format`. `type` 을 비우면 패턴 확장자로 핸들러를
추론하고(`Infer_type`), txt 등 추론 안 되는 건 `type` 을 명시한다 (예: `attr`). 모든 glob key 가
`type` 으로 핸들러가 갈린다 — 특수 취급되는 key 는 없다.

---

## 출력 (dict)

```python
{
    "converter": {
        "object_type": "glob",
        "sources": ["/path/to/raw"],
        "globs": {
            "frame":    "*_pose.png",                       # type 생략 → 확장자 추론
            "class_id": {"pattern": "*_pose.txt", "type": "attr"},
            "mask":     {"pattern": "*_mask.png", "type": "image", "dir": "raw_mask"},
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
