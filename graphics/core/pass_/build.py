from graphics.core.pass_.registry import Pass_Registry

from graphics.core.pass_.depth import Depth_Pass
from graphics.core.pass_.normal import Normal_Pass
from graphics.core.pass_.rgb import RGB_Pass
from graphics.core.pass_.segmentation import Segmentation_Pass


def Get_render(
    render_name: str
) -> Depth_Pass | Normal_Pass | RGB_Pass | Segmentation_Pass:
    return Pass_Registry.Get(render_name)()
