# Builder Tab Guide

Builder 탭은 선택된 scene instance의 공식 배치 파라미터를 수정하는 작업 공간이다.

## 표시 기준

Builder에는 asset root에 `parameters` 스키마가 있는 인스턴스만 표시된다. `metadata`, geometry 내부 값, child node 구조는 Builder 노출 기준으로 사용하지 않는다.

## 파라미터 조작

- `number`, `integer`, `string`, `boolean` 파라미터를 지원한다.
- `unit: "rad"` 파라미터는 UI에서 degree로 표시하고 내부 저장값은 radian으로 유지한다.
- 값 변경 시 선택된 인스턴스만 재빌드한다.

## 저장되는 데이터

Builder 변경값은 scene instance의 `params`에 저장된다. 예를 들어 conveyor는 `length`, `legGap`만 저장하고, robot은 `j1Yaw`부터 `j6Pitch`까지의 joint pose 값을 저장한다.

Asset 원본 JSON은 Builder에서 수정하지 않는다. 새 asset 정의나 구조 변경은 Asset Editor에서 처리한다.
