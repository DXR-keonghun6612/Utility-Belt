from sqlalchemy import Column, String, Integer, DateTime
import uuid
from datetime import datetime

from core.database import Base

class AssetModel(Base):
    __tablename__ = "assets"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    filename = Column(String, nullable=False)      # 원본 파일명 (예: receipt.jpg)
    stored_filename = Column(String, nullable=False) # 저장된 파일명 (예: uuid.jpg)
    file_path = Column(String, nullable=False)     # 저장 경로 (상대 경로)
    content_type = Column(String, nullable=False)  # MIME 타입 (image/jpeg)
    size_bytes = Column(Integer, nullable=False)   # 파일 크기
    created_at = Column(DateTime, default=datetime.now) # 생성 일시
