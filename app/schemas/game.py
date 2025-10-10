from pydantic import BaseModel
from app.schemas.room import RoomCreateRequest, RoomResponse
from app.schemas.player import PlayerCreateRequest, PlayerResponse
from typing import List

class GameCreateRequest(BaseModel):
    room: RoomCreateRequest
    player: PlayerCreateRequest

class GameResponse(BaseModel):
    room: RoomResponse
    players: List[PlayerResponse]
    model_config = {"from_attributes": True}
