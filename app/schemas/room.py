from pydantic import BaseModel, Field, constr

class RoomCreate(BaseModel):
    nombre_partida: constr(max_length=200)
    jugadores: int = Field(..., ge=2, le=6)
