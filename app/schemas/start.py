from pydantic import BaseModel

class StartRequest(BaseModel):
    user_id: int

    model_config = {"from_attributes": True}