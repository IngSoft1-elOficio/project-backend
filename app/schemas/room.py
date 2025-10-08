from pydantic import BaseModel, Field


class RoomCreateRequest(BaseModel):
    nombre_partida: str = Field(max_length=200)
    jugadoresMin: int = Field(ge=2)
    jugadoresMax: int = Field(le=6)

class RoomResponse(BaseModel):
    id: int
    name: str
    players_min: int
    players_max: int
    status: str
    host_id: int
    game_id: int 
    model_config = {"from_attributes": True}
