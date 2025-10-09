from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from app.db.database import SessionLocal
from app.db.models import Game, Room, CardsXGame, CardState, Player
from app.schemas.take_deck import TakeDeckRequest, TakeDeckResponse
from app.services.take_deck import robar_cartas_del_mazo
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
    """Convierte CardsXGame a diccionario"""
    return {
        "id": card.id_card,
        "name": card.card.name if card.card else None,
        "type": card.card.type.value if card.card and card.card.type else None,
        "img": card.card.img_src if card.card else None,
    }

@router.post("/{room_id}/take-deck", response_model=TakeDeckResponse, status_code=200)
async def take_from_deck(
    room_id: int,
    request: TakeDeckRequest,
    user_id: int = Header(..., alias="HTTP_USER_ID"),
    db: Session = Depends(get_db)
):
    """Endpoint para robar cartas del mazo regular"""
    
    # Validar sala
    room = db.query(Room).filter(Room.id == room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="room_not_found")
    
    # Validar juego
    game = db.query(Game).filter(Game.id == room.id_game).first()
    if not game:
        raise HTTPException(status_code=404, detail="game_not_found")
    
    # Validar turno
    if game.player_turn_id != user_id:
        raise HTTPException(status_code=403, detail="not_your_turn")
    
    print(f"🎴 Jugador {user_id} quiere robar {request.cantidad} carta(s)")
    
    # Robar cartas
    drawn = await robar_cartas_del_mazo(db, game, user_id, request.cantidad)
    
    if not drawn:
        raise HTTPException(status_code=400, detail="deck_empty")
    
    # Obtener mano actualizada
    hand = db.query(CardsXGame).filter(
        CardsXGame.id_game == game.id,
        CardsXGame.player_id == user_id,
        CardsXGame.is_in == CardState.HAND
    ).all()
    
    # Contar cartas restantes en el mazo
    deck_remaining = db.query(CardsXGame).filter(
        CardsXGame.id_game == game.id,
        CardsXGame.is_in == CardState.DECK
    ).count()
    
    print(f"✅ Robadas {len(drawn)} carta(s). Quedan {deck_remaining} en el mazo")
    
    # Preparar respuesta
    response = TakeDeckResponse(
        drawn=[to_card_summary(c) for c in drawn],
        hand=[to_card_summary(c) for c in hand],
        deck_remaining=deck_remaining
    )
    
    # Notificar vía WebSocket (opcional - si querés que otros vean que robó)
    players = db.query(Player).filter(Player.id_room == room_id).order_by(Player.order.asc()).all()
    
    ws_service = get_websocket_service()
    await ws_service.notificar_estado_partida(
        room_id=room_id,
        jugador_que_actuo=user_id,
        game_state={
            "game_id": game.id,
            "status": "INGAME",
            "turno_actual": game.player_turn_id,
            "jugadores": [{"id": p.id, "name": p.name, "is_host": p.is_host, "order": p.order} for p in players],
            "mazos": {
                "deck": deck_remaining,
                "discard": db.query(CardsXGame).filter(
                    CardsXGame.id_game == game.id,
                    CardsXGame.is_in == CardState.DISCARD
                ).count(),
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
    )
    
    return response