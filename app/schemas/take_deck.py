from pydantic import BaseModel, Field
from typing import List

class TakeDeckRequest(BaseModel):
    """Request para robar cartas del mazo"""
    cantidad: int = Field(default=1, ge=1, le=10, description="Cantidad de cartas a robar (1-10)")

class CardSummary(BaseModel):
    """Resumen de una carta"""
    id: int
    name: str | None = None
    type: str | None = None
    img: str | None = None

class TakeDeckResponse(BaseModel):
    """Response después de robar cartas"""
    drawn: List[CardSummary]
    hand: List[CardSummary]
    deck_remaining: int