from pydantic import BaseModel
from app.schemas.room import RoomCreate
from app.schemas.player import PlayerCreate

class GameCreate(BaseModel):
    room: RoomCreate
    player: PlayerCreate

class GameResponse(BaseModel):
    id_partida: int
    nombre_partida: str
    jugadores: int
    estado: str
    host_id: int

    class Config:
        orm_mode = True