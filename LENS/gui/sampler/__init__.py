"""gui/sampler — 파생 tasker 빌더 창 + tasker별 sample 뷰어.

Sampler 창(``Sampler_dialog``)이 tasker 목록·설정·``▶ sample`` 실행을, 뷰어(``Sample_viewer``)가
split→class→sample 트리 + crop 미리보기 + class write-back 을 맡는다. core sample tasker 계층 위에서
동작한다 — 설계는 [`../../core/sampler/README.md`](../../core/sampler/README.md).
"""

from gui.sampler._dialog import Sampler_dialog
from gui.sampler._viewer import Sample_viewer

__all__ = ["Sampler_dialog", "Sample_viewer"]
