from sqlalchemy.orm import Session
from .models import LocationModel

class LocationService:
    def __init__(self, db: Session):
        self.db = db

    def create_location(self, latitude: float, longitude: float, address: str = None) -> LocationModel:
        location = LocationModel(
            latitude=latitude,
            longitude=longitude,
            address=address
        )
        self.db.add(location)
        self.db.commit()
        self.db.refresh(location)
        return location

    def get_location(self, location_id: str) -> LocationModel:
        return self.db.query(LocationModel).filter(LocationModel.id == location_id).first()
