from typing import List, Dict, Any, Optional
from datetime import date
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core.accounting.ledger import Ledger
from web.dependencies import get_ledger, get_current_user_id

router = APIRouter(prefix="/transactions", tags=["Transactions"])

# Pydantic Schemas
class JournalEntryRequest(BaseModel):
    code: str
    amount: float
    description: str | None = None

class TransactionCreateRequest(BaseModel):
    date: date
    description: str
    debits: List[JournalEntryRequest]
    credits: List[JournalEntryRequest]
    evidence_id: str | None = None
    location_id: str | None = None

class TransactionResponse(BaseModel):
    id: str
    owner_id: str
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
    ledger: Ledger = Depends(get_ledger),
    user_id: str = Depends(get_current_user_id)
):
    try:
        debits_data = [d.dict() for d in req.debits]
        credits_data = [c.dict() for c in req.credits]
        
        new_tx = ledger.record_transaction(
            user_id=user_id,
            tx_date=req.date,
            description=req.description,
            debits=debits_data,
            credits=credits_data,
            evidence_id=req.evidence_id,
            location_id=req.location_id
        )
        
        resp_dict = new_tx.to_dict()
        resp_dict['is_balanced'] = new_tx.is_balanced
        return resp_dict

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/", response_model=List[TransactionResponse])
def read_transactions(
    ledger: Ledger = Depends(get_ledger),
    user_id: str = Depends(get_current_user_id)
):
    txs = ledger.get_all_transactions(user_id)
    
    result = []
    for tx in txs:
        d = tx.to_dict()
        d['is_balanced'] = tx.is_balanced
        result.append(d)
        
    return result

@router.get("/{tx_id}", response_model=TransactionResponse)
def read_transaction(
    tx_id: str,
    ledger: Ledger = Depends(get_ledger),
    user_id: str = Depends(get_current_user_id)
):
    try:
        tx = ledger.get_transaction(user_id, tx_id)
        d = tx.to_dict()
        d['is_balanced'] = tx.is_balanced
        return d
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))