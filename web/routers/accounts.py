from typing import List
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core.accounting.typing import Account_Type, Account_Side, Account as AccountDTO
from core.accounting.ledger import Ledger
from web.dependencies import get_ledger

router = APIRouter(prefix="/accounts", tags=["Accounts"])

# Pydantic Schemas (요청/응답 모델)
class AccountCreateRequest(BaseModel):
    code: str
    name: str
    category: str # Enum string
    side: str     # Enum string
    description: str | None = None

class AccountResponse(BaseModel):
    code: str
    name: str
    category: str
    side: str
    description: str | None

    class Config:
        from_attributes = True

# Endpoints
@router.post("/", response_model=AccountResponse)
def create_account(
    req: AccountCreateRequest, 
    ledger: Ledger = Depends(get_ledger)
):
    try:
        # Pydantic -> DTO 변환
        new_acc = AccountDTO(
            code=req.code,
            name=req.name,
            category=Account_Type(req.category), # String to Enum
            side=Account_Side(req.side),         # String to Enum
            description=req.description
        )
        saved_acc = ledger.add_account(new_acc)
        return saved_acc.to_dict() # DTO -> Dict
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/", response_model=List[AccountResponse])
def read_accounts(ledger: Ledger = Depends(get_ledger)):
    accounts = ledger.get_all_accounts()
    return [acc.to_dict() for acc in accounts]
