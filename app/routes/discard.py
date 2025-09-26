# app/routes/discard.py
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from typing import List
from app.db.database import SessionLocal
from app.db.models import Game, Room, Player, RoomStatus, CardsXGame, CardState
from app.schemas.discard_schema import DiscardRequest, DiscardResponse

router = APIRouter(prefix="/game", tags=["Game"])

# Conexión a la DB
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/{room_id}/discard", response_model=DiscardResponse, status_code=200)
async def discard_cards(room_id: int, request: DiscardRequest,
                        user_id: int = Header(..., alias="HTTP_USER_ID"), db: Session = Depends(get_db)):
    # buscar la room
    room = db.query(Room).filter(Room.id == room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="not_found")
    
    # validar que sea el turno del participante
    game = db.query(Game).filter(Game.id == room.id_game).first()
    if not game:
        raise HTTPException(status_code=404, detail="not_found")

    if game.player_turn_id != user_id:
        raise HTTPException(status_code=403, detail="forbidden")

    #Validar pertenencia de las cartas a la mano del jugador y cantidad > 0
    card_ids = request.card_ids
    if not card_ids:
        raise HTTPException(status_code=400, detail="validation error")
    
    player_cards = (db.query(CardsXGame).filter(CardsXGame.player_id == user_id, CardsXGame.id_game == game.id,
                                               CardsXGame.is_in == CardState.HAND, CardsXGame.id_card.in_(card_ids)).all())
    
    if len(player_cards) != len(card_ids):
        raise HTTPException(status_code=400, detail="validation_error")
