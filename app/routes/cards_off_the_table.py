# app/routes/cards_off_the_table.py
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from app.db.database import SessionLocal
from pydantic import BaseModel
from app.db.models import Game, Room, CardsXGame, CardState, Player, RoomStatus, Card
from app.schemas.discard_schema import DiscardRequest, DiscardResponse
from app.services.game_service import (
    descartar_cartas,
    robar_cartas_del_mazo,
    actualizar_turno
)
from app.sockets.socket_service import get_websocket_service
from datetime import datetime

router = APIRouter(prefix="/game", tags=["Games"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class Victim(BaseModel):
    user_id: int


@router.post("/game/{room_id}/cards_off_the_table")
async def cards_off_the_table(
    room_id: int,
    request: Victim,
    db: Session = Depends(get_db)
):
    # Busco la sala
    room = db.query(Room).filter(Room.id == room.id).first()
    if not room:
        raise HTTPException(status_code=404, detail="room_not_found")
    
    # Busco la partida
    game = db.query(Game).filter(Game.id == room.id_game).first()
    if not game:
        raise HTTPException(status_code=404, detail="game_not_found")
    
    # Busco las cartas NSF en la mano del jugador
    nsf_cards = (
        db.query(CardsXGame).filter(
            CardsXGame.player_id == Victim,
            CardsXGame.id_game == game.id,
            CardsXGame.is_in == CardState.HAND
            CardsXGame.id_card == 13
        )
    )
    