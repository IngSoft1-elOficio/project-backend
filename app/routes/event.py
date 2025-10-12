from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from app.db.database import SessionLocal
from pydantic import BaseModel
from app.db.models import Game, Room, CardsXGame, CardState, Player, RoomStatus, Card, ActionsPerTurn
from app.sockets.socket_service import get_websocket_service
from app.schemas.event_schema import OneMoreStartRequest, OneMoreStartResponse
from datetime import datetime

router = APIRouter(prefix="/api/game", tags=["Events"])

#abro sesion en la bd
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# One-More: Permite elegir un secreto revelado y añadirlo oculto en el set de secretos de cualquier jugador
@router.post("/{room_id}/event/one-more", response_model = OneMoreStartResponse, status_code = 200)
async def one_more(
    room_id: int,
    payload: OneMoreStartRequest,
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

            # Crear registro en actions_per_turn
    action = ActionsPerTurn(
        id_game = game.id,
        actionName = "and_then_one_more",
        player_id = user_id,              
        parent_action_id = None,       
        to_be_hidden = False    #indica si la accion va a ocultar cartas
    )

    db.add(action)
    db.commit()
    db.refresh(action)

    #ahora tengo q obtener los secretos revelados y ponerlos en avaliable_secrets
    secrets = db.query(CardsXGame).filter(CardsXGame.id_game == game.id, CardsXGame.is_in == CardState.SECRET_SET,
                                         CardsXGame.hidden == False).all()
    available_secrets_ids = [s.id for s in secrets]


    #notifico a todos la carta q se esta jugando
    ws_service = get_websocket_service()
    await ws_service.notificar_event_action_started(
        room_id = room_id,
        player_id = user_id,
        event_type = "one_more",
        card_name = "And Then There Was One More",
        step = "selecting_secret"
    )

    return {
        "action_id" : action.id,
        "available_secrets" : available_secrets_ids
    }















    #busco el secreto y chequeo q este revelado
    secret = db.query(CardsXGame).filter(CardsXGame.id == payload.secretId, CardsXGame.id_game == game.id, CardsXGame.is_in == CardState.SECRET_SET).first()
    if not secret:
        raise HTTPException(status_code = 404, detail = "secret_not_found")

    if secret.hidden:
        raise HTTPException(status_code = 400, detail = "secret_not_revealed")

    # chequeo que targetplayer exista en la partida
    target = db.query(Player).filter(Player.id == payload.targetPlayerId,Player.id_room == room_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="target_player_not_found")

    #guardo el owner 
    original_owner_id = secret.player_id

    # ahora q tengo el secreto, le cambio el player_id y el hidden
    secret.player_id = payload.targetPlayerId
    secret.hidden = True




