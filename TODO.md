# TODO

## Builder 탭

- [ ] Builder 값 변경 시 선택 인스턴스만 재빌드되는 흐름을 conveyor 예제로 검증

## Asset Editor

- [ ] anchor `exposed` 정책 문서화: 노출 anchor는 Scene tree 조작 대상, 내부 anchor는 asset 생성 규칙으로만 사용
- [ ] 갱신된 asset 정의를 기존 장면 인스턴스에 반영하는 정책 정의
- [ ] 같은 파일명 저장은 덮어쓰기, 새 파일명 저장은 새 에셋 등록으로 동작하는지 수동 검증

## 저장 / 불러오기

- [ ] 하나의 에셋 정의로 서로 다른 파라미터 인스턴스를 여러 개 복원할 수 있는지 검증

## 검증

- [ ] 하나의 `conveyor` 에셋으로 5m, 10m 컨베이어를 동시에 배치하는 시나리오 테스트
- [ ] 하나의 `robot` 에셋으로 서로 다른 joint pose 인스턴스를 동시에 배치하는 시나리오 테스트
- [ ] 루트 배치, 루트 삭제, anchor attach, anchor detach 흐름 테스트
- [ ] 편집된 asset을 Asset Editor에서 덮어쓰기 / 새 이름 저장하는 케이스 테스트
