from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from app.db.database import SessionLocal
from pydantic import BaseModel
from app.db.models import Game, Room, CardsXGame, CardState, Player, RoomStatus, Card, ActionsPerTurn
from app.sockets.socket_service import get_websocket_service
from app.schemas.delay_schema import (delay_escape_request, delay_escape_response)
from datetime import datetime
from app.db import crud, models
from app.services.game_status_service import build_complete_game_state

router = APIRouter(prefix="/api/game", tags=["Events"])

#abro sesion en la bd
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from app.db.database import SessionLocal
from app.db import crud, models
from app.schemas.delay_schema import delay_escape_request, delay_escape_response
from app.sockets.socket_service import get_websocket_service
from app.services.game_status_service import build_complete_game_state

router = APIRouter(prefix="/api/game", tags=["Events"])


# Abro sesión en la BD
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/{room_id}/event/delay-murderer-escape",
             response_model=delay_escape_response,
             status_code=200)
async def delay_murderer_escape(
    room_id: int,
    payload: delay_escape_request,
    user_id: int = Header(..., alias="HTTP_USER_ID"),
    db: Session = Depends(get_db)
):
    # Buscar sala
    room = crud.get_room_by_id(db, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="room_not_found")

    # Buscar partida
    game = crud.get_game_by_id(db, room.id_game)
    if not game:
        raise HTTPException(status_code=404, detail="game_not_found")

    # Validar turno
    if game.player_turn_id != user_id:
        raise HTTPException(status_code=403, detail="not_your_turn")

    # Validar carta
    event_card = db.query(models.CardsXGame).filter(
        models.CardsXGame.id == payload.card_id,
        models.CardsXGame.player_id == user_id,
        models.CardsXGame.id_game == room.id_game,
        models.CardsXGame.is_in == models.CardState.HAND
    ).first()

    if not event_card:
        raise HTTPException(status_code=404, detail="event_card_not_found")
    if event_card.card.type != models.CardType.EVENT:
        raise HTTPException(status_code=400, detail="not_an_event_card")

    try:
        current_turn = crud.get_current_turn(db, room.id_game)
        parent_action = crud.create_action(db, {
            "id_game": room.id_game,
            "turn_id": current_turn.id,
            "player_id": user_id,
            "action_name": models.ActionName.DELAY_THE_MURDERERS_ESCAPE,
            "action_type": models.ActionType.EVENT_CARD,
            "result": models.ActionResult.SUCCESS,
            "selected_card_id": event_card.id
        })

        # Cartas del descarte
        discard_cards = (
            db.query(models.CardsXGame)
            .filter(
                models.CardsXGame.id_game == room.id_game,
                models.CardsXGame.is_in == models.CardState.DISCARD
            )
            .order_by(models.CardsXGame.position.desc())
            .limit(payload.quantity)
            .all()
        )

        if not discard_cards:
            raise HTTPException(status_code=400, detail="discard_pile_empty")


        # Obtener posición mínima del mazo regular (tope)
        top_card = (
            db.query(models.CardsXGame)
            .filter(
                models.CardsXGame.id_game == room.id_game,
                models.CardsXGame.is_in == models.CardState.DECK
            )
            .order_by(models.CardsXGame.position.asc())
            .first()
        )
        min_position = top_card.position if top_card else 1

        moved_cards_ids = []

        #  Queremos que la última del descarte quede en el tope → invertimos
        discard_cards = list(reversed(discard_cards))

        # Calcular posiciones nuevas, todas menores al tope actual
        # Si el tope es posición 5, y movemos 3 cartas → nuevas posiciones serán [2,3,4]? No, queremos [2,3,4]? no, [min-3,min-2,min-1]
        new_positions = list(range(min_position - len(discard_cards), min_position))

        for card, new_pos in zip(discard_cards, new_positions):
            card.is_in = models.CardState.DECK
            card.position = new_pos
            card.hidden = True
            moved_cards_ids.append(card.id)

        # Eliminar carta de evento
        event_card.is_in = models.CardState.REMOVED
        event_card.position = 0
        event_card.hidden = True

        db.commit()

        # Mostrar orden final con posiciones
        deck_cards = (
            db.query(models.CardsXGame)
            .filter(
                models.CardsXGame.id_game == room.id_game,
                models.CardsXGame.is_in == models.CardState.DECK
            )
            .order_by(models.CardsXGame.position.asc())
            .all()
        )
        
        crud.create_action(db, {
            "id_game": room.id_game,
            "turn_id": parent_action.turn_id,
            "player_id": user_id,
            "action_type": models.ActionType.MOVE_CARD,
            "action_name": "Delay The Murderer's Escape!",
            "result": models.ActionResult.SUCCESS,
            "parent_action_id": parent_action.id,
            "source_pile": models.SourcePile.DISCARD_PILE,
        })

        db.commit()

        ws_service = get_websocket_service()
        await ws_service.notificar_event_action_started(
            room_id=room_id,
            player_id=user_id,
            event_type="delay_murderer_escape",
            card_name="Delay The Murderer's Escape",
            step="played"
        )
        await ws_service.notificar_event_action_complete(
            room_id=room_id,
            player_id=user_id,
            event_type="delay_murderer_escape"
        )

        game_state = build_complete_game_state(db, game.id)
        await ws_service.notificar_estado_publico(room_id=room_id, game_state=game_state)
        await ws_service.notificar_estados_privados(
            room_id=room_id,
            estados_privados=game_state.get("estados_privados", {})
        )

        return {
            "status": "ok",
            "action_id": parent_action.id,
            "moved_cards": moved_cards_ids
        }

    except Exception as e:
        db.rollback()
        import logging
        logging.exception("Error in delay_murderer_escape")
        raise HTTPException(status_code=500, detail="internal_error_delay_murderer_escape")

