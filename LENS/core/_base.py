"""core 기본 구조 — Pipeline(계산 오케스트레이션 binder) + 모델 풀.

``Pipeline`` 은 정본(``Dataset_Meta``)을 중심으로 **계산 단계**(Convert → Run)를 조율하고 결과를
``meta.Save()`` 로 영속한다. flow 시퀀스를 조립·실행하며, 무거운 prediction 모델을 **클래스
dict 풀**(``Pipeline._RESOURCE_POOL``)로 공유한다(프로세스 수명, 인스턴스 간 공유 — GUI 가 실행마다 새
바인더를 만들어도 재사용).

전이·삭제·병합·들이기·내보내기 같은 **데이터 라이프사이클**은 바인더가 아니라 [`store`](store) 의
``Bucket_Store`` **메서드**가 소유한다 — 호출 측(GUI 등)이 ``meta.Move(…)`` 를 직접 부른다.
바인더는 계산 단계만 잇는다. Verify(품질 검수)는 미구현.

진입점·경로 resolve 는 [`__init__.py`](__init__.py).
"""

from __future__ import annotations

import csv
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, ClassVar

from python_toolbox.project.config import Base_Config

from .constant import MODIFIED, TO_STORAGE, UNCLASSIFIED_ID
from .format.id_map import Id_map
from .process import Build_flow, Sample_stage
from .store import SAMPLE_DIR, Dataset_Meta, Sample_Set
from .tasker import Load_taskers, Save_taskers
from .process.stream.model.onnx import Onnx_segmenter
from .process.stream.model.torch import Sam3_runner


# ── 모델 풀 ───────────────────────────────────────────────────────────────────

# prediction 모델 빌더 — type → 빌더 클래스. registry 가 아니라 그냥 작은 dict(단순 데이터).
# type 은 **기능**을 고르고, 그 기능의 어떤 모델을 쓸지는 빌더 파라미터가 정한다(onnx 는 ``onnx_file``).
MODEL_BUILDERS: dict[str, Any] = {
    "sam3": Sam3_runner,
    "onnx_seg": Onnx_segmenter,
}


def _is_model_spec(value: Any) -> bool:
    """값이 ``{type: <빌더에 있는 종류>, …}`` 모델 스펙인지 — 구조만으로 판별."""
    return isinstance(value, dict) and value.get("type") in MODEL_BUILDERS


def _model_key(spec: dict) -> tuple:
    """공유 key — canonical 스펙 ``(type, 정렬 params)``. 같은 스펙이면 한 번만 빌드."""
    return (spec["type"], tuple(sorted((_k, repr(_v)) for _k, _v in spec.items() if _k != "type")))


# ── config ────────────────────────────────────────────────────────────────────

@dataclass
class Pipeline_config(Base_Config):
    dataset_root: str  = ""
    converter:    dict = field(default_factory=dict)
    flows:        list = field(default_factory=list)   # flow 엔트리 시퀀스
    sample:       dict = field(default_factory=dict)   # 파생(Sample) 설정 — task·split ratio 등
    verify:       dict = field(default_factory=dict)


# ── Pipeline (최상위 binder) ───────────────────────────────────────────────────

class Pipeline:
    """정본(meta)을 중심으로 계산 단계(Convert → Run)를 조율하는 binder.

    생성 시 dataset_root 의 meta 를 로드(없으면 빈 meta). flow·모델은 ``Run`` 에서 lazy 조립한다.
    데이터 라이프사이클(전이·병합·내보내기)은 여기 없다 — ``data`` 계층 ``store`` 가 소유한다.
    """

    # 모델 인스턴스 풀 — 클래스 var(프로세스 수명, 인스턴스 공유). 같은 스펙은 세션당 1회만 빌드.
    _RESOURCE_POOL: ClassVar[dict[tuple, Any]] = {}

    def __init__(self, cfg: Pipeline_config, *,
                 progress: Callable[[int, int], None] | None = None) -> None:
        """``progress`` 가 있으면 meta 복원(수만 사이드카 로드)이 ``(읽은 수, 전체)`` 로 진행을 알린다 —
        GUI 가 이걸 백그라운드 워커의 진행바로 돌려 초 단위 로드에 UI 가 얼지 않게 한다."""
        self.root            = Path(cfg.dataset_root)
        self._converter_cfg  = cfg.converter
        self._flow_cfgs      = cfg.flows
        self._sample_cfg     = cfg.sample
        self._verify_cfg     = cfg.verify
        self.meta            = Dataset_Meta.Restore(self.root, progress=progress)   # 정본 (Dataset_Meta)
        self._sample_root    = self.root / SAMPLE_DIR            # 파생 root ({root}/sample/{tasker})

    def Reload(self) -> None:
        """정본을 디스크에서 다시 읽는다 — **저장 안 한 편집을 버린다.**

        편집은 메모리에서 일어나고(`meta.Remove_object`·캔버스 편집 …) 영속은 명시적 저장이 한다.
        그래서 "취소"는 되돌리기 스택이 아니라 **다시 읽기**다 — 디스크가 마지막 저장 시점이므로,
        무엇을 얼마나 했든 한 번에 그 시점으로 돌아간다.
        """
        self.meta = Dataset_Meta.Restore(self.root)

    # ── config 섹션 갱신 (단일 Pipeline 에 섹션별 주입) ─────────────────────────
    def set_converter(self, cfg: dict) -> None:
        """converter 섹션을 갱신한다 (meta 재로드 없이 — ``Convert`` 가 이 값을 읽는다)."""
        self._converter_cfg = cfg

    # ── 모델 풀 ───────────────────────────────────────────────────────────────
    def _model(self, spec: dict) -> Any:
        """모델 스펙 → 객체. 클래스 풀에 같은 스펙이 있으면 공유, 없으면 빌드해 캐싱."""
        _key = _model_key(spec)
        if _key not in self._RESOURCE_POOL:
            _params = {_k: _v for _k, _v in spec.items() if _k != "type"}
            self._RESOURCE_POOL[_key] = MODEL_BUILDERS[spec["type"]](**_params)
        return self._RESOURCE_POOL[_key]

    def _resolve_step(self, step: dict | str) -> dict | str:
        """process step config 의 모델 스펙 필드를 빌린 객체로 치환한다 (나머지는 그대로)."""
        if not isinstance(step, dict):
            return step
        return {_k: (self._model(_v) if _is_model_spec(_v) else _v)
                for _k, _v in step.items()}

    def _resolve_models(self, flow_cfg: dict) -> dict:
        """flow config 의 process/finalize 스펙 안 모델 스펙을 객체로 치환한 새 config."""
        _out = dict(flow_cfg)
        for _key in ("processes", "finalize_processes"):
            if _key in _out:
                _out[_key] = [self._resolve_step(_s) for _s in _out[_key]]
        return _out

    # ── 단계 ──────────────────────────────────────────────────────────────────
    def Convert(self, progress: Callable[[str, int, int], None] | None = None) -> int:
        """raw 파일을 탐색해 modified 버킷에 컨테이너 ``Data_Ref`` 를 등록하고 저장한다.

        Convert 는 **stage 가 아니다** — 체인이 비어 엔진을 안 쓴다. 들이는 일은 라이프사이클이라
        **store 가 소유한다**(``meta.Import``) — 바인더는 config 를 넘길 뿐이다.

        Returns:
            modified 버킷의 총 frame 수. 0이면 sources/globs 가 어떤 파일도 매칭하지 못한 것.
        """
        _cfg = self._converter_cfg
        self.meta.Import(sources=_cfg.get("sources", []),
                         globs=_cfg.get("globs", {}),
                         params=_cfg.get("params", {}),
                         progress=progress)
        # class→id 매핑(id_map)은 파생(sample) 소유 — 정본은 class 이름만 든다.
        self.meta.Save()
        return len(self.meta.Bucket(MODIFIED))

    def Run(self, progress: Callable[[str, int, int], None] | None = None,
            flows: list | None = None) -> None:
        """flow 시퀀스를 meta 위에서 실행하고 저장한다 (flow 간 데이터는 meta 경유).

        Args:
            progress: flow별 진행 콜백 ``(label, i, total)``.
            flows: 실행할 flow config (None 이면 생성 시 ``self._flow_cfgs``).
        """
        _cfgs = self._flow_cfgs if flows is None else flows
        _flows = [Build_flow(self._resolve_models(_cfg)) for _cfg in _cfgs]
        for _flow in _flows:
            _flow(self.meta, progress=progress)
        self.meta.Save()

    # 객체 재정렬(mask 무게중심 순)은 binder 가 아니라 ``order_objects`` **process**(flow)의 몫이다 —
    # binder 는 오케스트레이터라 segment·mask 픽셀을 직접 로드하지 않는다. obj_id 도 라벨맵 픽셀값이
    # 아니라 이제 **그냥 트리 key** 라(라벨맵 제거) 연속일 필요가 없어 "구멍 압축"도 불필요해졌다.

    # ── 파생(Sample) — 이름 붙은 tasker ({root}/sample/{name} + taskers.yaml) ────
    def Taskers(self) -> dict[str, dict]:
        """등록된 tasker 목록 (``{name: sample config}``) — ``{root}/sample/taskers.yaml``."""
        return Load_taskers(self._sample_root)

    def List_taskers(self) -> list[str]:
        """GUI 목록용 tasker 이름 — 등록 레시피(taskers.yaml) ∪ 실제 빌드 폴더(``{root}/sample/*``).

        레시피와 산출물 폴더가 어긋나도(한쪽만 존재) 둘 다 보이게 합쳐 돌려준다 — 레시피 없이
        폴더만 남은 orphan 도 목록에 떠 ``Delete_tasker`` 로 폴더째 지울 수 있다.
        """
        _names = set(self.Taskers())
        if self._sample_root.exists():
            _names |= {_p.name for _p in self._sample_root.iterdir()
                       if _p.is_dir() and not _p.name.startswith(".")}
        return sorted(_names)

    def Load_sample(self, name: str) -> Sample_Set:
        """이름 붙은 tasker 의 학습셋 store 를 복원한다 (``{root}/sample/{name}``).

        파생 store 는 타입이 하나뿐이다 — task(classification/detection)는 빌드가 아니라 **내보내기**의
        축이라 store 모양을 가르지 않는다.
        """
        return Sample_Set.Restore(self._sample_root / name)

    def Tasker_root(self, name: str) -> Path:
        """빌드된 tasker 의 store 루트 ``{root}/sample/{name}`` (payload 는 ``{split}/crop/*.png``)."""
        return self._sample_root / name

    def Sample(self, name: str, cfg: dict | None = None) -> int:
        """staged 정본을 소비해 이름 붙은 tasker 를 (재)빌드·영속하고 ``taskers.yaml`` 에 등록한다.

        ``Sample_stage`` 를 meta 위에서 구동한다 — Run 과 **같은 엔진**이고 양 끝만 다르다(순회=staged
        정본, 배치=새 ``Sample_Set``). 매 호출이 그 tasker 를 새로 지어 ``{root}/sample/{name}`` 에
        흩고(A+ 순수 재생성), 레시피(``cfg``)를 ``taskers.yaml`` 에 등록한다.

        **split 은 빌드가 배정한다** — split 이 곧 store 범주라 배치 시점에 정해져야 한다. 레시피의
        ``ratios``/``salt`` 가 그래서 여기로 온다(옛 모델은 내보내기가 갈랐다).

        Args:
            name: tasker 이름 (폴더·레지스트리 key).
            cfg:  sample 설정(``unit``/``ratios``/``salt``/``processes``, 내보내기용 ``task``). None 이면
                  등록된 레시피(없으면 생성 시 ``sample`` 섹션).

        Returns:
            파생된 sample 수 합계 (전 split).
        """
        _cfg = cfg if cfg is not None else self.Taskers().get(name, self._sample_cfg)
        _sset = Sample_Set(root=str(self._sample_root / name))
        _stage = Sample_stage(
            unit=_cfg.get("unit", "object"),
            ratios=_cfg.get("ratios") or {},       # 빈 dict → 균등 배분 (Sample_stage._norm_ratios)
            salt=_cfg.get("salt", ""),
            target=_sset,
            processes=_cfg.get("processes", []),   # crop 실체화 체인
        )
        _stage(self.meta)
        _sset.Save()
        _taskers = self.Taskers()                  # 레시피 등록 (name ↔ 폴더 매칭)
        _taskers[name] = _cfg
        Save_taskers(self._sample_root, _taskers)
        return sum(len(_sset.Bucket(_s)) for _s in _sset.CATEGORIES)

    def Export_tasker(self, name: str, dest: str | Path, *, format: str | None = None) -> Path:
        """빌드된 tasker 를 학습 프레임워크 레이아웃으로 외부 경로에 실체화한다.

        **내보내기는 binder 가 든다** (``core.export.Run_export`` — read+compute+external-write 라 store
        라이프사이클이 아니다). 바인더가 여기서 하는 일은 **레시피에서 task 를 읽어 넘기는 것** + 정본·파생
        store 와 id_map 을 조율하는 것이다: 어떤 tasker 인지 아는 건 레시피이고, 그 레시피는 바인더가 든다.

        Args:
            name: 내보낼 tasker 이름.
            dest: 대상 상위 디렉터리 — 이 아래 ``{name}`` 폴더로 실체화된다.

        Returns:
            산출물 경로 (``dest/{name}``).

        Raises:
            FileNotFoundError: tasker 폴더가 없으면 (아직 빌드 안 됨).
            ValueError: 레시피의 task 에 맞는 exporter 가 없으면 (``Run_export`` 가 판정).
        """
        from .export import Run_export
        if not (self._sample_root / name).exists():
            raise FileNotFoundError(f"빌드된 tasker 가 없습니다: {name!r} (먼저 Sample 실행)")
        _cfg = self.Taskers().get(name, {})
        _task = _cfg.get("task")
        if not _task:                          # 조용한 classification fallback 걷어냄 — 레시피가 task 를 든다
            raise ValueError(f"tasker {name!r} 레시피에 task 가 없다 — 프로필에서 지정하라")
        return Run_export(
            self.Load_sample(name), Path(dest) / name,
            task=_task, format=format,         # format None → task 기본 레이아웃
            meta=self.meta, id_map=self.Class_table() or None)

    def Split_export(self, dest: str | Path, ratios: dict[str, float], *,
                     salt: str = "", stratified: bool = False, min_count: int = 0,
                     task: str = "segmentation", format: str | None = "coco",
                     progress: Callable[[str, int, int], None] | None = None) -> Path:
        """검수 끝난(`staged`) 프레임을 비율대로 갈라 ``dest`` 아래 폴더별로 내보낸다.

        배정 규칙과 조율은 [`split.py`](split.py) 가 소유한다 — 바인더가 여기서 하는 일은
        :meth:`Export_tasker` 와 같다: **정본과 class 표를 붙여 넘기는 것**.

        Args:
            dest:       산출물 루트 (``{dest}/{몫}/…``).
            ratios:     ``{몫 이름: 비율}`` — 이름이 곧 폴더 이름이다.
            salt:       해시 salt (같은 데이터를 다르게 나누되 재현 가능하게).
            stratified: class별 공평 배분.
            min_count:  이만큼 안 나온 class 의 주석을 안 적는다 (0 = 끄기). id_map 은 그대로.
            task:       ``detection`` / ``segmentation``.
            format:     직렬화 레이아웃 (기본 ``coco``).
            progress:   진행 콜백 ``(label, i, total)``.
        """
        from .split import Run_split
        return Run_split(self.meta, dest, ratios, salt=salt, stratified=stratified,
                         min_count=min_count, task=task, format=format,
                         id_map=self.Class_table() or None, progress=progress)

    def Class_map(self) -> Id_map:
        """정본 ``meta.params`` 의 id_map 을 **표**(:class:`~core.format.id_map.Id_map`)로 (없으면 빈 표).

        파일에 앉은 모양(호출번호 키 dict)과 다루는 모양(표)은 다르다 — 형식과 그 위의 편집은
        [`format.id_map`](format/id_map.py) 이 소유하고, 여기는 **어디서 읽어 오나**만 안다. 아래 조회
        셋(:meth:`Class_table`·:meth:`Class_choices`·:meth:`Class_names`)도 전부 이 표에서 나온다.

        params leaf 는 인라인(attr)일 수도 파일(doc yaml/json)일 수도 있는데, ``meta.Param`` 이 그걸
        통합해 푼다 — 바인더는 포맷을 모른다.
        """
        _val = self.meta.Param("id_map") if self.meta is not None else None
        return Id_map.Restore(_val if isinstance(_val, dict) else {})

    def Apply_class_map(self, table: Id_map, remap: dict[int, int] | None = None,
                        progress: Callable[[str, int, int], None] | None = None) -> int:
        """편집한 class 표를 정본에 앉힌다 — **라벨 재배정이 먼저, 표 교체가 나중**. 바뀐 객체 수 반환.

        표만 고치면 사라진 번호를 든 라벨이 표에 없는 class 를 가리키게 되므로 둘은 한 걸음이다. 그
        **순서가 규약이다**: 재배정이 중간에 끊겨도 최악이 "표는 옛것, 라벨 일부는 새 번호"라 두 값 모두
        표 안에 있다. 뒤집으면 표에서 사라진 번호를 든 라벨이 남는다.

        바인더가 드는 이유도 그거다 — 표(params)와 라벨(item)이 store 의 서로 다른 자리에 살아서, 둘을
        같은 순서로 묶는 건 조율이지 라이프사이클이 아니다.

        Args:
            table:    새 표 (호출 측이 ``Id_map`` 편집으로 만든 것).
            remap:    그 편집이 낸 ``{옛 class_id: 새 class_id}``. 비면 라벨은 안 건드린다(추가만 한 경우).
            progress: stem 순회 진행 콜백 ``(label, i, total)``.
        """
        _moved = self.meta.Remap_classes(remap, progress=progress) if remap else {}
        _ref = self.meta.Params().get("id_map")
        _fmt = _ref.format if _ref is not None and _ref.format else ("docs", "yaml")
        self.meta.Put_param(
            "id_map",
            {"to": TO_STORAGE, "type": _fmt[0],
             "format": _fmt[1] if len(_fmt) > 1 else "yaml"},
            table.Document())
        self._log_class_edit(remap or {}, _moved)
        return sum(_moved.values())

    def _log_class_edit(self, remap: dict[int, int], moved: dict[int, int]) -> None:
        """번호 이동을 ``{root}/params/id_map_history.csv`` 에 덧붙인다 — ``from,to,ct`` 세 칸.

        표 편집은 압축 때문에 하나를 지워도 **뒤의 번호가 전부 밀리므로**, 나중에 "이 라벨이 왜 이 번호가
        됐나"를 되짚을 근거가 어딘가 남아야 한다. 정본에는 마지막 상태만 남고 과정이 안 남는다.

        - ``from`` 옮겨간 번호 · ``to`` 도착한 번호(삭제는 0=미분류) · ``ct`` 실제로 바뀐 객체 수.
        - 헤더는 **파일을 처음 만들 때 한 번만** 쓰고 이후는 행만 덧붙인다 (그래야 CSV 로 그냥 읽힌다).

        **임시 기록이다** — 제대로 된 이력 기능이 생기면 이 자리가 통째로 그리로 옮겨간다.
        """
        _path = self.root / self.meta.PARAMS / "id_map_history.csv"
        _path.parent.mkdir(parents=True, exist_ok=True)
        _new = not _path.exists()
        with _path.open("a", encoding="utf-8", newline="") as _f:
            _w = csv.writer(_f)
            if _new:
                _w.writerow(["from", "to", "ct"])
            _w.writerows([_o, _remap_to, moved.get(_o, 0)]
                         for _o, _remap_to in sorted(remap.items()))

    def Class_table(self) -> dict[str, dict]:
        """내보내기용 class 표 ``{class 이름: {class_id, …}}``. **0번(미분류 예약)은 뺀다**.

        호출번호 키를 class 이름 키로 뒤집은 것 — 내보내기가 다루는 축이 class 이름이라서다(호출번호는
        목록의 자리일 뿐 정체가 아니다). ``class_id`` 0 은 학습 측 ignore_index 자리이고 내보내기가
        ``no_label`` 로 직접 채우므로(``Exporter._id_map_document``) 여기서 빠져야 한다.

        정본이 든 **부속 칸(``category_id`` 등)을 그대로 나른다** — 무엇이 붙어 있는지는 표가 아니라
        소비 측이 아는 것이고(``Id_entry.extra``), 여기서 걸러내면 내보낸 id_map 에서 조용히 깎인다.
        """
        return {_name: _e for _name, _e in self._entries().items()
                if _e["class_id"] != UNCLASSIFIED_ID}

    def Class_choices(self) -> dict[str, str]:
        """편집 후보 ``{표시 이름: class_id}`` — **미분류(``no_label``, 0)도 포함**한다.

        저장되는 건 번호이고 이름은 표시일 뿐이라(:data:`core.constant.UNCLASSIFIED_ID` 참고) GUI 는
        이 사전으로 "이름을 보여주고 번호를 쓴다". 미분류는 라벨을 **되돌리는** 선택지라 후보에 있어야
        한다 — 빼면 한 번 붙인 class 를 지울 방법이 빈 값밖에 없다.

        **값이 문자열이다** — 저장 표현이 그렇다(``Data_Ref.Set_attr`` 이 문자열로 굳힌다). 여기서
        int 를 주면 고른 값이 저장분과 다른 타입으로 들어가 다음 조회가 빗나간다.
        """
        return {_name: str(_e["class_id"]) for _name, _e in self._entries().items()}

    def Class_names(self) -> dict[str, str]:
        """표시용 역인덱스 ``{class_id: 이름}`` — 저장된 번호를 사람이 읽는 이름으로 되돌린다.

        **키가 문자열이다** — 저장 표현이 그렇기 때문이다. ``class_id`` 는 객체의 인라인 attr 이고
        ``Data_Ref.Set_attr`` 이 값을 문자열로 굳히므로, 정본에서 읽으면 늘 ``"197"`` 이다. 여기서
        int 키를 내면 소비처가 ``names.get("197")`` 로 물어 **전부 빗나가고**(캔버스 상자 라벨이
        번호로 남는다) 조회가 실패한 것도 안 드러난다.
        """
        return {str(_e["class_id"]): _name for _name, _e in self._entries().items()}

    def _entries(self) -> dict[str, dict]:
        """class 표 → ``{class 이름: {class_id, …부속 칸}}`` (0번 포함, 번호순).

        위 셋의 공통 앞단이다 — 축을 **이름**으로 뒤집는다(내보내기·GUI 가 다루는 축이 이름이라서).
        읽을 수 없는 항목을 버리는 건 표(``Id_map.Restore``)가 하고, 여기는 축만 바꾼다. 부속 칸은
        **열어 두고 나른다** — 이 계층은 ``category_id`` 가 있는지도 모른다.
        """
        return {_e.id_name: {"class_id": _e.id_num, **_e.extra}
                for _e in self.Class_map().Sorted()}

    def Delete_tasker(self, name: str) -> None:
        """tasker 를 제거한다 — 폴더(``{root}/sample/{name}``)와 ``taskers.yaml`` 항목 (없으면 no-op)."""
        _dir = self._sample_root / name
        if _dir.exists():
            shutil.rmtree(_dir)
        _taskers = self.Taskers()
        if _taskers.pop(name, None) is not None:
            Save_taskers(self._sample_root, _taskers)

    def Verify(self) -> None:
        """생성 결과의 품질 검수 — Sampling 이후로 미룸(또는 Run 결과에서 대상 선택). 미구현."""
        raise NotImplementedError
