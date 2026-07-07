"""SAM3 추론 backend — segment 정책이 쓰는 저수준 프리미티브(encode/run) 래퍼.

모델 고유부만 담는다: 모델 빌드·수명주기(``_ensure``), inference 컨텍스트(``infer_ctx``),
프레임 인코딩(``encode``), interactive 디코드 1회 정규화(``run``). best mask 선택·이진화·
box 배치·구멍 보존 같은 정책은 여기 없다 — ``model/segment`` 가 이 프리미티브 위에서 조립한다.
다른 promptable segmenter 로 교체하려면 같은 계약(``infer_ctx``/``encode``/``run``)만 구현하면 된다.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any

import cv2
import numpy as np


def _as_np(x: Any) -> np.ndarray:
    """torch/np(확률·logit·bool) → float32 numpy. numpy 는 bfloat16 불가라 tensor 는 캐스팅."""
    if hasattr(x, "detach"):
        return x.detach().float().cpu().numpy()
    return np.asarray(x, dtype=np.float32)


class Sam3_runner:
    """SAM3 backend — 모델 1회 빌드·캐싱 + ``encode``/``run`` 프리미티브.

    정책(``model/segment``)이 의존하는 계약:

    - ``infer_ctx`` — ``torch.inference_mode`` + (cuda 면) bfloat16 autocast 엔벨로프.
      정책이 프레임 1장의 encode·여러 run 을 이 컨텍스트로 감싼다.
    - ``encode`` — 프레임 → inference state. 비싼 이미지 backbone 은 여기 1회뿐.
    - ``run`` — state + box/points 프롬프트 → interactive 디코드 1회를 numpy 로 정규화.

    ``predict_inst`` 는 호출 끝에 predictor feature 를 비워 inference 루프 메모리 누적이 없다.
    """

    def __init__(self, *, bpe_path: str = "", checkpoint: str = "",
                 device: str = "cuda") -> None:
        self.bpe_path   = bpe_path
        self.checkpoint = checkpoint
        self.device     = device
        self._model: Any     = None
        self._processor: Any = None

    # ── 모델 수명주기 ────────────────────────────────────────────────────────────
    def _ensure(self) -> None:
        if self._model is not None:
            return
        from sam3 import build_sam3_image_model                # noqa: PLC0415
        from sam3.model.sam3_image_processor import Sam3Processor  # noqa: PLC0415

        print(f"[sam3] 모델 빌드 (1회, device={self.device}) …")
        self._model = build_sam3_image_model(
            bpe_path=self.bpe_path or None,
            device=self.device,
            checkpoint_path=self.checkpoint or None,
            load_from_HF=not self.checkpoint,
            enable_inst_interactivity=True,
        )
        self._processor = Sam3Processor(self._model)

    # ── 프리미티브 (정책이 의존하는 계약) ────────────────────────────────────────
    @contextmanager
    def infer_ctx(self):
        import torch                                           # noqa: PLC0415
        with torch.inference_mode():
            if str(self.device).startswith("cuda") and torch.cuda.is_available():
                with torch.autocast("cuda", dtype=torch.bfloat16):
                    yield
            else:
                yield

    def encode(self, frame_bgr: np.ndarray, *,
               text: str | None = None, conf: float = 0.5) -> Any:
        """프레임 → inference state. 이미지 backbone 1회 + (있으면) text concept 1회 얹기.

        비싼 이미지 인코딩은 여기 1회뿐 — 이후 box/point ``run`` 디코드는 가볍다.
        """
        self._ensure()
        from PIL import Image                                  # noqa: PLC0415

        _pil   = Image.fromarray(cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB))
        _state = self._processor.set_image(_pil)
        if text:                                               # text 는 concept 로 state 에 얹는다
            self._processor.set_confidence_threshold(conf, _state)
            _state = self._processor.set_text_prompt(text, _state)
        return _state

    def run(self, state: Any, **kwargs
            ) -> tuple[list, np.ndarray, np.ndarray | None] | None:
        """``predict_inst`` 1회 → ``(masks[list HxW], scores[np], low_res[np|None])`` 정규화.

        None/빈 출력은 None 으로, 점수·저해상 logit 은 numpy 로 정리해 정책이 다루기 쉽게 한다.
        ``box``/``point_coords``/``point_labels``/``mask_input``/``multimask_output``/
        ``return_logits`` 등 ``predict_inst`` 인자를 그대로 넘긴다.
        """
        _res = self._model.predict_inst(state, **kwargs)
        if _res is None:
            return None
        _masks, _scores, _low = _res
        if _masks is None or len(_masks) == 0:
            return None
        _arr  = np.asarray(_masks)
        _flat = list(_arr.reshape(-1, *_arr.shape[-2:]))
        _sc   = _as_np(_scores).reshape(-1)
        _lw   = _as_np(_low) if _low is not None else None
        return _flat, _sc, _lw
