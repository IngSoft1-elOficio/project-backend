from pydantic import BaseModel
from typing import List, Optional

class CardWithOrder(BaseModel):
    order: int
    card_id: int

class DiscardRequest(BaseModel):
    card_ids: List[CardWithOrder]

class CardSummary(BaseModel):
    id: int
    name: str
    type: str
    img: Optional[str] = None  

class ActionResult(BaseModel):
    discarded: List[CardSummary]
    drawn: List[CardSummary]

class HandView(BaseModel):
    player_id: int
    cards: List[CardSummary]

class DeckView(BaseModel):
    remaining: int

class DiscardView(BaseModel):
    top: CardSummary | None
    count: int

class DiscardResponse(BaseModel):
    action: ActionResult
    hand: HandView
    deck: DeckView
    discard: DiscardView
