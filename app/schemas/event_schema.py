from pydantic import BaseModel
from typing import List

# delay de murderer escape
class delay_escape_start_request(BaseModel):
    card_id : int
    quantity : int

class delay_escape_start_response(BaseModel):
    action_id : int 
    available_cards: List[int]

class delay_escape_order_request(BaseModel):
    action_id : int
    ordered_cards_ids : List[int]

class delay_escape_order_response(BaseModel):
    status: str
    action_id: int
    moved_cards: List[int]

