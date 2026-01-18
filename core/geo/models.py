from sqlalchemy import Column, String, Float, DateTime
import uuid
from datetime import datetime

from core.database import Base

class LocationModel(Base):
    __tablename__ = "locations"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    address = Column(String, nullable=True) # 선택 사항: 주소 텍스트
    created_at = Column(DateTime, default=datetime.now)
