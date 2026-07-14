"""port — 외부 세계와 닿는 유일한 지점 (실체화·발견).

데이터 **하나**의 읽기/쓰기와 외부 레이아웃의 **발견**(glob). 아는 것은 **디스크와 포맷뿐** —
``Bucket_Store`` 를 모른다. 의존은 한 방향 — ``schema ← port ← store``. **store 만이 여기를 부른다**
(읽기/쓰기는 store 가 소유하고 위 계층은 요청한다). 이 방향은 [`../test_layering.py`](../test_layering.py)
가 강제한다.

**축이 둘이다 — ``format = (domain, format)``:**

- **domain** ([`domain/`](domain)) — *무엇을 담는 데이터인가*. 유효 포맷 검증 + 정준형 + 정책(Claims·Blank).
- **format** ([`codec/`](codec)) — *어떻게 직렬화하나*. 읽기/쓰기의 실제 범위는 도메인보다 훨씬 작다 —
  png 를 읽는 법은 사진이든 마스크든 라벨맵이든 같다. 그래서 **I/O 는 포맷이 소유**하고 도메인을 넘어
  재사용된다(``raster`` 하나를 image·mask·segmap 이 공유).

그래서 새 처리 구조는 **파일 하나 + 한 줄**이다 — codec 을 떨구고 도메인 ``FORMATS`` 에 이름을 더한다
(SAM polygon 이 그렇게 붙었다). 20개 포맷이 와도 도메인당 파일이 늘지 않는다.

**``Data_Ref`` 를 재노출하지 않는다.** 소비처는 [`core.schema`](../schema.py) 에서 직접 가져간다 — 편의
재노출이 있던 동안 데이터모델만 필요한 쪽까지 cv2·numpy 를 끌고 왔다(cv2-free 가 이론으로만 존재했다).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..constant import ROUTE_TARGETS, TO_META, TO_STORAGE
from ..schema import Data_Ref
from .codec import CODEC_REGISTRY, Codec, Codec_for, File_Codec, Inline_Codec
from .codec.value import Inline, Python_type
from .domain import ATTR, DOMAIN_REGISTRY, Domain, Domain_for, Domains, Infer_domain
from ._structure import Structure


def Types() -> list[str]:
    """등록된 도메인 목록 (GUI 데이터-추가 combobox 등) — ``format[0]`` 에 오는 이름들."""
    return Domains()


def Infer_type(ext: str) -> str | None:
    """파일 확장자로 도메인을 추론한다 (없으면 ``None`` — 호출 측이 ``type`` 을 명시하게).

    같은 확장자를 여러 도메인이 쓰면(png = 사진·마스크·라벨맵) 추론은 조용히 하나를 고르는 일이라,
    애매한 도메인은 빠져 있다(png → image 로만).
    """
    return Infer_domain(ext)


# ── 디스패치 — 도메인이 검증하고, codec 이 I/O 한다 ──────────────────────────────
def _domain(ref: Data_Ref) -> tuple[str, type[Domain]]:
    """이 ref 의 도메인 — **등록된 첫 칸이 아니면 개념이라 ``attr`` 로** 보낸다.

    첫 칸은 도메인 이름이거나 **도메인 개념**(``bbox``)이다. 개념은 파일 I/O 가 없어 도메인을 안 갖고,
    갈리는 곳은 표현(gui viewer)이지 저장이 아니다 — 여기서 전부 인라인(attr)으로 흘려보내므로 **개념을
    더해도 port 를 안 고친다**.
    """
    _key = ref.format[0] if ref.format else ""
    _cls = Domain_for(_key)
    if _cls is None:                                     # 개념(bbox…) 또는 빈 칸 → 인라인 값
        return ATTR, Domain_for(ATTR)                    # type: ignore[return-value]
    return _key, _cls


def _codec(ref: Data_Ref) -> type[Codec]:
    """이 ref 의 codec — 도메인이 **포맷 유효성을 검증한 뒤** ``format[1]`` 로 고른다.

    Raises:
        ValueError: 그 도메인에 유효하지 않은 포맷이거나, 그 포맷을 맡는 codec 이 없을 때 (조용한 기본값 없음).
    """
    _name, _dom = _domain(ref)
    _fmt = ref.format[1] if len(ref.format) > 1 else ""
    _dom.Validate(_fmt, name=_name)                      # 도메인의 일 — 유효성만 본다
    _c = Codec_for(_fmt)                                 # 포맷의 일 — I/O
    if _c is None:
        raise ValueError(f"포맷 '{_fmt}' 를 맡는 codec 이 없다 (도메인 '{_name}')")
    return _c


def Load(root: str, path: tuple[str, ...], name: str, ref: Data_Ref) -> Any:
    """payload 로드 (``path`` = leaf 조상 key 시퀀스) — codec 이 싣고, 도메인이 정준형으로 맞춘다."""
    _value = _codec(ref).Load(root, path, name, ref)
    if _value is None:
        return None
    return _domain(ref)[1].Canonicalize(_value)


def _effective_format(dom: type[Domain], ref: Data_Ref, src: Any) -> str:
    """저장할 때 실제로 쓸 포맷 — 서술자가 비어 있으면(ingest) 소스에서 정한다.

    ingest 는 값을 읽기 *전에* 서술자를 짓느라 둘째 칸이 비어 있다(``Template_for_file``) — 그 자리를 여기서
    채운다: 소스가 파일이고 그 확장자가 이 도메인에 유효하면 그대로(복사이지 변환이 아니다), 아니면 도메인
    기본 포맷. (인라인 도메인은 파일 확장자가 무의미해 자연히 기본으로 떨어지고, codec 이 값에서 정정한다.)
    """
    _fmt = ref.format[1] if len(ref.format) > 1 else ""
    if _fmt:
        return _fmt
    if isinstance(src, (str, Path)):
        _ext = Path(src).suffix.lstrip(".").lower()
        if _ext in dom.FORMATS:
            return _ext
    return dom.Default_format()


def Save(root: str, path: tuple[str, ...], name: str, ref: Data_Ref, src: Any) -> Data_Ref:
    """저장. 갱신된 ``Data_Ref`` 반환 (in-memory 값은 도메인 정준형으로 맞춰 쓴다)."""
    _name, _dom = _domain(ref)
    _ref = Data_Ref(format=(ref.format[0] if ref.format else "",
                            _effective_format(_dom, ref, src)),   # ingest 의 빈 칸을 여기서 채운다
                    info=dict(ref.info))
    _value = src if isinstance(src, (str, Path)) else _dom.Canonicalize(src)
    return _codec(_ref).Save(root, path, name, _ref, _value)


def Move(src_root: str, src_path: tuple[str, ...],
         dst_root: str, dst_path: tuple[str, ...], name: str, ref: Data_Ref) -> None:
    """파일을 ``src`` 경로 → ``dst`` 경로로 옮긴다 (인라인=no-op)."""
    _codec(ref).Move(src_root, src_path, dst_root, dst_path, name, ref)


def Copy(src_root: str, src_path: tuple[str, ...],
         dst_root: str, dst_path: tuple[str, ...], name: str, ref: Data_Ref) -> None:
    """파일을 ``src`` → ``dst`` 로 복사한다 (src 보존; 인라인=no-op)."""
    _codec(ref).Copy(src_root, src_path, dst_root, dst_path, name, ref)


def Delete(root: str, path: tuple[str, ...], name: str, ref: Data_Ref) -> None:
    """이 ref 의 파일을 지운다 (인라인=no-op)."""
    _codec(ref).Delete(root, path, name, ref)


def Path_of(root: str, path: tuple[str, ...], name: str, ref: Data_Ref):
    """이 ref 를 받치는 파일 경로 (인라인이면 None) — store 밖 레이아웃으로 내보낼 때."""
    return _codec(ref).Path_of(root, path, name, ref)


def Can_visualize(ref: Data_Ref) -> bool:
    """이 ref 가 이미지로 시각화 가능한지 (도메인이 답한다 — GUI 트리·오버레이용)."""
    return _domain(ref)[1].Can_visualize()


# ── 쓰기 게이트 — 값을 어떤 서술자로 담을지 ────────────────────────────────────
def _claim_domain(value: Any, *, storage: bool, params: bool) -> str | None:
    """spec 이 type 을 안 줄 때, value+맥락을 담당하는 도메인 (최고 ``Claims``; 없으면 None)."""
    _best, _name = 0, None
    for _n, _cls in DOMAIN_REGISTRY._module_dict.items():
        _p = _cls.Claims(value, storage=storage, params=params)
        if _p > _best:
            _best, _name = _p, _n
    return _name


def Template(spec: dict, value: Any, *, params: bool = False) -> Data_Ref:
    """routing spec(+값·맥락) → ``Data_Ref`` 템플릿 — 값을 어떤 서술자로 담을지 한곳에서 정한다.

    도메인 확정 순서: ``spec.type`` → ``spec.format`` 확장자 추론 → value+맥락 ``Claims``. 포맷은
    ``spec.format`` 이 있으면 그게 이기고, 없으면 도메인 기본. **도메인이 그 포맷을 검증**한다.

    **``to`` 는 요청이지 힌트가 아니다** — 그릇(``meta``=인라인 / ``storage``·``trace``=파일)과 확정된
    포맷의 ``INLINE`` 이 어긋나면 실패한다. 같은 mask 라도 ``to`` 에 따라 rle(인라인)/png(파일)로 갈린다.

    **위치는 spec 이 안 정한다** — 파일 경로는 트리 위치(``path``)와 leaf 이름에서 codec 이 파생한다.

    Raises:
        ValueError: ``to`` 가 ``ROUTE_TARGETS`` 밖 · 도메인을 정할 수 없음 · ``to`` ↔ 포맷 그릇 불일치 ·
            도메인에 유효하지 않은 포맷.
    """
    _to = spec.get("to", TO_META)
    if _to not in ROUTE_TARGETS:
        raise ValueError(f"routing: 알 수 없는 to={_to!r} (가능: {', '.join(ROUTE_TARGETS)})")
    _file = _to != TO_META                               # storage·trace = 파일 / meta = 인라인
    _name = (spec.get("type")
             or Infer_domain(spec.get("format", ""))
             or _claim_domain(value, storage=_file, params=params))
    if _name is None:
        raise ValueError(
            f"routing: value({type(value).__name__})·맥락(to={_to}, params={params})"
            f" 으로 도메인을 정할 수 없음 — spec 에 type 을 명시하세요")

    _dom = Domain_for(_name)
    if _dom is None:                                     # 개념(bbox 등) — 도메인이 없다 → 인라인 값
        if _file:
            raise ValueError(f"routing: to={_to!r}(파일) 인데 '{_name}' 은 개념(인라인)이다 — "
                             f"to: {TO_META} 로 바꾸거나 파일 도메인({', '.join(Domains())})을 쓰세요")
        return Inline(value, _name)
    if _name == ATTR:                                    # 등록 이름 = 개념 없음 (그냥 파이썬 값)
        if _file:
            raise ValueError(f"routing: to={_to!r}(파일) 인데 type={_name!r} 은 인라인이다 — "
                             f"to: {TO_META} 로 바꾸거나 파일 도메인을 쓰세요")
        return Inline(value)

    _fmt = spec.get("format") or _dom.Default_format()
    _dom.Validate(_fmt, name=_name)                      # 도메인이 포맷 유효성을 본다
    _codec_cls = Codec_for(_fmt)
    if _codec_cls is None:
        raise ValueError(f"포맷 '{_fmt}' 를 맡는 codec 이 없다 (도메인 '{_name}')")
    if _codec_cls.INLINE == _file:                       # 그릇 ↔ 포맷 불일치는 실패 (조용히 안 바꾼다)
        raise ValueError(
            f"routing: to={_to!r}({'파일' if _file else '인라인'}) 인데 format={_fmt!r} 은 "
            f"{'인라인' if _file else '파일'} 이다 — "
            + (f"to: {TO_STORAGE} 로 바꾸거나 파일 포맷을 쓰세요" if not _file else
               f"to: {TO_META} 로 바꾸거나 인라인 포맷(rle·polygon)을 쓰세요"))
    return Data_Ref(format=(_name, _fmt), info={})


def Template_for_file(spec: dict | str) -> Data_Ref:
    """ingest 스펙(``{pattern, ext, type}``) → ``Data_Ref`` 템플릿.

    ``Template`` 의 자매 — 담을 그릇을 정하는 일은 같지만, ingest 는 파일이 아직 디스크에만 있어 **볼 값이
    없다**(``Template`` 은 값+맥락으로 고를 수 있다).

    **``type``(도메인)은 필수다 — 확장자로 추론하지 않는다.** png 하나가 image 일 수도 segmap·mask 일 수도
    있어, 추론은 **둘 중 하나를 말없이 고르는 것**이다.

    **저장 포맷은 따로 안 받는다** — 서술자의 둘째 칸은 ``Save`` 가 채운다(파일=소스 확장자 그대로).
    ingest 는 **복사이지 변환이 아니라서** 소스와 다른 확장자를 정할 이유가 없다.

    Raises:
        ValueError: ``type`` 이 없거나 등록되지 않은 도메인일 때.
    """
    if isinstance(spec, str):
        spec = {"pattern": spec}
    _type = spec.get("type")
    if not _type:
        raise ValueError(
            f"glob '{spec['pattern']}': type 을 명시하세요 (가능: {', '.join(Types())}). "
            f"확장자로 추론하지 않습니다 — png 는 image 일 수도 segmap 일 수도 있습니다.")
    if Domain_for(_type) is None:
        raise ValueError(
            f"glob '{spec['pattern']}': 알 수 없는 type '{_type}' (가능: {', '.join(Types())}).")
    return Data_Ref(format=(_type, ""))                 # 포맷은 Save 가 소스에서 채운다


def Route(root: str, path: tuple[str, ...], name: str, spec: dict, value: Any,
          *, params: bool = False) -> Data_Ref:
    """값을 spec 대로 저장한다 — ``Template`` 로 ref 를 짓고 ``Save`` 로 write."""
    return Save(root, path, name, Template(spec, value, params=params), value)


def Blank(type: str, *, size: tuple[int, int] | None = None) -> Any:
    """이 도메인의 빈 payload 를 만든다 — "빈 것"의 표현(shape·dtype)은 도메인이 소유한다.

    Raises:
        ValueError: 등록되지 않은 도메인.
        NotImplementedError: 그 도메인이 빈 객체 생성을 지원하지 않을 때.
    """
    _dom = Domain_for(type)
    if _dom is None:
        raise ValueError(f"알 수 없는 type '{type}' (가능: {', '.join(Types())})")
    return _dom.Blank(size=size)


from .scan import Glob_of, Pattern_of, Scan  # noqa: E402  (등록 순회 뒤 — scan 은 codec·domain 이 아니다)

__all__ = [
    "Domain", "DOMAIN_REGISTRY", "Domains", "Domain_for", "Infer_domain",
    "Codec", "File_Codec", "Inline_Codec", "CODEC_REGISTRY", "Codec_for",
    "Structure",
    "Types", "Infer_type", "Load", "Save", "Move", "Copy", "Delete", "Path_of", "Can_visualize",
    "Template", "Template_for_file", "Route", "Blank", "Inline", "Python_type",
    "Scan", "Glob_of", "Pattern_of",
]
