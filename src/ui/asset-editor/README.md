# Asset Editor Guide

Asset Editor는 새 asset을 만들거나 기존 asset 정의를 수정하는 별도 화면이다.

## Source Of Truth

현재 Asset Editor의 기준 데이터는 `ASSET DATA` JSON이다. `parameters`, `computed`, `definitions`, inline `defaultNode` 같은 구조를 보존하려면 JSON을 직접 수정하고 `Apply JSON`으로 preview를 재빌드한다.

## 주요 조작

- `New`: 새 빈 asset draft를 만든다.
- `Load JSON`: 로컬 JSON 파일을 불러온다.
- `Format JSON`: `ASSET DATA` 내용을 정렬한다.
- `Apply JSON`: JSON을 기준으로 preview와 node tree를 재빌드한다.
- `Save JSON`: 파일명을 입력해 JSON을 저장한다.
- `Send to Scene`: 현재 JSON을 메인 Scene Editor에 런타임 등록한다.

## Node 편집

Tree와 Geometry Editor는 단순 asset이나 빠른 preview 수정에 사용할 수 있다. 단, `definitions`를 쓰는 asset은 tree 기반 저장이 구조를 깨뜨릴 수 있으므로 `ASSET DATA` JSON을 직접 편집해야 한다.

## 데이터 구조 예시

- `parameters`: Builder에 노출될 인스턴스 파라미터 스키마
- `computed`: `parameters`에서 계산되는 내부 값
- `definitions`: 깊은 node tree를 평활화하기 위한 내부 descriptor map
- `defaultNode`: anchor 내부 반복 배치에 사용할 inline descriptor
- `defaultModel`: asset DB에 등록된 외부 asset을 anchor에 배치할 때 사용하는 참조
