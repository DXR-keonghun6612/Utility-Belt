from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from web.dependencies import get_db
from core.assets.manager import AssetService

router = APIRouter(prefix="/assets", tags=["Assets"])

@router.post("/upload")
def upload_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    service = AssetService(db)
    try:
        asset = service.upload_asset(file)
        return {
            "id": asset.id,
            "filename": asset.filename,
            "url": f"/assets/{asset.id}" # 미리보기 URL
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{asset_id}")
def get_file(asset_id: str, db: Session = Depends(get_db)):
    service = AssetService(db)
    asset = service.get_asset(asset_id)
    
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
        
    return FileResponse(asset.file_path, media_type=asset.content_type)
