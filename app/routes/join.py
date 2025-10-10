from fastapi import APIRouter, Query, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Dict
from datetime import date
from ..db.database import SessionLocal
from ..db.models import Room, Player, RoomStatus
from ..services.game_service import join_game_logic

router = APIRouter()

# Conexión a la DB
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Modelos para join game
class JoinGameRequest(BaseModel):
    name: str
    avatar: str
    birthdate: str  # Formato: "YYYY-MM-DD"

class PlayerResponse(BaseModel):
    id: int
    name: str
    avatar: str
    birthdate: str
    is_host: bool
    model_config = {"from_attributes": True}

class RoomResponse(BaseModel):
    id: int
    name: str
    players_min: int
    players_max: int
    status: str
    host_id: int
    game_id: int
    model_config = {"from_attributes": True}

class JoinGameResponse(BaseModel):
    room: RoomResponse
    players: List[PlayerResponse]

# Endpoint: POST /game/{room_id}/join
@router.post("/game/{room_id}/join", response_model=JoinGameResponse)
async def join_game(room_id: int, request: JoinGameRequest, db: Session = Depends(get_db)):
    print(room_id, "    ---- ", request)

    try:
        result = join_game_logic(db, room_id, request.dict())
        
        if not result["success"]:
            if result["error"] == "room_not_found":
                raise HTTPException(status_code=404, detail="Room not found")
            elif result["error"] == "room_full":
                raise HTTPException(status_code=400, detail="Room is full")
            elif result["error"] == "room_not_waiting":
                raise HTTPException(status_code=400, detail="Room is not accepting players")
            else:
                raise HTTPException(status_code=400, detail=result["error"])
        
        # Format response
        room_data = result["room"]
        players_data = result["players"]

        # Encontrar el host
        host = next((p for p in players_data if p.is_host), None)
        
        return JoinGameResponse(
            room=RoomResponse(
                id=room_data.id,
                name=room_data.name,
                players_min=room_data.players_min,
                players_max=room_data.players_max,
                status=room_data.status.value if hasattr(room_data.status, 'value') else room_data.status,
                host_id=host.id if host else None,
                game_id=room_data.id_game
            ),
            players=[
                PlayerResponse(
                    id=p.id,
                    name=p.name,
                    avatar=p.avatar_src, 
                    birthdate=p.birthdate.strftime("%Y-%m-%d") if isinstance(p.birthdate, date) else p.birthdate,
                    is_host=p.is_host
                ) for p in players_data
            ]
        )
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in join_game: {e}")  # Para debug
        raise HTTPException(status_code=500, detail="server_error")