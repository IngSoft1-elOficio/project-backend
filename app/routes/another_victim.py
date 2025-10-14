# app/routes/another_victim.py
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from app.db.database import SessionLocal
from pydantic import BaseModel
from app.db.models import Game, Room, CardsXGame, CardState, Player, ActionsPerTurn
from app.services.game_service import robar_cartas_del_mazo, actualizar_turno
from app.sockets.socket_service import get_websocket_service
from datetime import datetime

router = APIRouter(prefix="/game", tags=["Games"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def to_card_summary(card: CardsXGame) -> dict:
    return {
        "id": card.id_card,
        "name": card.card.name if card.card else None,
        "type": card.card.type.value if card.card and card.card.type else None,
        "img": card.card.img_src if card.card else None,
    }

class VictimRequest(BaseModel):
    ActionsPerTurn.player_target.id # ID del jugador victima

@router.post("/{room_id}/another_victim")
async def another_victim(
    room_id: int,
    request: VictimRequest,
    actor_user_id: int = Header(..., alias="HTTP_USER_ID"),
    db: Session = Depends(get_db)
):
    
    room = db.query(Room).filter(Room.id == room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    game = db.query(Game).filter(Game.room_id == room_id).first()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    actor = db.query(Player).filter(Player.user_id == actor_user_id).first()
    if not actor:
        raise HTTPException(status_code=404, detail="Actor not found")  
    
    victim = db.query(Player).filter(Player.user_id == request.user_id).first()
    if not victim:
        raise HTTPException(status_code=404, detail="Victim not found")

    if actor.id == victim.id:
        raise HTTPException(status_code=400, detail="Cannot target yourself")
    
    victim_sets = db.query(CardsXGame).filter(
        CardsXGame.player_id == victim.id,
        CardsXGame.id_game == game.id,
        CardsXGame.is_in == CardState.DETECTIVE_SET
    ).all()

    

    

    


    



