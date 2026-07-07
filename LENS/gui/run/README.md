# gui/run/

flow 프로필(= `flows:` 리스트) 빌더. 카드 시퀀스를 편집/저장/불러오기 한다.

빌더 ↔ 실행 분리 — `Run_dialog` 는 편집만, 실행은 메인 버튼이 보유 `Pipeline` 으로 직접 한다.
flow/process 의 의미(unit·carry·outputs 라우팅 등)는
[`../../core/process/README.md`](../../core/process/README.md).

---

## 구성

- `Run_dialog` — 메인 `flow_profile 가져오기` 가 여는 다이얼로그. 닫힐 때 메인이 `flows()` 로 회수.
- `Flow_sequence` — `Flow_card` 목록 추가/삭제/순서 변경.
- `Flow_card` — flow 하나(= `flows:` 1 엔트리) config 편집. flow 는 등록 타입도 preset 도 아니라
  config 가 직접 기술한다 — 카드는 빈 상태로 시작해 수동 구성.

## Flow_card 필드

| 영역 | 내용 |
|---|---|
| 헤더 | `object_type`(진행표시용 자유 명명) · `name`(선택) · `unit`(frame/object) · `cacheable` |
| shared | 모든 step 에 주입할 공통 config (예: `space`) |
| Processes | per-unit 체인. step 마다 [param 폼 \| outputs 라우팅]. `model` 필드 process 는 모델 주입 서브폼 |
| Finalize | 순회 후 1회 도는 체인 (carry 최종값 reduce). outputs 는 level 없이 params 로 |
| carry | 프레임 간 이월할 ctx 키 |

각 step 의 outputs = `meta`(인라인)/`storage`(파일) × `frame`/`object` level (finalize 는 params).
lock 은 UI 를 바꾸지 않고 편집 컨트롤만 동결한다.
