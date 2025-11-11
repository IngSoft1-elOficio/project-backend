# app/services/early_train_discard.py
from typing import Optional
from sqlalchemy.orm import Session
from app.db.models import CardsXGame, CardState, ActionType, ActionResult, SourcePile, ActionName
from app.db.crud import create_parent_card_action, create_card_action
from app.sockets.socket_service import get_websocket_service
import logging

logger = logging.getLogger(__name__)

async def early_train_discard_effect(db: Session, game_id: int, player_id: int, room_id):

    first_six = db.query(CardsXGame).filter(
        CardsXGame.id_game == game_id, 
        CardsXGame.is_in == CardState.DECK).order_by(CardsXGame.position.desc()).limit(6).all()
    

    if not first_six:

        if room_id:
            ws = get_websocket_service()
            await ws.notificar_event_step_update(
                room_id=room_id,
                player_id=player_id,
                event_type="early_train",
                step="finish",
                message=f"Jugador {player_id} activó Early Train to Paddington, pero el mazo está vacío."
            )
        return

    num_to_move = len(first_six)
    logger.info(f"early_train: moviendo {num_to_move} cartas del deck al discard.")

    max_discard_pos_row = (
        db.query(CardsXGame.position)
        .filter(CardsXGame.id_game == game_id, CardsXGame.is_in == CardState.DISCARD)
        .order_by(CardsXGame.position.desc())
        .first()
    )
    next_pos = (max_discard_pos_row[0] + 1) if max_discard_pos_row else 1

    parent_action = create_parent_card_action(
        db=db,
        game_id=game_id,
        turn_id=None,
        player_id=player_id,
        action_type=ActionType.DISCARD,
        action_name=ActionName.EARLY_TRAIN_TO_PADDINGTON,
        source_pile=SourcePile.DISCARD_PILE
    )

    for i, card in enumerate(first_six):
        old_pos = card.position
        card.is_in = CardState.DISCARD
        card.position = next_pos + i
        card.player_id = None
        card.hidden = False

        create_card_action(
            db=db,
            game_id=game_id,
            turn_id=None,
            player_id=player_id,
            action_type=ActionType.DISCARD,
            source_pile=SourcePile.DISCARD_PILE,
            card_id=card.id_card,
            position=card.position,
            result=ActionResult.SUCCESS,
            parent_action_id=parent_action.id
        )

        logger.debug(f"early_train: moved card id_card={card.id_card} old_pos={old_pos} -> new_pos={card.position}")

    db.flush()
    db.commit()

    try:
        ws = get_websocket_service()
        await ws.notificar_event_step_update(
            room_id=room_id,
            player_id=player_id,
            event_type="early_train",
            step="finish",
            message=f"Jugador {player_id} activó Early Train to Paddington: {num_to_move} cartas movidas al descarte."
        )
        logger.info("early_train")
    except Exception as e:
        logger.exception(f"error enviando notificación {e}")

    logger.info(f"early_train: efecto completado. {num_to_move} cartas movidas.")
