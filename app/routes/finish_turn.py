from fastapi import APIRouter, Query, Depends, HTTPException, Path
from sqlalchemy.orm import Session
from typing import List
from ..db.database import SessionLocal
from ..db.models import Room, Player, RoomStatus, Game, CardsXGame, CardState, Turn, TurnStatus
from app.sockets.socket_service import get_websocket_service
from fastapi import APIRouter, Query, Depends, HTTPException, Path
from app.services.game_status_service import build_complete_game_state

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

class FinishTurnRequest(BaseModel):
    user_id: int

@router.post("/game/{room_id}/finish-turn")
async def finish_turn(
    room_id: int,
    request: FinishTurnRequest,
    db: Session = Depends(get_db)
):
    print(f"🎯 POST /finish-turn received: {FinishTurnRequest}")

    # Buscar sala
    room = db.query(Room).filter(Room.id == room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="room_not_found")
    
    # Buscar partida
    game = db.query(Game).filter(Game.id == room.id_game).first()
    if not game:
        raise HTTPException(status_code=404, detail="game_not_found")

    # Validar turno
    if game.player_turn_id != request.user_id:
        raise HTTPException(status_code=403, detail="not_your_turn")
    
    # Buscar cartas en la mano del jugador
    # hand_cards = (
    #    db.query(CardsXGame).filter(
    #        CardsXGame.id_game == game.id,
    #        CardsXGame.player_id == request.user_id,
    #        CardsXGame.is_in == CardState.HAND
    #    ).order_by(CardsXGame.position.asc()).all()
    #)

    #if not hand_cards:
    #    raise HTTPException(status_code=400, detail="empty_hand")

    # Descartar primera carta
    # discarded = hand_cards[0]

    #Calcular la siguiente posición en el mazo de descarte
    #next_discard_pos = db.query(CardsXGame).filter(
    #    CardsXGame.id_game == game.id,
    #    CardsXGame.is_in == CardState.DISCARD
    #).count()

    #discarded.is_in = CardState.DISCARD
    #discarded.position = next_discard_pos  #Asignar posición correcta
    #discarded.player_id = None
    #db.add(discarded)

    #print(f"🔄 Skip turn: Descartada carta {discarded.id_card} en position {next_discard_pos}")

    # Robar del mazo
    #new_card = (
    #    db.query(CardsXGame).filter(
    #        CardsXGame.id_game == game.id,
    #        CardsXGame.is_in == CardState.DECK
    #    ).order_by(CardsXGame.position.asc()).first()
    #)

    #if not new_card:
    #    raise HTTPException(status_code=400, detail="deck_empty")
    
    #new_card.is_in = CardState.HAND
    #new_card.player_id = request.user_id
    #new_card.position = 0
    #db.add(new_card)
    
    # Avanzar turno
    players = db.query(Player).filter(Player.id_room == room.id).order_by(Player.order.asc()).all()

    current_order = next((p.order for p in players if p.id == request.user_id), None)
    next_order = (current_order % len(players)) + 1
    next_player = next((p for p in players if p.order == next_order), None)
    
    # Finalizar turno actual
    current_turn = db.query(Turn).filter(
        Turn.id_game == game.id,
        Turn.player_id == request.user_id,
        Turn.status == TurnStatus.IN_PROGRESS
    ).first()
    
    if current_turn:
        current_turn.status = TurnStatus.FINISHED
        db.add(current_turn)
        print(f"🔄 Turn {current_turn.number} finished for player {request.user_id}")
        
        # Crear nuevo turno para el siguiente jugador
        new_turn = Turn(
            number=current_turn.number + 1,
            id_game=game.id,
            player_id=next_player.id,
            status=TurnStatus.IN_PROGRESS,
            start_time=datetime.now()
        )
        db.add(new_turn)
        print(f"🆕 Turn {new_turn.number} created for player {next_player.id}")
    else:
        print(f"⚠️ No active turn found for player {request.user_id}")
    
    game.player_turn_id = next_player.id
    
    db.commit()
    db.refresh(game)

    deck_count = db.query(CardsXGame).filter(CardsXGame.id_game == game.id, CardsXGame.is_in == CardState.DECK).count()

    # Build game state
    game_state = build_complete_game_state(db, game.id)
       

    ws_service = get_websocket_service()
    await ws_service.notificar_estado_partida(
        room_id=room_id,
        jugador_que_actuo=request.user_id,
        game_state=game_state
    )
    await ws_service.notificar_turn_finished(room_id=room_id, player_id=request.user_id)
    
    return {
        "status": "ok",
        "next_turn": next_player.id
    }