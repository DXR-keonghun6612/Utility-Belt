import shutil
import uuid
from pathlib import Path
from typing import BinaryIO
from fastapi import UploadFile
from sqlalchemy.orm import Session

from .models import AssetModel

UPLOAD_DIR = Path("data/uploads")

class FileManager:
    """물리적 파일 입출력을 담당"""
    
    @staticmethod
    def save_file(file: UploadFile) -> tuple[str, str, int]:
        """
        업로드된 파일을 저장소에 저장하고 정보를 반환합니다.
        Returns: (stored_filename, file_path_str, size_bytes)
        """
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        
        # 고유 파일명 생성 (UUID + 확장자)
        ext = Path(file.filename).suffix
        if not ext:
            ext = ".bin"
            
        stored_filename = f"{uuid.uuid4()}{ext}"
        file_path = UPLOAD_DIR / stored_filename
        
        # 파일 저장
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        return stored_filename, str(file_path), file_path.stat().st_size

    @staticmethod
    def delete_file(file_path_str: str):
        path = Path(file_path_str)
        if path.exists():
            path.unlink()

class AssetService:
    """DB와 파일 시스템을 조율하는 서비스"""
    
    def __init__(self, db: Session):
        self.db = db

    def upload_asset(self, file: UploadFile) -> AssetModel:
        # 1. 물리적 파일 저장
        stored_name, path_str, size = FileManager.save_file(file)
        
        # 2. DB 메타데이터 저장
        asset = AssetModel(
            filename=file.filename,
            stored_filename=stored_name,
            file_path=path_str,
            content_type=file.content_type,
            size_bytes=size
        )
        self.db.add(asset)
        self.db.commit()
        self.db.refresh(asset)
        
        return asset

    def get_asset(self, asset_id: str) -> AssetModel:
        return self.db.query(AssetModel).filter(AssetModel.id == asset_id).first()

    def delete_asset(self, asset_id: str):
        asset = self.get_asset(asset_id)
        if asset:
            # 1. 물리적 파일 삭제
            FileManager.delete_file(asset.file_path)
            # 2. DB 레코드 삭제
            self.db.delete(asset)
            self.db.commit()
