# app/routes/api.py
from fastapi import APIRouter, Query, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List
from ..db.database import SessionLocal
from ..db.models import Room, Player, RoomStatus

router = APIRouter(prefix="/api", tags=["API"])

# Conexión a la DB
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Modelos de respuesta
class GameItem(BaseModel):
    id: int
    name: str
    player_qty: int
    players_joined: int
    host_id: int | None 

    model_config = {"from_attributes": True}

class GameListResponse(BaseModel):
    items: List[GameItem]
    page: int
    limit: int

# Endpoint de prueba
@router.get("/test")
async def test_endpoint():
    return {"message": "Test endpoint is working!"}

# Endpoint: GET /game_list
@router.get("/game_list", response_model=GameListResponse)
def get_game_list(page: int = Query(1, ge=1), limit: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)):
    try:
        rooms = (
            db.query(Room)
            .filter(Room.status == RoomStatus.WAITING)
            .order_by(Room.id.desc())
            .all()
        )

        available = []
        for room in rooms:
            # Cuenta los jugadores en la partida
            players = db.query(Player).filter(Player.id_room == room.id).all()
            players_joined = len(players)

            # Busca al host
            host = next((p for p in players if p.is_host), None)

            # Salas con cupo disponible
            if players_joined < room.player_qty:
                available.append({
                    "id": room.id,
                    "name": room.name,
                    "player_qty": room.player_qty,
                    "players_joined": players_joined,
                    "host_id": host.id if host else None
                })
          
        # Paginación
        start = (page - 1) * limit
        end = start + limit
        paginated = available[start:end]

        return GameListResponse(
            items=[GameItem(**r) for r in paginated],
            page=page,
            limit=limit
        )
    
    except Exception as e:
        print(f"Error in game_list: {e}")  # Para debug
        raise HTTPException(status_code=500, detail="server_error")