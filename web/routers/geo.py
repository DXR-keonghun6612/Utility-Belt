from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from web.dependencies import get_db
from core.geo.service import LocationService

router = APIRouter(prefix="/geo", tags=["Geo"])

class LocationCreateRequest(BaseModel):
    latitude: float
    longitude: float
    address: str | None = None

class LocationResponse(BaseModel):
    id: str
    latitude: float
    longitude: float
    address: str | None

@router.post("/", response_model=LocationResponse)
def create_location(
    req: LocationCreateRequest,
    db: Session = Depends(get_db)
):
    service = LocationService(db)
    try:
        loc = service.create_location(req.latitude, req.longitude, req.address)
        return {
            "id": loc.id,
            "latitude": loc.latitude,
            "longitude": loc.longitude,
            "address": loc.address
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
