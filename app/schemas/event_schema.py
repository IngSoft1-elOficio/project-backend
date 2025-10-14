from pydantic import BaseModel

# delay de murderer escape
class delay_escape_start_request(BaseModel):
    "action_id" : int
    "quantity" : int

class delay_escape_start_response(BaseModel):
    "action_id" : int 
    "avaliable_cards" : list[int]

class delay_escape_order_request(BaseModel):
    "action_id" : int
    "orderer_cards_ids" : list[int]


class delay_escape_order_response(BaseModel):
    "sucess" : bool
