from typing import List, Dict, Any, Optional
from datetime import date
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core.accounting.ledger import Ledger
from web.dependencies import get_ledger

router = APIRouter(prefix="/transactions", tags=["Transactions"])

# Pydantic Schemas
class JournalEntryRequest(BaseModel):
    code: str
    amount: float # JS에서는 Decimal이 없으므로 float/str로 받음
    description: str | None = None

class TransactionCreateRequest(BaseModel):
    date: date
    description: str
    debits: List[JournalEntryRequest]
    credits: List[JournalEntryRequest]
    evidence_id: str | None = None
    location_id: str | None = None

class TransactionUpdateRequest(BaseModel):
    description: Optional[str] = None
    evidence_id: Optional[str] = None
    location_id: Optional[str] = None

class TransactionResponse(BaseModel):
    id: str
    date: date
    description: str
    debits: List[Dict[str, Any]]
    credits: List[Dict[str, Any]]
    evidence_id: str | None
    location_id: str | None
    is_balanced: bool

    class Config:
        from_attributes = True

# Endpoints
@router.post("/", response_model=TransactionResponse)
def create_transaction(
    req: TransactionCreateRequest,
    ledger: Ledger = Depends(get_ledger)
):
    try:
        # Pydantic Model -> Dict List 변환
        debits_data = [d.dict() for d in req.debits]
        credits_data = [c.dict() for c in req.credits]
        
        # Ledger 호출
        new_tx = ledger.record_transaction(
            tx_date=req.date,
            description=req.description,
            debits=debits_data,
            credits=credits_data,
            evidence_id=req.evidence_id,
            location_id=req.location_id
        )
        
        # DTO -> Dict 변환하여 응답
        resp_dict = new_tx.to_dict()
        resp_dict['is_balanced'] = new_tx.is_balanced
        return resp_dict

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.patch("/{transaction_id}", response_model=TransactionResponse)
def update_transaction(
    transaction_id: str,
    req: TransactionUpdateRequest,
    ledger: Ledger = Depends(get_ledger)
):
    try:
        updated_tx = ledger.update_transaction_metadata(
            transaction_id=transaction_id,
            description=req.description,
            evidence_id=req.evidence_id,
            location_id=req.location_id
        )
        
        resp_dict = updated_tx.to_dict()
        resp_dict['is_balanced'] = updated_tx.is_balanced
        return resp_dict
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.get("/", response_model=List[TransactionResponse])
def read_transactions(ledger: Ledger = Depends(get_ledger)):
    txs = ledger.get_all_transactions()
    
    # DTO list -> Response list
    result = []
    for tx in txs:
        d = tx.to_dict()
        d['is_balanced'] = tx.is_balanced
        result.append(d)
        
    return result
