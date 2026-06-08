# Scene Tab Guide

Scene 탭은 현재 장면 상태를 확인하고, 인스턴스를 배치하거나 제거하는 작업 공간이다. Scene root 자체는 표시하지 않고 root 아래의 직계 인스턴스부터 보여준다.

## 주요 역할

- root 객체 목록을 확인한다.
- root에 새 asset 인스턴스를 추가하거나 기존 인스턴스를 삭제한다.
- 노출된 anchor(`exposed: true`)에 asset 인스턴스를 attach/detach한다.
- 선택한 객체의 transform을 조정한다.
- 노출 anchor의 layout을 scene instance override로 수정한다.
- scene JSON을 저장하거나 불러온다.

## Tree 조작

- `SCENE GRAPH` 제목 옆 `+` 버튼으로 root 인스턴스를 추가한다.
- root 인스턴스의 `×` 버튼으로 해당 인스턴스를 삭제한다.
- 빈 anchor의 `+` 버튼으로 asset을 attach한다.
- attach된 anchor의 `×` 버튼으로 anchor를 비운다.
- Array anchor는 펼쳤을 때 `slot N` 행을 표시한다.
- Array anchor의 빈 slot `+` 버튼으로 해당 칸에만 asset을 attach한다.
- Array anchor의 채워진 slot `×` 버튼으로 해당 칸만 비운다.

## Inspector 조작

선택한 node의 transform을 수정할 수 있다. Anchor를 선택하면 `kind`, `axis`, `count`, `gap`, `start` layout 값을 수정할 수 있다.

Anchor layout 수정값은 asset 원본을 바꾸지 않고, 현재 scene instance의 `anchorOverrides`로 저장된다.

## 저장 / 불러오기

`Save Scene`은 현재 scene instance 상태를 JSON으로 저장한다. 저장되는 주요 값은 `model`, `instanceId`, `params`, `anchorOverrides`, transform override다.

`Load Scene`은 저장된 JSON을 공용 asset 정의와 조합해 장면을 복원한다.
