# app/routes/discard.py
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from app.db.database import SessionLocal
from app.db.models import Game, Room, CardsXGame, CardState, Player
from app.schemas.discard_schema import DiscardRequest, DiscardResponse
from app.services.discard import descartar_cartas
from app.services.game_service import actualizar_turno
from app.sockets.socket_service import get_websocket_service
from app.services.game_status_service import build_complete_game_state

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

@router.post("/{room_id}/discard", response_model=DiscardResponse, status_code=200)
async def discard_cards(
    room_id: int,
    request: DiscardRequest,
    user_id: int = Header(..., alias="HTTP_USER_ID"),
    db: Session = Depends(get_db)
):
    room = db.query(Room).filter(Room.id == room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="not_found")
    
    game = db.query(Game).filter(Game.id == room.id_game).first()
    if not game:
        raise HTTPException(status_code=404, detail="game_not_found")
    
    # validar turno
    if game.player_turn_id != user_id:
        raise HTTPException(status_code=403, detail="forbidden")
    
    # validar cartas en la mano
    card_ids_with_order = request.card_ids
    if not card_ids_with_order:
        raise HTTPException(status_code=400, detail="validation_error: empty card list")

    card_ids = [c.card_id for c in card_ids_with_order]

    print(f"🎯 POST /discard received: {DiscardRequest}")

    player_cards = (
        db.query(CardsXGame)
        .filter(
            CardsXGame.player_id == user_id,
            CardsXGame.id_game == game.id,
            CardsXGame.is_in == CardState.HAND,
            CardsXGame.id.in_(card_ids)
        )
        .all()
    )
    
    if len(player_cards) != len(card_ids):
        raise HTTPException(status_code=400, detail="validation_error: invalid or not owned cards")
    print(f"❌ Orden después del query (DESORDENADO): {[c.id_card for c in player_cards]}")  # LOG 2

    # reordenar cartas para mantener orden de descarte
    card_dict = {card.id: card for card in player_cards}
    ordered_player_cards = [card_dict[card_id] for card_id in card_ids]
    ordered_card_ids = [c.id_card for c in ordered_player_cards]
    print(f"✅ Orden corregido: {ordered_card_ids}")  # LOG 3

    # descartar
    discarded = await descartar_cartas(db, game, user_id, ordered_player_cards)
    # Capture card IDs BEFORE any other operation that might detach objects
    discarded_card_ids = [c.id_card for c in discarded]
    print(f"📤 Orden final descartado: {discarded_card_ids}")  # LOG 4
  

    # Check deck count
    deck_count = db.query(CardsXGame).filter(
        CardsXGame.id_game == game.id,
        CardsXGame.is_in == CardState.DECK
    ).count()

    # Get all players
    players = db.query(Player).filter(Player.id_room == room_id).order_by(Player.order.asc()).all()
    
    all_hand_cards = db.query(CardsXGame).filter(
        CardsXGame.id_game == game.id,
        CardsXGame.player_id == user_id,
        CardsXGame.is_in == CardState.HAND
    ).all()
    
    # armar response usando helper
    response = DiscardResponse(
        action={
            "discarded": [to_card_summary(c) for c in discarded],
            "drawn": []
        },
        hand={
            "player_id": user_id,
            "cards": [to_card_summary(c) for c in all_hand_cards]
        },
        deck={
            "remaining": db.query(CardsXGame)
                .filter(CardsXGame.id_game == game.id, CardsXGame.is_in == CardState.DECK)
                .count()
        },
        discard={
            "top": to_card_summary(discarded[-1]) if discarded else None,
            "count": db.query(CardsXGame)
                .filter(CardsXGame.id_game == game.id, CardsXGame.is_in == CardState.DISCARD)
                .count()
        }
    )

    print(f"response: {response.discard.top}")

    game_state = build_complete_game_state(db, game.id)

    # Emit complete game state via WebSocket
    ws_service = get_websocket_service()
    await ws_service.notificar_estado_partida(
        room_id=room_id,
        jugador_que_actuo=user_id,
        game_state=game_state
    )

    await ws_service.notificar_player_must_draw(
        room_id=room_id,
        player_id=user_id,
        cards_to_draw=len(discarded)
    )

    # Verificar todo el mazo de descarte
    all_discarded = db.query(CardsXGame).filter(
        CardsXGame.id_game == game.id,
        CardsXGame.is_in == CardState.DISCARD
    ).order_by(CardsXGame.position.asc()).all()

    print(f"\n MAZO DE DESCARTE COMPLETO (orden por position):")
    for card in all_discarded:
        print(f"  Position {card.position}: Carta {card.id_card} - {card.card.name if card.card else 'N/A'}")
    print(f"Total: {len(all_discarded)} cartas\n")

    return response
