from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.database import Base, engine
from core.assets.models import AssetModel
from core.geo.models import LocationModel # Geo Model Import
from web.routers import accounts, transactions, assets, geo

# DB 테이블 자동 생성 (서버 시작 시)
# 프로덕션에서는 Alembic 같은 마이그레이션 도구를 쓰는 게 좋음
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Utility Belt (CACHE)",
    description="Double-entry bookkeeping API with Evidence & Geolocation",
    version="0.1.0"
)

# CORS 설정 (React 프론트엔드 연동용)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # 개발 중이니 모든 출처 허용. 배포 시 특정 도메인으로 제한.
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록
app.include_router(accounts.router)
app.include_router(transactions.router)
app.include_router(assets.router)
app.include_router(geo.router)

@app.get("/")
def root():
    return {"message": "Welcome to Utility Belt API. Visit /docs for Swagger UI."}
