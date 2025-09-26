from pydantic import BaseModel

class StartRequest(BaseModel):
    user_id: int

    class Config:
        orm_mode = True