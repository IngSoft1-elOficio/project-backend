# app/routes/api.py
from fastapi import APIRouter, Query, Depends, HTTPException, Path
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List
from ..db.database import SessionLocal
from ..db.models import Room, Player, RoomStatus, Game, CardsXGame, CardState
from app.sockets.socket_service import get_websocket_service

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
    

# Endpoint: POST /game/{id}/skip
@router.post("/game/{game_id}/skip")
async def skip_turn(
    game_id: int = Path(..., descrition="ID de la partida"),
    user_id: int = 1, # token/auth, pero por ahora es 1
    db: Session = Depends(get_db)
):
    # Busca la patrida
    game = db.query(Game).filter(Game.id == game_id).first()
    if not game:
        raise HTTPException(status_code=404, detail="game_not_found")

    # Validar turno
    if game.player_turn_id != user_id:
        raise HTTPException(status_code=403, detail="not_your_turn")
    
    # Buscar cartas en la mano del jugador
    hand_cards = (
        db.query(CardsXGame).filter(
            CardsXGame.id_game == game_id,
            CardsXGame.player_id == user_id,
            CardsXGame.is_in == CardState.HAND
        ).order_by(CardsXGame.position.asc()).all()
    )

    if not hand_cards:
      raise HTTPException(status_code=400, detail="empty_hand")

    # Descartar primera carta
    discarded = hand_cards[0]
    discarded.is_in = CardState.DISCARD
    discarded.player_id = None
    db.add(discarded)

    # Robar del mazo la carta con menor posicion en el deck