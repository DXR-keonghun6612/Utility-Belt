"""gui/app — 연결층(app 셸). ``Main_page`` 가 보유 ``Pipeline``(정본 단일 소스)을 소유하고, meta_page
갈래의 창/다이얼로그를 가져다 배선·주입한다. 백그라운드 meta 연산은 ``Meta_ops``(``_meta_ops``) 소유.
표현은 안 가짐 — 총괄=소유(place), 부분=주입(contract).
"""

from gui.app._main import Main_page

__all__ = ["Main_page"]
