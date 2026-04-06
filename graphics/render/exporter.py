from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PySide6.QtGui import QImage

from data.scene.node.camera import Camera_Node
from graphics.render.config import Render_Config


class Result_Exporter:
    """렌더 결과물(이미지, 메타데이터)을 파일 시스템에 저장함.

    출력 디렉토리 구조:
        <output_dir>/
            rgb_000000.png
            rgb_000001.png
            ...
            depth_000000.npy
            depth_000001.npy
            ...
            segmentation_000000.png
            segmentation_000001.png
            ...
            normal_000000.png
            normal_000001.png
            ...
            metadata_000000.json
            metadata_000001.json
            ...
    """

    def __init__(self, output_dir: str | Path):
        self._output_dir = Path(output_dir)
        self._output_dir.mkdir(parents=True, exist_ok=True)

    def Save(
        self,
        frame_id: int,
        results: dict[str, np.ndarray],
        camera_node: Camera_Node,
        config: Render_Config,
    ) -> Path:
        """프레임별 렌더 결과 및 메타데이터를 저장하고 프레임 디렉토리 경로를 반환함.

        Args:
            frame_id: 프레임 고유 번호 (파일명 패딩 기준).
            results: Render_Pipeline.Execute()의 반환값.
            camera_node: 메타데이터 추출에 사용할 카메라 씬 노드.
            config: 렌더 설정 (메타데이터에 포함).

        Returns:
            Path: 저장된 프레임 디렉토리 경로.
        """
        for _name, _data in results.items():
            self._Save_array(self._output_dir / f"{_name}_{frame_id:06d}", _data)

        self._Save_metadata(self._output_dir, frame_id, camera_node, config)

        return self._output_dir

    # ==========================================
    # 내부 저장 로직
    # ==========================================

    def _Save_array(self, base_path: Path, data: np.ndarray) -> None:
        """dtype에 따라 이미지(PNG) 또는 배열(npy) 형식으로 저장함."""
        if data.dtype == np.float32:
            # 연속 메모리 보장 후 npy 저장 (depth 등 float 패스)
            np.save(str(base_path.with_suffix(".npy")), np.ascontiguousarray(data))
        else:
            # uint8 RGB 데이터 → PNG
            _h, _w = data.shape[:2]
            _channels = data.shape[2] if data.ndim == 3 else 1
            _contiguous = np.ascontiguousarray(data)
            _img = QImage(
                _contiguous.tobytes(), _w, _h,
                _w * _channels, QImage.Format.Format_RGB888
            )
            _img.save(str(base_path.with_suffix(".png")))

    def _Save_metadata(
        self, output_dir: Path, frame_id: int,
        camera_node: Camera_Node, config: Render_Config
    ) -> None:
        """카메라 intrinsic/extrinsic 및 렌더 설정을 JSON으로 저장함."""
        _intrinsic = camera_node.intrinsic
        _meta = {
            "camera": {
                "label": camera_node.label,
                "intrinsic": _intrinsic.Serialize() if _intrinsic else {},
                "extrinsic": camera_node.world_matrix.tolist(),
            },
            "render": config.Serialize(),
        }
        (output_dir / f"metadata_{frame_id:06d}.json").write_text(
            json.dumps(_meta, indent=2, ensure_ascii=False), encoding="utf-8"
        )
