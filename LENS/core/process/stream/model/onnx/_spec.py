"""onnx 모델 스펙 — 파일이 스스로 자기 입출력을 설명하게 한다.

**진실은 onnx 그래프다.** 입출력의 이름·dtype·shape 는 전부 그래프 안에 이미 있으므로 여기서 읽는다
(예전엔 ``input_name="image"`` 같은 기본값으로 코드에 베껴 적었고, 파일을 바꾸면 조용히 어긋났다).

**cfg(``*_rt_cfg.yaml``)는 읽기만 한다 — 우리 필드를 얹지 않는다.** cfg 는 변환 툴이 onnx 와 함께 매번
**생성**하는 산출물이라 우리가 뭘 적어도 재-export 가 지운다(실제로 그렇게 잃었다). 그래서 여기서 cfg 는
**대조자**일 뿐이다: 같은 입출력을 한 번 더 적고 있으니 그래프와 맞대보고 어긋나면 터뜨린다(중복은 어차피
생기니, 중복이 거짓말하는 것만 막는다). ``precision`` 등 TensorRT knob 은 보관만 한다.

**layout(NHWC/NCHW)은 묻지도 추론하지도 않는다.** ``[1,600,800,3]`` 과 ``[1,1,588,798]`` 은 둘 다 4-D
정수라 숫자만으론 구분되지 않지만, **애초에 알 필요가 없다** — 우리가 넣는 배열이 틀린 배치면
``Tensor_spec.Check`` 의 shape 대조가 어느 축이 다른지 짚어 터뜨리고, 출력의 공간 크기는 채널이 1인 한
``squeeze`` 가 layout 과 무관하게 같은 답을 낸다([`Onnx_segmenter`](segment.py)). 이름을 물어보는 건
그래서 요구할 자격이 없는 정보였다.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

#: cfg 파일명 규약 — ``detection.onnx`` ↔ ``detection_rt_cfg.yaml`` (같은 폴더).
CFG_SUFFIX = "_rt_cfg.yaml"

#: onnx ``TensorProto.DataType`` 이름 → numpy dtype 이름. 필요한 것만 (없는 건 raise 로 드러난다).
_NP_DTYPE: dict[str, str] = {
    "UINT8": "uint8", "INT8": "int8", "UINT16": "uint16", "INT16": "int16",
    "INT32": "int32", "INT64": "int64", "FLOAT": "float32", "FLOAT16": "float16",
    "DOUBLE": "float64", "BOOL": "bool",
}

@dataclass(frozen=True)
class Tensor_spec:
    """모델 입출력 텐서 하나 — 그래프가 준 ``name``/``dtype``/``shape`` 그대로.

    Attributes:
        name: 그래프의 텐서 이름 (onnxruntime feed/fetch key).
        dtype: numpy dtype 이름 ("uint8"·"float32" …).
        shape: 고정 shape. 동적 축은 -1 (프로파일이 고정한 모델은 안 나온다).
    """

    name:   str
    dtype:  str
    shape:  tuple[int, ...]

    def Check(self, arr: np.ndarray) -> None:
        """feed 배열이 이 스펙과 맞는지 — 안 맞으면 raise.

        onnxruntime 이 내는 shape/dtype 오류는 어느 텐서인지 알기 어렵다. 세션에 넣기 전에 여기서
        이름과 함께 터뜨려 호출 측이 무엇을 잘못 줬는지 바로 알게 한다.

        Raises:
            ValueError: dtype 또는 shape 이 스펙과 다르면 (동적 축 -1 은 통과).
        """
        if arr.dtype.name != self.dtype:
            raise ValueError(f"입력 {self.name!r} dtype 불일치 — 모델은 {self.dtype}, "
                             f"받은 건 {arr.dtype.name}")
        if len(arr.shape) != len(self.shape):
            raise ValueError(f"입력 {self.name!r} 차원 불일치 — 모델은 {list(self.shape)}, "
                             f"받은 건 {list(arr.shape)}")
        _bad = [(_i, _e, _g) for _i, (_e, _g) in enumerate(zip(self.shape, arr.shape))
                if _e >= 0 and _e != _g]
        if _bad:
            raise ValueError(f"입력 {self.name!r} shape 불일치 — 모델은 {list(self.shape)}, "
                             f"받은 건 {list(arr.shape)} (축 {[_b[0] for _b in _bad]})")

    def __str__(self) -> str:
        return f"{self.name}  {self.dtype}  {list(self.shape)}"


@dataclass(frozen=True)
class Model_spec:
    """onnx 파일 하나의 입출력 계약 — 그래프에서 읽고 (cfg 가 있으면) 대조까지 마친 결과.

    세션 없이 만들어진다(그래프 헤더만 읽으므로 가볍고 CUDA 도 필요 없다). 그래서 정책·GUI 가 모델을
    빌드하지 않고도 "이 파일이 뭘 받고 뭘 내는지" 를 물어볼 수 있다 — ``Describe`` 가 그 답이다.

    Attributes:
        onnx_file: 그래프 파일 경로 (절대).
        cfg_file: 대조에 쓴 cfg 경로 (없으면 None — 그래프만으로도 완전하다).
        inputs: 그래프 입력 순서 그대로.
        outputs: 그래프 출력 순서 그대로.
        precision: cfg 의 ``precision`` (TensorRT knob — 여기선 안 쓰고 보관만).
    """

    onnx_file: Path
    cfg_file:  Path | None
    inputs:    tuple[Tensor_spec, ...]
    outputs:   tuple[Tensor_spec, ...]
    precision: str = ""

    @classmethod
    def Parse(cls, onnx_file: str | Path, cfg_file: str | Path | None = None) -> Model_spec:
        """onnx 그래프(+ 옆의 cfg)를 읽어 스펙을 만든다.

        cfg 는 **읽기만 한다** — 대조에 실패하면 터지지만, 있든 없든 스펙 내용은 그래프에서 나온다.

        Args:
            onnx_file: onnx 파일 경로.
            cfg_file: cfg 경로. None 이면 규약(``{stem}{CFG_SUFFIX}``)으로 찾고, 없으면 cfg 없이 간다.

        Returns:
            그래프 IO 스펙 (+ cfg 가 있으면 precision).

        Raises:
            FileNotFoundError: onnx 파일이 없거나, 명시한 cfg 가 없으면.
            ValueError: cfg 의 profile 이 그래프와 어긋나면 (이름·dtype·shape).
        """
        _onnx = Path(onnx_file)
        if not _onnx.is_file():
            raise FileNotFoundError(f"onnx 파일이 없다: {_onnx}")

        _in, _out = _Read_graph(_onnx)
        _cfg_path = cls._cfg_path(_onnx, cfg_file)
        if _cfg_path is None:
            return cls(onnx_file=_onnx, cfg_file=None, inputs=_in, outputs=_out)

        _cfg = _Read_yaml(_cfg_path)
        _Verify(_in,  _cfg.get("input_profiles"),  "input",  _cfg_path)
        _Verify(_out, _cfg.get("output_profiles"), "output", _cfg_path)
        return cls(onnx_file=_onnx, cfg_file=_cfg_path, inputs=_in, outputs=_out,
                   precision=str(_cfg.get("precision", "")))

    @staticmethod
    def _cfg_path(onnx: Path, cfg_file: str | Path | None) -> Path | None:
        """명시 cfg 는 없으면 raise, 규약 cfg 는 없으면 None (있는 대로 쓴다)."""
        if cfg_file:
            _p = Path(cfg_file)
            if not _p.is_absolute():
                _p = onnx.parent / _p
            if not _p.is_file():
                raise FileNotFoundError(f"지정한 cfg 파일이 없다: {_p}")
            return _p
        _guess = onnx.with_name(onnx.stem + CFG_SUFFIX)
        return _guess if _guess.is_file() else None

    def Describe(self) -> str:
        """사람이 읽는 요약 — 이 모델이 뭘 받고 뭘 내는지. 에러 메시지·확인용."""
        _lines = [f"onnx : {self.onnx_file.name}",
                  f"cfg  : {self.cfg_file.name if self.cfg_file else '(없음)'}"
                  + (f"  precision={self.precision}" if self.precision else "")]
        _lines += ["inputs :"]  + [f"    {_t}" for _t in self.inputs]
        _lines += ["outputs:"] + [f"    {_t}" for _t in self.outputs]
        return "\n".join(_lines)

    def __str__(self) -> str:
        return self.Describe()


# ── 파싱 ──────────────────────────────────────────────────────────────────────

def _Read_graph(onnx_file: Path) -> tuple[tuple[Tensor_spec, ...], tuple[Tensor_spec, ...]]:
    """onnx 그래프의 입출력 선언을 읽는다 — 가중치는 안 읽는다(``load_external_data=False``).

    89MB 파일이라도 헤더 파싱만 하므로 싸다(세션·CUDA 없이 돈다).
    """
    import onnx                                                   # noqa: PLC0415

    _model = onnx.load(str(onnx_file), load_external_data=False)

    def _specs(values: Any) -> tuple[Tensor_spec, ...]:
        _out = []
        for _v in values:
            _t = _v.type.tensor_type
            _name = onnx.TensorProto.DataType.Name(_t.elem_type)
            if _name not in _NP_DTYPE:
                raise ValueError(f"{onnx_file.name}: 텐서 {_v.name!r} 의 dtype {_name} 은 "
                                 f"아직 다루지 않는다 (_NP_DTYPE 에 더하라).")
            #: 동적 축(dim_param)은 -1 — 고정 프로파일 모델이면 안 나온다.
            _shape = tuple(_d.dim_value if _d.HasField("dim_value") else -1
                           for _d in _t.shape.dim)
            _out.append(Tensor_spec(name=_v.name, dtype=_NP_DTYPE[_name], shape=_shape))
        return tuple(_out)

    return _specs(_model.graph.input), _specs(_model.graph.output)


def _Read_yaml(path: Path) -> dict:
    """cfg yaml 을 dict 로. 최상위가 매핑이 아니면 raise."""
    import yaml                                                   # noqa: PLC0415

    _data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(_data, dict):
        raise ValueError(f"cfg 가 매핑이 아니다: {path}")
    return _data


def _Verify(graph: tuple[Tensor_spec, ...], profiles: Any, kind: str, cfg_path: Path) -> None:
    """cfg profile 이 그래프와 같은 말을 하는지 대조한다 — **아무것도 가져오지 않는다.**

    cfg 는 변환 툴의 산출물이라 우리가 쓸 필드를 얹을 수 없다(재-export 가 지운다). 그래서 여기서 하는
    일은 검사뿐이다: 어긋나면 cfg 를 따르지 않고 raise 한다(조용히 한쪽을 택하면 어느 쪽이 옳은지 영영
    모른다). profile 이 없으면 대조를 건너뛴다 — 그래프만으로 스펙은 이미 완전하다.

    Raises:
        ValueError: cfg 에 그래프에 없는 텐서가 있거나, dtype/opt_shape 이 그래프와 어긋나면.
    """
    if not profiles:
        return

    _by_name = {_p.get("name"): _p for _p in profiles if isinstance(_p, dict)}
    _unknown = set(_by_name) - {_t.name for _t in graph}
    if _unknown:
        raise ValueError(
            f"{cfg_path.name}: {kind}_profiles 에 그래프에 없는 텐서 {sorted(_unknown)} — "
            f"그래프의 {kind} 은 {[_t.name for _t in graph]}. cfg 가 다른 onnx 의 것이 아닌지 확인하라.")

    for _t in graph:
        _p = _by_name.get(_t.name)
        if _p is not None:                                        # cfg 가 안 적은 텐서는 그냥 넘어간다
            _Check_agrees(_t, _p, kind, cfg_path)


def _Check_agrees(spec: Tensor_spec, profile: dict, kind: str, cfg_path: Path) -> None:
    """cfg profile 이 그래프와 같은 말을 하는지 — dtype 과 ``opt_shape``."""
    _dtype = str(profile.get("dtype", "")).lower()
    if _dtype and _dtype != spec.dtype:
        raise ValueError(f"{cfg_path.name}: {kind} {spec.name!r} dtype 이 그래프와 다르다 — "
                         f"그래프 {spec.dtype}, cfg {_dtype}")
    _shape = profile.get("opt_shape")
    if _shape is not None and tuple(_shape) != spec.shape:
        raise ValueError(f"{cfg_path.name}: {kind} {spec.name!r} opt_shape 이 그래프와 다르다 — "
                         f"그래프 {list(spec.shape)}, cfg {list(_shape)}")
