from fastapi import APIRouter, Query, Depends, HTTPException, Path
from sqlalchemy.orm import Session
from typing import List
from ..db.database import SessionLocal
from ..db.models import Room, Player, RoomStatus, Game, CardsXGame, CardState
from app.sockets.socket_service import get_websocket_service
from fastapi import APIRouter, Query, Depends, HTTPException, Path
from pydantic import BaseModel
from datetime import datetime

router = APIRouter()

# Conexión a la DB
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class SkipRequest(BaseModel):
    user_id: int

@router.post("/game/{room_id}/skip")
async def skip_turn(
    room_id: int,
    request: SkipRequest,
    db: Session = Depends(get_db)
):
    # Buscar sala
    room = db.query(Room).filter(Room.id == room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="room_not_found")
    
    # Buscar partida
    game = db.query(Game).filter(Game.id == room.id_game).first()
    if not game:
        raise HTTPException(status_code=404, detail="game_not_found")

    # DEBUG: Log the comparison
    print(f"DEBUG: game.player_turn_id = {game.player_turn_id}, request.user_id = {request.user_id}")
    print(f"DEBUG: Types - turn_id: {type(game.player_turn_id)}, user_id: {type(request.user_id)}")

    # Validar turno
    if game.player_turn_id != request.user_id:
        raise HTTPException(status_code=403, detail="not_your_turn")
    
    # Buscar cartas en la mano del jugador
    hand_cards = (
        db.query(CardsXGame).filter(
            CardsXGame.id_game == game.id,
            CardsXGame.player_id == request.user_id,
            CardsXGame.is_in == CardState.HAND
        ).order_by(CardsXGame.position.asc()).all()
    )

    if not hand_cards:
        raise HTTPException(status_code=400, detail="empty_hand")

    # Descartar primera carta
    discarded = hand_cards[0]

    #Calcular la siguiente posición en el mazo de descarte
    next_discard_pos = db.query(CardsXGame).filter(
        CardsXGame.id_game == game.id,
        CardsXGame.is_in == CardState.DISCARD
    ).count()

    discarded.is_in = CardState.DISCARD
    discarded.position = next_discard_pos  #Asignar posición correcta
    discarded.player_id = None
    db.add(discarded)

    print(f"🔄 Skip turn: Descartada carta {discarded.id_card} en position {next_discard_pos}")

    # Robar del mazo
    new_card = (
        db.query(CardsXGame).filter(
            CardsXGame.id_game == game.id,
            CardsXGame.is_in == CardState.DECK
        ).order_by(CardsXGame.position.asc()).first()
    )

    if not new_card:
        raise HTTPException(status_code=400, detail="deck_empty")
    
    new_card.is_in = CardState.HAND
    new_card.player_id = request.user_id
    new_card.position = 0
    db.add(new_card)
    
    # Avanzar turno
    players = db.query(Player).filter(Player.id_room == room.id).order_by(Player.order.asc()).all()
    
    current_order = next((p.order for p in players if p.id == request.user_id), None)
    next_order = (current_order % len(players)) + 1
    next_player = next((p for p in players if p.order == next_order), None)
    
    game.player_turn_id = next_player.id
    
    db.commit()
    db.refresh(game)

    # CHECK IF DECK IS EMPTY AFTER DRAWING
    deck_count = db.query(CardsXGame).filter(
        CardsXGame.id_game == game.id,
        CardsXGame.is_in == CardState.DECK
    ).count()
    
    # Build game state
    game_state = {
        "game_id": game.id,
        "status": "INGAME",
        "turno_actual": game.player_turn_id,
        "jugadores": [{"id": p.id, "name": p.name, "is_host": p.is_host, "order": p.order} for p in players],
        "mazos": {
            "deck": deck_count,
            "discard": {
                "top": db.query(CardsXGame).filter(
                CardsXGame.id_game == game.id,
                CardsXGame.is_in == CardState.DISCARD
            ).order_by(CardsXGame.position.asc()).first(), 
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
       
    # CHECK FOR GAME END
    if deck_count == 0:
        from app.services.game_service import procesar_ultima_carta
        await procesar_ultima_carta(
            game_id=game.id,
            room_id=room_id,
            carta=new_card.card.name,
            game_state=game_state,
            jugador_que_actuo=request.user_id
        )
    else:
        # Normal notification if game not finished
        ws_service = get_websocket_service()
        await ws_service.notificar_estado_partida(
            room_id=room_id,
            jugador_que_actuo=request.user_id,
            game_state=game_state
        )
    
    return {
        "status": "ok",
        "discarded_card_id": discarded.id_card,
        "new_card_id": new_card.id_card,
        "next_turn": next_player.id
    }