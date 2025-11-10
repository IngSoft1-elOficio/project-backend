
from pydantic import BaseModel

class LookAshesPlayRequest(BaseModel):
    card_id: int  # Event card ID from player's hand

class LookAshesSelectRequest(BaseModel):
    action_id: int  # ActionsPerTurn.id
    selected_card_id: int  # CardsXGame.id from the 5 shown cards

