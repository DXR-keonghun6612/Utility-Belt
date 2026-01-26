from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.database import Base, engine
from core.assets.models import AssetModel
from core.geo.models import LocationModel
from core.finance.models import InstallmentPlanModel, StockLotModel, GroupDueModel
from core.automation.models import RecurringTransactionModel

from web.routers import accounts, transactions, assets, geo, finance, automation

# DB 테이블 자동 생성 (서버 시작 시)
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Utility Belt (CACHE)",
    description="Multi-tenant Double-entry bookkeeping API with Advanced Finance & Automation",
    version="0.3.0"
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
app.include_router(finance.router)
app.include_router(automation.router) # Automation 라우터 추가

@app.get("/")
def root():
    return {"message": "Welcome to Utility Belt API. Visit /docs for Swagger UI."}
