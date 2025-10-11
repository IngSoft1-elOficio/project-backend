# app/routes/cards_off_the_table.py
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from app.db.database import SessionLocal
from pydantic import BaseModel
from app.db.models import Game, Room, CardsXGame, CardState, Player
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
    user_id: int  # ID del jugador víctima


@router.post("/{room_id}/cards_off_the_table")
async def cards_off_the_table(
    room_id: int,
    request: VictimRequest,
    user_id: int = Header(..., alias="HTTP_USER_ID"),
    db: Session = Depends(get_db)
):
    # Busco la sala
    room = db.query(Room).filter(Room.id == room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="room_not_found")
    
    # Busco la partida
    game = db.query(Game).filter(Game.id == room.id_game).first()
    if not game:
        raise HTTPException(status_code=404, detail="game_not_found")
    
    # Validar turno
    if game.player_turn_id != user_id:
        raise HTTPException(status_code=403, detail="not_your_turn")

    # Busco al jugador víctima
    victim = db.query(Player).filter(Player.id == request.user_id).first()
    if not victim:
        raise HTTPException(status_code=404, detail="player_not_found")

    # Busco todas las cartas en la mano de la víctima
    victim_hand = db.query(CardsXGame).filter(
        CardsXGame.player_id == victim.id,
        CardsXGame.id_game == game.id,
        CardsXGame.is_in == CardState.HAND
    ).all()

    # Filtro solo las cartas NSF (id_card == 13)
    nsf_cards = [card for card in victim_hand if card.id_card == 13]

    # Check deck count ANTES de descartar/robar
    deck_count_before = db.query(CardsXGame).filter(
        CardsXGame.id_game == game.id,
        CardsXGame.is_in == CardState.DECK
    ).count()
    
    discarded = []
    drawn = []
    
    if len(nsf_cards) > 0:
        # Calcular siguiente posición en discard
        next_discard_pos = db.query(CardsXGame).filter(
            CardsXGame.id_game == game.id,
            CardsXGame.is_in == CardState.DISCARD
        ).count()
        
        # Descartar todas las cartas NSF
        for i, card in enumerate(nsf_cards):
            card.is_in = CardState.DISCARD
            card.player_id = None
            card.position = next_discard_pos + i
            discarded.append(card)
        
        db.commit()

        # Reponer cartas (solo si hay cartas en el mazo)
        if deck_count_before > 1:
            cantidad_a_robar = min(len(discarded), deck_count_before)
            drawn = await robar_cartas_del_mazo(db, game, victim.id, cantidad_a_robar)
    
    # Check deck count DESPUÉS para ver si se acabó
    deck_count_after = db.query(CardsXGame).filter(
        CardsXGame.id_game == game.id,
        CardsXGame.is_in == CardState.DECK
    ).count()
    
    # Avanzar turno
    await actualizar_turno(db, game)
    
    # Me traigo los players
    players = db.query(Player).filter(Player.id_room == room_id).order_by(Player.order.asc()).all()

    game_state = {
        "game_id": game.id,
        "status": "INGAME",
        "turno_actual": game.player_turn_id,
        "jugadores": [{"id": p.id, "name": p.name, "is_host": p.is_host, "order": p.order} for p in players],
        "mazos": {
            "deck": deck_count_after,
            "discard": {
                "top": to_card_summary(discarded[-1]) if discarded else None,
                "count": db.query(CardsXGame).filter(
                    CardsXGame.id_game == game.id,
                    CardsXGame.is_in == CardState.DISCARD
                ).count()
            }
        },
        "manos": {
            p.id: [
                {"id": c.id_card, "name": c.card.name, "type": c.card.type.value}
                for c in db.query(CardsXGame).filter(
                    CardsXGame.id_game == game.id,
                    CardsXGame.player_id == p.id,
                    CardsXGame.is_in == CardState.HAND
                ).all()
            ]
            for p in players
        },
        "secretos": {
            p.id: [
                {"id": c.id_card, "name": c.card.name, "type": c.card.type.value}
                for c in db.query(CardsXGame).filter(
                    CardsXGame.id_game == game.id,
                    CardsXGame.player_id == p.id,
                    CardsXGame.is_in == CardState.SECRET_SET
                ).all()
            ]
            for p in players
        },
        "timestamp": datetime.now().isoformat()
    }

    # Chequeo si el mazo está en 1 y se acabó el juego
    if deck_count_after == 1 and drawn:
        from app.services.game_service import procesar_ultima_carta
        await procesar_ultima_carta(
            game_id=game.id,
            room_id=room_id,
            carta=drawn[-1].card.name,
            game_state=game_state,
            jugador_que_actuo=user_id
        )
    else:
        # Emit complete game state via WebSocket
        ws_service = get_websocket_service()
        await ws_service.notificar_estado_partida(
            room_id=room_id,
            jugador_que_actuo=user_id,
            game_state=game_state
        )
    
    return {
        "status": "ok",
        "action": "cards_off_the_table",
        "victim_id": request.user_id,
        "nsf_cards_discarded": len(discarded),
        "cards_drawn": len(drawn),
        "had_nsf": len(nsf_cards) > 0,
        "next_turn": game.player_turn_id,
        "deck_remaining": deck_count_after
    }