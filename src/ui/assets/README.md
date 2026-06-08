# Assets Tab Guide

ASSETS 탭은 프로젝트에 등록된 asset DB를 확인하고, 선택한 asset을 Asset Editor로 여는 작업 공간이다.

## Asset DB 구조

Asset DB는 파일 시스템 폴더 구조를 기준으로 분류한다.

```text
src/asset/<category>/<subcategory>/<asset>.json
```

예시는 다음과 같다.

```text
src/asset/passive/general/conveyor.json
src/asset/active/general/vision_robot.json
```

## 주요 조작

- Tree에서 category, subcategory, asset 이름을 확인한다.
- Asset을 선택하면 기본 정보와 경로를 확인한다.
- `Edit Asset`으로 선택한 asset을 Asset Editor에서 연다.
- `Add`로 빈 Asset Editor 창을 연다.

## 정책

현재 ASSETS 탭은 읽기 전용 tree다. 이동, 삭제, 이름 변경은 서버 또는 파일 시스템 연동 이후 별도 관리 기능으로 검토한다.

Asset 저장은 Asset Editor에서 파일명 입력 기반으로 처리한다. 같은 파일명이면 런타임 등록값을 덮어쓰고, 새 파일명이면 새 asset으로 등록한다.
