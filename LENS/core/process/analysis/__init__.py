"""analysis — **아직 흡수되지 않은 덩어리** (계층이 아니다).

옛 ``Analysis`` 계약(analyze/report/figure + 레지스트리 + ``present``)은 **구현자 0·등록 0·호출 0** 이라
삭제했다. 아무도 구현하지 않는 추상이었고, 실제 소비처(``gui/…/sample/_tab.py``)는 계약을 무시하고 모듈
함수를 직접 import 했다. 그래서 "연산은 stream/analysis 두 종류"라는 서술은 **근거가 없다 — 하나뿐이다.**

남은 모듈은 자유함수 묶음이고, 갈 곳이 정해져 있다 ([`../TODO.md`](../TODO.md)):

- **형상 계산**(align·features·polar) → **끝났다.** `torch_toolbox.modules.transform.mask` 로 승격해
  학습과 같은 모듈을 쓴다. 남은 계산(`chroma/stats`)만 [`../func/`](../func) 대상이다.
- **chroma 진단** → params(누산기)를 읽는 자유함수. 누산기는 이미 영속이라 엔진이 필요 없다.
- **shape 군집**(umap/hdbscan) → **산출물 소비자**로 남는다. sample export 폴더를 훑어 군집하고 GUI 가
  파라미터를 바꿔 **재실행**한다 — finalize 로 접으면 "재군집하려면 파이프라인을 다시 돌려야" 하는
  기능 퇴행이다. 파이프라인과 **수명이 다르다.**

그때까지는 소비처가 하위 모듈을 직접 import 한다 (지금도 그렇다).
"""
