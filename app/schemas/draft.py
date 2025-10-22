from pydantic import BaseModel

class DraftRequest(BaseModel):
    card_id: int
    user_id: int

    model_config = {"from_attributes": True}