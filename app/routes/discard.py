# app/routes/discard.py
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from app.db.database import SessionLocal
from app.db.models import Game, Room, CardsXGame, CardState, Player
from app.schemas.discard_schema import DiscardRequest, DiscardResponse
from app.services.game_service import (
    descartar_cartas,
    robar_cartas_del_mazo,
    actualizar_turno
)
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
    card_ids = request.card_ids
    if not card_ids:
        raise HTTPException(status_code=400, detail="validation_error: empty card list")
    
    player_cards = (
        db.query(CardsXGame)
        .filter(
            CardsXGame.player_id == user_id,
            CardsXGame.id_game == game.id,
            CardsXGame.is_in == CardState.HAND,
            CardsXGame.id_card.in_(card_ids)
        )
        .all()
    )
    
    if len(player_cards) != len(card_ids):
        raise HTTPException(status_code=400, detail="validation_error: invalid or not owned cards")
    
    # descartar
    discarded = await descartar_cartas(db, game, user_id, card_ids)
    
    # reponer
    drawn = await robar_cartas_del_mazo(db, game, user_id, len(discarded))

    # Check deck count
    deck_count = db.query(CardsXGame).filter(
        CardsXGame.id_game == game.id,
        CardsXGame.is_in == CardState.DEC
    ).count()
    
    # turno
    await actualizar_turno(db, game)
    
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
            "drawn": [to_card_summary(c) for c in drawn]
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

    # Check for game end
    if deck_count == 0 and drawn:
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
            game_state={
                "game_id": game.id,
                "status": "INGAME",
                "turno_actual": game.player_turn_id,
                "jugadores": [{"id": p.id, "name": p.name, "is_host": p.is_host, "order": p.order} for p in players],
                "mazos": {
                    "deck": response.deck.remaining,  
                    "discard": response.discard.count,  
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