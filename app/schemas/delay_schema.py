from pydantic import BaseModel
from typing import List

# delay de murderer escape
class delay_escape_request(BaseModel):
    card_id : int
    quantity : int

class delay_escape_response(BaseModel):
    status: str
    action_id: int
    moved_cards: List[int]

