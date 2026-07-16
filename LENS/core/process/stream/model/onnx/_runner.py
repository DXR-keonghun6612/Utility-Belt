"""onnx 세션 — 기능 무관 공용부. 스펙대로 feed·fetch 하는 일만 한다.

**여기엔 전처리도 후처리도 없다** — 배열을 넣으면 배열이 나온다. 무엇을 넣을 배열로 만들고 나온 배열을
무엇으로 읽을지는 **기능마다 다르므로**, 기능 클래스가 이 위에 앉아 자기 전/후처리를 든다
(예: [`Onnx_segmenter`](segment.py) — 프레임을 배치로 싸서 넣고 mask logits 로 읽는다).

**교체 단위는 onnx 파일 하나다.** 무엇을 받고 무엇을 내는지는 코드가 아니라 파일이 알고 있으므로
([`Model_spec`](_spec.py)), 같은 기능의 다른 모델로 갈아타는 건 ``weights/`` 에 ``foo.onnx`` +
``foo_rt_cfg.yaml`` 을 떨구고 config 의 ``onnx_file:`` 한 줄을 바꾸는 것이다 — 기능 클래스는 그대로.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from ._spec import Model_spec

#: 상대 ``onnx_file`` 의 기준 — 가중치는 코드와 섞이지 않게 여기 모은다(파일은 gitignore).
WEIGHTS_DIR = Path(__file__).parent / "weights"

#: 실행 provider — **CUDA 전용**. CPU fallback 은 두지 않는다(아래 ``_ensure`` 참고).
_PROVIDER = "CUDAExecutionProvider"


class Onnx_runner:
    """onnx 세션 1회 빌드·캐싱 + ``Infer`` 프리미티브 — **기능 클래스의 base**.

    직접 쓰지 않는다(``MODEL_BUILDERS`` 에도 없다). 기능 클래스가 상속해 자기 전/후처리를 얹는다.
    그 기능 클래스가 의존하는 계약은 둘이다:

    - ``Spec`` — 모델의 입출력 스펙([`Model_spec`](_spec.py)). **세션 없이도 답한다**(그래프 헤더만
      읽으므로 가볍고 CUDA 도 필요 없다). 기능 클래스는 이걸로 입·출력 크기를 알아내 상수를 안 박는다.
    - ``Infer`` — 입력 배열들 → 출력 배열들. 스펙 순서대로 feed 하고 스펙대로 대조한다.

    무거운 세션 빌드는 [`Pipeline._RESOURCE_POOL`](../../../../_base.py) 이 스펙당 1회만 하고 공유한다.
    """

    def __init__(self, *, onnx_file: str, cfg_file: str = "", device_id: int = 0) -> None:
        """Args:
            onnx_file: onnx 파일 경로. 상대경로면 ``weights/`` 기준으로 푼다(cfg 가 파일명만 줘도 되게).
            cfg_file: cfg 경로. 비우면 규약(``{stem}_rt_cfg.yaml``)으로 옆에서 찾는다.
            device_id: CUDA 디바이스 번호.
        """
        self.onnx_file = onnx_file
        self.cfg_file  = cfg_file
        self.device_id = device_id
        self._spec: Model_spec | None = None
        self._sess: Any               = None

    @property
    def Path_of(self) -> Path:
        """푼 onnx 절대경로 — 상대경로면 ``weights/`` 기준."""
        _p = Path(self.onnx_file)
        return _p if _p.is_absolute() else WEIGHTS_DIR / _p

    @property
    def Spec(self) -> Model_spec:
        """이 모델의 입출력 스펙 (첫 접근에 파싱해 캐싱 — 세션 빌드와 무관하다)."""
        if self._spec is None:
            self._spec = Model_spec.Parse(self.Path_of, self.cfg_file or None)
        return self._spec

    def _ensure(self) -> None:
        """세션 1회 빌드 — **CUDA 가 없으면 터진다.**

        예전엔 CUDA→CPU 로 떨어졌는데, 그건 성능이 소리 없이 죽는 길이었다(같은 코드가 몇십 배 느리게
        "돌긴 도는" 상태). GPU 전용이므로 provider 가 없으면 부재를 드러낸다.

        Raises:
            RuntimeError: onnxruntime 에 CUDA provider 가 없으면 (CPU 빌드이거나 설치가 깨진 것).
        """
        if self._sess is not None:
            return
        import onnxruntime as ort                                 # noqa: PLC0415

        _avail = ort.get_available_providers()
        if _PROVIDER not in _avail:
            raise RuntimeError(
                f"onnxruntime 에 {_PROVIDER} 가 없다 (가용: {_avail}). GPU 전용이라 CPU 로 떨어지지 "
                f"않는다 — pip install --no-cache-dir onnxruntime-gpu 로 GPU 빌드를 설치하라.")
        print(f"[onnx] 세션 빌드 (1회, {self.Path_of.name}, cuda:{self.device_id}) …")
        self._sess = ort.InferenceSession(
            str(self.Path_of), providers=[(_PROVIDER, {"device_id": self.device_id})])
        self._verify_graph()

    def _verify_graph(self) -> None:
        """세션이 본 IO 이름과 스펙이 같은지 — 다르면 스펙 파싱이 거짓이라는 뜻이라 터뜨린다."""
        _sess_io = ([_i.name for _i in self._sess.get_inputs()],
                    [_o.name for _o in self._sess.get_outputs()])
        _spec_io = ([_t.name for _t in self.Spec.inputs],
                    [_t.name for _t in self.Spec.outputs])
        if _sess_io != _spec_io:
            raise RuntimeError(f"세션 IO 가 스펙과 다르다 — 세션 {_sess_io}, 스펙 {_spec_io}\n"
                               f"{self.Spec.Describe()}")

    def Infer(self, *arrays: np.ndarray) -> list[np.ndarray]:
        """입력 배열들 → 출력 배열들 (둘 다 **스펙 순서** 그대로).

        각 배열을 feed 전에 스펙과 대조해([`Tensor_spec.Check`](_spec.py)) 어긋나면 어느 텐서가
        왜 틀렸는지와 함께 터뜨린다 — onnxruntime 이 내는 오류보다 짚기 쉽게.

        Args:
            *arrays: 모델 입력 순서대로의 배열. 개수가 스펙과 다르면 raise.

        Returns:
            모델 출력 순서대로의 배열 리스트 (모델이 낸 shape 그대로 — 복원·정리는 정책이).

        Raises:
            ValueError: 입력 개수·dtype·shape 이 스펙과 다르면.
            RuntimeError: CUDA provider 가 없으면.
        """
        _spec = self.Spec
        if len(arrays) != len(_spec.inputs):
            raise ValueError(f"입력 개수 불일치 — 모델은 {len(_spec.inputs)}개"
                             f"({[_t.name for _t in _spec.inputs]}), 받은 건 {len(arrays)}개")
        _feed = {}
        for _t, _a in zip(_spec.inputs, arrays):
            _arr = np.ascontiguousarray(_a)
            _t.Check(_arr)
            _feed[_t.name] = _arr
        self._ensure()
        _outs = self._sess.run([_t.name for _t in _spec.outputs], _feed)
        return [np.asarray(_o) for _o in _outs]
