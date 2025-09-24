from pydantic import BaseModel

class SessionCreate(BaseModel):
    room: RoomCreate
    player: PlayerCreate

class GameResponse(BaseModel):
    host_id: bool

    class Config:
        orm_mode = True