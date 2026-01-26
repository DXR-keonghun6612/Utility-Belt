from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.database import Base, engine
from core.assets.models import AssetModel
from core.geo.models import LocationModel
from core.finance.models import InstallmentPlanModel, StockLotModel # Finance Models

from web.routers import accounts, transactions, assets, geo, finance

# DB 테이블 자동 생성 (서버 시작 시)
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Utility Belt (CACHE)",
    description="Multi-tenant Double-entry bookkeeping API with Advanced Finance Support",
    version="0.2.0"
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록
app.include_router(accounts.router)
app.include_router(transactions.router)
app.include_router(assets.router)
app.include_router(geo.router)
app.include_router(finance.router) # Finance 라우터 추가

@app.get("/")
def root():
    return {"message": "Welcome to Utility Belt API. Visit /docs for Swagger UI."}