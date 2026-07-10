"""파생(sample) 스테이지 store — staged 정본에서 파생된 학습셋의 데이터 구조·영속.

``Sample_Set``(``Bucket_Store``, 범주 = 단일 작업 버킷 ``WORKING``)만 든다 — 정본→파생 빌드(sampler)는
[`../../sampler`](../../sampler)가 소유한다(meta store↔converter 대칭). ``SAMPLE_DIR``/``WORKING``/``SPLITS``
는 store 규약 상수(split 은 store 범주가 아니라 내보내기 산출물).
"""

from ._base import SAMPLE_DIR, SPLITS, WORKING, Sample_Set

__all__ = ["Sample_Set", "SAMPLE_DIR", "SPLITS", "WORKING"]
