"""파생 스테이지 store — thin ``Sample_Set``(``Bucket_Store``, 범주 = split train/val/test).

정본(staged ``Dataset_Meta``)에서 파생된 학습셋의 구조·영속만 소유한다 — 정본→파생 빌드는
[`../../process/sample.py`](../../process/sample.py)가 짓는다. split 은 build 때 frame stem 해시로
배정되는 **데이터셋 정체성**이다(같은 이미지의 객체는 한 split → leakage 방지). class_id 와 split 은
독립이라 class 재배정이 split 을 안 건드린다.

**task 별 store 타입은 없다.** 빌드는 "무엇을 뽑나"(unit·crop 여부)만 정하고, task(classification /
detection)는 **내보낼 때** 비로소 의미를 갖는다 — ImageFolder 든 COCO 든 학습 프레임워크 레이아웃은
export 산출물이지 store 구조가 아니다. 그래서 파생 store 는 이 하나뿐이다.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, Mapping

from ...constant import SPLITS, TEST, TRAIN, VAL
from ..bucket_store import Bucket_Store
from ... import port
from ...schema import Data_Ref

SAMPLE_DIR = "sample"                                # 정본 root 아래 파생 서브트리 ({dataset_root}/sample/{tasker})


@dataclass
class Sample_Set(Bucket_Store):
    """파생 학습셋 store — 범주 = split (train/val/test).

    item = sample. 무엇이 sample 인지는 빌드의 ``unit`` 이 정한다(object → 객체 하나 / frame → 프레임
    하나, 객체를 자식으로 낀 채). class 는 구조가 아니라 sample 의 ``class_id`` attr 이다.
    """

    CATEGORIES:       ClassVar[tuple[str, ...]] = SPLITS
    DEFAULT_CATEGORY: ClassVar[str]             = TRAIN   # placeholder — split 배정은 빌드(frame 해시) 몫

    # ── 내보내기 — 학습 프레임워크 레이아웃으로 (라이프사이클이라 store 소유) ──────────
    def Export(self, dest: str | Path, *, task: str,
               meta=None, id_map: dict[str, int] | None = None) -> Path:
        """이 학습셋을 ``task`` 레이아웃으로 ``dest`` 아래에 실체화한다 (원본 비파괴).

        **split 은 재배정하지 않는다** — 이미 split 범주로 갈려 있다(빌드가 배정). 여기서 정하는 건
        레이아웃뿐이고, 그게 task 다: classification=ImageFolder(class-major) / detection=COCO(kind-major).

        Args:
            dest: 산출물 루트.
            task: ``EXPORTERS`` 의 key (classification/detection).
            meta: 정본 store — detection 은 픽셀이 sample 이 아니라 정본에 있어 필요하다.
            id_map: class→정수. None 이면 class 정렬로 생성.

        Raises:
            ValueError: 그 task 의 exporter 가 없을 때.
        """
        from .export import EXPORTERS
        _cls = EXPORTERS.get(task)
        if _cls is None:
            raise ValueError(f"알 수 없는 sample task: {task!r} (가능: {', '.join(EXPORTERS)})")
        _out = Path(dest)
        _cls(source=self, meta=meta, id_map=id_map).Export(_out)
        return _out

    # ── 배치 — sample 하나를 split 범주에 앉힌다 (payload write 포함) ────────────────
    def Place(self, sample_id: str, ref: Data_Ref, *,
              split: str, crop=None) -> None:
        """sample 하나를 ``split`` 범주에 넣는다 — ``crop`` 이 있으면 payload 로 저장하고 leaf 를 단다.

        경로는 port 가 트리 위치에서 파생한다 — ``{root}/{split}/crop/{sample_id}.png``(kind-major).
        **class 는 경로에 안 들어간다**(attr 이므로) → 재분류가 파일을 안 건드린다.

        split **배정**(어느 split 이냐)은 빌드 정책이라 여기 없다 — 호출 측(빌드)이 정해 넘긴다.
        여기가 소유하는 건 그 배정을 **앉히는 일**(payload write + 범주 등록)이다.

        Args:
            sample_id: sample key (범주 직속 자식 = item).
            ref: sample 컨테이너 (정본 역참조 + class_id attr).
            split: 배치할 split 범주.
            crop: 실체화된 crop 이미지 (없으면 payload 없이 역참조만).
        """
        if crop is not None:
            ref.Push("crop", port.Route(
                self.root, (split, sample_id), "crop", {"to": "storage"}, crop))
        self.Set(sample_id, ref, category=split)

    # ── named accessor — ``Bucket(split)`` 읽기 뷰에 이름을 얹은 sugar ──────────────
    @property
    def train(self) -> Mapping[str, Data_Ref]:
        """train split 항목 — 읽기 전용 뷰."""
        return self.Bucket(TRAIN)

    @property
    def val(self) -> Mapping[str, Data_Ref]:
        """val split 항목 — 읽기 전용 뷰."""
        return self.Bucket(VAL)

    @property
    def test(self) -> Mapping[str, Data_Ref]:
        """test split 항목 — 읽기 전용 뷰."""
        return self.Bucket(TEST)
