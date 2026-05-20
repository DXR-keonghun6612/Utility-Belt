"""Hashing & cache invalidation.

METHODOLOGY §3: 4종 해시(source / dependency / context / upstream)를 통한
단계별 자동 무효화.

알고리즘: blake2b(digest_size=16). 변경 감지 용도이므로 빠르고 가벼운 선택
(보안 목적이 아니므로 SHA-256은 과함).
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable


DIGEST_SIZE: int = 16


def Hash_bytes(data: bytes) -> str:
    """바이트 시퀀스의 blake2b 해시(hex 문자열)를 반환합니다."""
    return hashlib.blake2b(data, digest_size=DIGEST_SIZE).hexdigest()


def Hash_text(text: str, encoding: str = "utf-8") -> str:
    """문자열의 blake2b 해시(hex)를 반환합니다."""
    return Hash_bytes(text.encode(encoding))


def Hash_file(path: Path | str) -> str:
    """파일 내용의 blake2b 해시를 반환합니다. 파일이 없으면 빈 문자열."""
    _p = Path(path)
    if not _p.is_file():
        return ""
    return Hash_bytes(_p.read_bytes())


def Hash_files(paths: Iterable[Path | str]) -> dict[str, str]:
    """파일 목록을 ``{절대경로: 해시}`` dict로 반환합니다."""
    return {str(Path(p)): Hash_file(p) for p in paths}


def Hash_context(payload: Any) -> str:
    """컨텍스트(컴파일 플래그·언어 버전 등)의 정규화 직렬화 후 해시.

    Notes:
        ``json.dumps(sort_keys=True)``로 순서 정규화 — dict 순서 차이로
        해시가 달라지는 것을 방지합니다.
    """
    _serialized = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return Hash_text(_serialized)


def Is_cache_valid(
    cached_meta: dict,
    *,
    source_hash: str | None = None,
    dependency_hashes: dict[str, str] | None = None,
    context_hash: str | None = None,
    upstream_hash: str | None = None,
) -> bool:
    """캐시된 단계 결과의 무효화 판정.

    저장된 ``meta``의 각 해시 필드와 현재 값을 비교하여, 하나라도 다르면
    캐시 무효(``False``)로 판정합니다. ``None``으로 전달된 항목은 비교를
    건너뜁니다.

    Args:
        cached_meta: 저장된 yaml의 ``meta`` 영역 (dict).
        source_hash: 현재 소스의 해시 (생략 시 비교 안 함).
        dependency_hashes: 현재 의존 파일 해시 dict (생략 시 비교 안 함).
        context_hash: 현재 컨텍스트 해시 (생략 시 비교 안 함).
        upstream_hash: 현재 직전 단계 출력의 해시 (생략 시 비교 안 함).

    Returns:
        ``True``면 캐시 그대로 사용 가능, ``False``면 재실행 필요.
    """
    if source_hash is not None and cached_meta.get("source_hash") != source_hash:
        return False
    if context_hash is not None and cached_meta.get("context_hash") != context_hash:
        return False
    if dependency_hashes is not None:
        if cached_meta.get("dependency_hashes", {}) != dependency_hashes:
            return False
    if upstream_hash is not None and cached_meta.get("upstream_hash") != upstream_hash:
        return False
    return True
