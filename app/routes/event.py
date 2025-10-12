from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from app.db.database import SessionLocal
from pydantic import BaseModel
from app.db.models import Game, Room, CardsXGame, CardState, Player, RoomStatus, Card
from app.sockets.socket_service import get_websocket_service
from app.schemas.event_schema import AndThenOneMoreRequest, AndThenOneMoreEffect, AndThenOneMoreResponse

router = APIRouter(prefix="/api/game", tags=["Events"])

#abro sesion en la bd
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# One-More: Permite elegir un secreto revelado y añadirlo oculto en el set de secretos de cualquier jugador
@router.post("/{room_id}/event/one-more", response_model = AndThenOneMoreResponse, status_code = 200)
async def one_more(
    room_id: int,
    payload: AndThenOneMoreRequest,
    user_id: int = Header(..., alias = "HTTP_USER_ID"),
    db: Session = Depends(get_db)
):


    #busco sala
    room = db.query(Room).filter(Room.id == room_id).first()
    if not room:
        raise HTTPException(status_code = 404, detail = "room_not_found")
    #busco partida
    game = db.query(Game).filter(Game.id == room.id_game).first()
    if not game :
        raise HTTPException(status_code = 404 , detail = "game_not_found")

    #validar turno
    if game.player_turn_id != user_id:
        raise HTTPException(status_code = 403, detail = "not_your_turn")

    #busco el secreto y chequeo q este oculto
    secret = db.query(CardsXGame).filter(CardsXGame.id == payload.secretId, CardsXGame.is_in == CardState.SECRET_SET).first()
    if not secret:
        raise HTTPException(status_code = 404, detail = "secret_not_found")

    if secret.hidden:
        raise HTTPException(status_code = 400, detail = "secret_not_revealed")

    # ahora q tengo el secreto, le cambio el player_id y el hidden
    secret.player_id = payload.targetPlayerId
    secret.hidden = True
    db.commit()

