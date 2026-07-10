"""gui/sampler — 파생 tasker 탭 창 (tasker 마다 탭 = 툴바 + sample 편집 뷰).

Sampler 창(``Sampler_dialog``)은 ``QTabWidget`` 컨테이너 — 탭 한 칸(``Tasker_tab``)이 레시피 편집
(``프로필 편집``)·빌드(``▶ sample``)·내보내기(``▶ split 처리``)와 sample 편집 뷰(``Sample_view``:
group→sample 트리 + crop 미리보기 + class write-back)를 소유한다. core sample tasker 계층 위에서
동작한다 — 설계는 [`../../core/sampler/README.md`](../../core/sampler/README.md).
"""

from gui.meta_page.sample._dialog import Sampler_dialog

__all__ = ["Sampler_dialog"]
