from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from app.db.database import SessionLocal
from pydantic import BaseModel
from app.db.models import Game, Room, CardsXGame, CardState, Player, RoomStatus, Card, ActionsPerTurn
from app.sockets.socket_service import get_websocket_service
from app.schemas.event_schema import (delay_escape_start_request, delay_escape_start_response, delay_escape_order_request, delay_escape_order_response)
from datetime import datetime

router = APIRouter(prefix="/api/game", tags=["Events"])

#abro sesion en la bd
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Delay de murderer escape: traigo las uotimas x cartas del mazo de descarte
@router.post("/{room_id}/event/delay-murderer-escape", response_model = delay_escape_start_response, status_code = 200 )
async def delay_murderer_step_1(
    room_id: int,
    payload: delay_escape_start_request,
    user_id: int = Header(..., alias = "HTTP_USER_ID"),
    db: Session = Depends(get_db)
):

    #busco sala
    room = crud.get_room_by_id(db, room_id)
    if not room:
        raise HTTPException(status_code = 404, detail = "room_not_found")

    #busco partida
    game = crud.get_game_by_id(db, room.id_game)
    if not game :
        raise HTTPException(status_code = 404 , detail = "game_not_found")

    #validar turno
    if game.player_turn_id != user_id:
        raise HTTPException(status_code = 403, detail = "not_your_turn")

    # Validar que la carta esté en mano del jugador
    event_card = db.query(models.CardsXGame).filter(
        models.CardsXGame.id == payload.card_id,
        models.CardsXGame.player_id == user_id,
        models.CardsXGame.id_game == room.id_game,
        models.CardsXGame.is_in == models.CardState.HAND
    ).first()
    
    if not event_card:
        raise HTTPException(
            status_code=404, 
            detail="Event card not found in your hand"
        )
    
    # Validate card type is EVENT
    if event_card.card.type != models.CardType.EVENT:
        raise HTTPException(
            status_code=400,
            detail="Card is not an event card"
        )
    
    try:
        # Crear registro en actions_per_turn
        current_turn = crud.get_current_turn(db, room.id_game)
        action_data = {
            'id_game': room.id_game,
            'turn_id': current_turn.id,
            'player_id': user_id,
            'action_name': models.ActionName.DELAY_THE_MURDERERS_ESCAPE,
            'action_type': models.ActionType.EVENT_CARD,
            'result': models.ActionResult.SUCCESS,
            'selected_card_id': event_card.id
        }
        
        action = crud.create_action(db, action_data)

        db.commit()

        #chequeo cuantas cartas tiene el mazo de descarte
        discard_cards = crud.count_cards_by_state(db, room.id_game, CardState.DISCARD)

        # si la cantidad de cartas del mazo de descarte es menor q las q quiere el jugador
        if discard_cards < payload.quantity:
            last_cards = (
                db.query(models.CardsXGame)
                .join(models.Card)
                .filter(
                    models.CardsXGame.id_game == room.id_game,
                    models.CardsXGame.is_in == models.CardState.DISCARD,
                )
                .order_by(models.CardsXGame.position.desc())
                .limit(discard_cards)
                .all()
            )
        else:
            last_cards = (
                db.query(models.CardsXGame)
                .join(models.Card)
                .filter(
                    models.CardsXGame.id_game == room.id_game,
                    models.CardsXGame.is_in == models.CardState.DISCARD,
                )
                .order_by(models.CardsXGame.position.desc())
                .limit(payload.quantity)
                .all()
            )


        
        available_cards_id = [card.id for card in last_cards]

        #notifico q se jugo la carta
        ws_service = get_websocket_service()
        await ws_service.notificar_event_action_started(
            room_id = room_id,
            player_id = user_id,
            event_type = "delay_murderer",
            card_name = "Delay The Murderer's Escape",
            step = "selecting_order"
        )

        return {
            "action_id" : action.id,
            "available_cards" : available_cards_id
        }

    except Exception as e:
        db.rollback()
        import logging
        logging.exception("Error creating action in delay_murderer_step_1")
        raise HTTPException(status_code=500, detail="internal_error_creating_action")

# Delay de murderer escape:pongo las cartas del mazo de descarte en el regular en el orden q recibo
@router.post("/{room_id}/event/delay-murderer-escape/order", response_model = delay_escape_order_response, status_code = 200 )
async def delay_murderer_order(
    room_id: int,
    payload: delay_escape_order_request,
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

    #si no hay cartas en el mazo de descarte
    descarte = db.query(CardsXGame).filter(CardsXGame.id_game == game.id, CardsXGame.is_in == CardState.DISCARD).count()
    if descarte == 0:
        raise HTTPException (status_code = 404, detail = "the_card_cannot_be_played")

    #hay q cambiar discard a deck en el orden correcto, primero obtengo la posicion maxima

    max_pos = db.query(CardsXGame.position).filter(game.id == CardsXGame.id_game, CardsXGame.is_in == CardState.DECK).order_by(
              CardsXGame.position.desc()).first() # devuelve una tupla (3,)

    max_position = max_pos[0] if max_pos else 0 # me quedo solo con la posicion

    #reordeno
    for i, card_id in enumerate(payload.orderer_cards_ids):
        card = db.query(CardsXGame).filter( CardsXGame.id == card_id, CardsXGame.id_game == game.id , CardsXGame.is_in == CardState.DISCARD).first()
        if not card:
            raise HTTPException (status_code = 404, detail = "card_not_found")
        card.is_in = CardState.DECK
        card.position = (max_position + i + 1) 

    db.commit()

    #transmitir ws

    ws_service = get_websocket_service()
    await ws_service.notificar_event_action_complete(
        room_id = room_id,
        player_id = user_id,
        event_type = "delay_murderer_escape"
    )

    return {
        "success" : True
    }


    