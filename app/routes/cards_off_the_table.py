# app/routes/cards_off_the_table.py
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from app.db.database import SessionLocal
from pydantic import BaseModel
from app.db.models import Game, Room, CardsXGame, CardState, Player, RoomStatus, Card
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

class Victim(BaseModel):
    user_id: int


@router.post("/game/{room_id}/cards_off_the_table")
async def cards_off_the_table(
    room_id: int,
    request: Victim,
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

    # Busco al jugador victima
    victim = db.query(Player).filter(Player.id == request.user_id).first()
    if not victim:
        raise HTTPException(status_code=404, detail="player_not_found")


    player_cards = (db.query(CardsXGame)
        .filter(
            CardsXGame.player_id == victim.id,
            CardsXGame.id_game == game.id,
            CardsXGame.is_in == CardState.HAND,
            CardsXGame.id_card.in_(card_ids)
        )
        .all()
    )

    nsf_cards = [card for card in player_cards if card.id == 13]

    if len(nsf_cards) == 0:
        

    else:
        for card_in_hand in nsf_cards:
            card_in_game.state = CardState.DISCARD

        db.commit()

        # Repongo las cartas
        drawn = await robar_cartas_del_mazo(db, game., victim.id, len(nsf_cards))

        db.refresh(victim)
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