"""기능: 전경 분할 — 프레임 한 장 → 전경 mask logits 한 장 (프롬프트 없음).

onnx backend 는 **기능별로 나뉜다.** 파일 하나를 돌리는 일은 다 같아도([`Onnx_runner`](_runner.py)),
프레임을 어떤 배열로 싸서 넣고 나온 배열을 무엇으로 읽을지는 기능이 정하기 때문이다. 이 모듈이 그
"전경 분할" 기능의 전/후처리를 든다 — 다른 기능(분류·키포인트 …)이 생기면 옆에 새 파일로 낸다.

**바뀔 수 있는 건 onnx 파일 하나다.** 같은 기능의 다른 모델로 갈아타는 건 ``weights/`` 에 onnx+cfg 를
떨구고 config 의 ``onnx_file:`` 을 바꾸는 것뿐 — 입력 크기·출력 크기가 달라져도 스펙에서 읽으므로
이 코드도 정책도 안 바뀐다.

**SAM3([`../torch/_sam3.py`](../torch/_sam3.py))와 계약이 다르다.** SAM3 는 box 프롬프트로 객체를 하나씩
분할하지만(``encode``/``run``), 이 기능은 프레임을 통째로 받아 전경 logits 한 장을 낸다 — 인스턴스
분리는 downstream 이 connected-components 로 한다.
"""

from __future__ import annotations

import numpy as np

from ._runner import Onnx_runner


class Onnx_segmenter(Onnx_runner):
    """ONNX 전경-분할 backend — ``Infer_logits`` 계약 하나.

    정책([`Detect_instances`](../detect/_base.py))은 ``Infer_logits(frame_bgr) -> (H', W')`` 만 안다.

    **이진화는 하지 않는다** — sigmoid·threshold 는 사용자가 GUI 로 돌리는 정책 파라미터라 정책이 든다.
    여기서 미리 이진화하면 그 손잡이가 사라진다.

    **layout 을 묻지 않는다.** 전처리(flip·NHWC→NCHW·정규화·crop)가 전부 그래프에 내장돼 raw BGR 을
    그대로 받으므로 이쪽이 할 일은 배치 축을 씌우는 것뿐인데, 그게 모델과 안 맞으면
    [`Tensor_spec.Check`](_spec.py) 의 shape 대조가 잡는다. 출력의 공간 크기도 ``squeeze`` 가 내주므로
    (아래) NHWC/NCHW 를 알 필요가 없다.
    """

    def Infer_logits(self, frame_bgr: np.ndarray) -> np.ndarray:
        """BGR 프레임 ``(H, W, 3)`` → 전경 mask logits ``(H', W')``.

        전처리는 배치 축 하나, 후처리는 ``squeeze``. **squeeze 가 layout 문제를 없앤다** — 이 기능의
        출력은 mask 한 장(채널 1)이라 NCHW ``(1,1,H',W')`` 든 NHWC ``(1,H',W',1)`` 든 **같은 메모리
        배열**이고, 크기 1인 축을 걷어내면 둘 다 ``(H', W')`` 로 떨어진다. 그래서 축 순서를 몰라도 된다.

        남은 축이 2-D 가 아니면 mask 한 장이 아니라는 뜻이라 터뜨린다 — 채널 여럿(멀티클래스)이면 이
        기능이 아니고, 그때는 layout 이 실제로 의미를 갖는다(이 클래스로 다룰 수 없다).

        Args:
            frame_bgr: 원본 BGR 프레임. 모델 입력 스펙과 같은 크기·dtype 이어야 한다.

        Returns:
            전경 logits ``(H', W')`` — 원본보다 작을 수 있다(모델이 crop 하므로).

        Raises:
            ValueError: 프레임이 입력 스펙과 안 맞거나, 출력이 mask 한 장이 아니면.
            RuntimeError: CUDA provider 가 없으면.
        """
        _outs = self.Infer(frame_bgr[None])
        if len(_outs) != 1:
            raise ValueError(f"{type(self).__name__} 은 출력이 1개인 모델용이다 (지금 {len(_outs)}개)\n"
                             f"{self.Spec.Describe()}")
        _sq = np.squeeze(_outs[0])
        if _sq.ndim != 2:
            raise ValueError(f"출력이 mask 한 장이 아니다 — squeeze 후 {list(_sq.shape)} "
                             f"(채널이 여럿이면 이 기능이 아니다)\n{self.Spec.Describe()}")
        return _sq
