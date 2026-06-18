from .extract_hs import Extract_hs_process
from .extract_mask_with_hs_stats import Extract_mask_hs_process
from .extract_mask_sam3 import Extract_mask_sam3_process
from .frame_crop import Frame_crop_process
from .load_frame import Load_frame_process
from .normalize_mask import Normalize_mask_process
from .save_frame import Save_process

FRAME_PROCESS = (
    Extract_hs_process
    | Extract_mask_hs_process
    | Extract_mask_sam3_process
    | Frame_crop_process
    | Load_frame_process
    | Normalize_mask_process
    | Save_process
)
