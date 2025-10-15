from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import SessionLocal
from app.db.models import Game, Room, CardsXGame, CardState
from app.schemas.draft import DraftRequest
from app.services.draft_service import list_draft_cards, pick_card_from_draft
from app.services.game_service import procesar_ultima_carta
from app.services.game_status_service import _build_hand_view, _build_deck_view, build_complete_game_state
from app.sockets.socket_service import get_websocket_service
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/game/{game_id}/draft", tags=["Draft"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/pick", status_code=200)
async def pick_card(game_id: int, draft_request: DraftRequest, db: Session = Depends(get_db)):
    try:
        # Validar juego
        game = db.query(Game).filter(Game.id == game_id).first()
        if not game:
            raise HTTPException(status_code=404, detail="game_not_found")

        # Validar turno
        if game.player_turn_id != draft_request.user_id:
            raise HTTPException(status_code=403, detail="not_your_turn")

        # Validar que el jugador pueda robar hasta 6 cartas
        new_hand = _build_hand_view(db, game_id, draft_request.user_id)
        if hasattr(new_hand, "cards"):
            hand_count = len(new_hand.cards)
        elif isinstance(new_hand, list):
            hand_count = len(new_hand)
        else:
            hand_count = 0
        if hand_count >= 6:
            raise HTTPException(status_code=403, detail="must_discard_before_draft")

        # Obtener cartas del draft y validar que la carta este ahi
        draft_cards = list_draft_cards(db, game_id)
        print("draft_request.card_id =", draft_request.card_id)
        print("draft_cards =", [c.id for c in draft_cards])
        card = next((card for card in draft_cards if card.id == draft_request.card_id), None)
        if not card:
            raise HTTPException(status_code=404, detail="Card not found in draft")

        # Mover la carta a la mano del jugador
        picked_card = pick_card_from_draft(db, draft_request.card_id, draft_request.user_id)

        # Actualizar mano, draft y deck
        game_state = build_complete_game_state(db, game_id)
        new_hand = _build_hand_view(db, game_id, draft_request.user_id)
        new_deck = _build_deck_view(db, game_id)

        # Obtener room_id para las notificaciones
        room = db.query(Room).filter(Room.id_game == game_id).first()
        room_id = room.id if room else game_id

        # Verificar si el draft esta vacio para terminar la partida
        draft_remaining = db.query(CardsXGame).filter(
            CardsXGame.id_game == game_id,
            CardsXGame.is_in == CardState.DRAFT
        ).count()

        # Emitir eventos por WebSocket
        try:
            ws_service = get_websocket_service()
            
            if draft_remaining == 0:
                await procesar_ultima_carta(game_id=game_id, room_id=room_id, game_state=game_state)
            else:
                # Notificar al jugador su mano actualizada
                await ws_service.notificar_estados_privados(room_id=room_id, estados_privados=game_state["estados_privados"])
                # Notificar a la sala el estado del deck y draft
                await ws_service.notificar_estado_partida(room_id=room_id, jugador_que_actuo=draft_request.user_id, game_state=game_state)
                # Notificar a todos que el jugador robo del draft
                await ws_service.notificar_card_drawn_simple(
                    room_id=room_id,
                    player_id=draft_request.user_id,
                    drawn_from="draft",
                    cards_remaining= 6 - len(new_hand.cards)
                )
        except Exception as e:
            logger.error(f"Failed to notify WebSocket for room {room_id}: {e}")

        # Retornar la carta seleccionada y el nuevo estado
        return {"picked_card": picked_card, "hand": new_hand, "deck": new_deck}

    except Exception as e:
        import traceback
        logger.error("ERROR EN /draft/pick:\n", traceback.format_exc())
        raise HTTPException(status_code=400, detail=str(e))