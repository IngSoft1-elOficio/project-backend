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
    
    deck_count_before = db.query(CardsXGame).filter(
        CardsXGame.id_game == game.id,
        CardsXGame.is_in == CardState.DECK
    ).count()
    
    # descartar
    discarded = await descartar_cartas(db, game, user_id, card_ids)
    
    # reponer (solo si hay cartas en el mazo)
    drawn = []
    if deck_count_before > 0:
        cantidad_a_robar = min(len(discarded), deck_count_before)
        drawn = await robar_cartas_del_mazo(db, game, user_id, cantidad_a_robar)
    
    # Check deck count DESPUES para ver si se acabó
    deck_count_after = db.query(CardsXGame).filter(
        CardsXGame.id_game == game.id,
        CardsXGame.is_in == CardState.DECK
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
            "remaining": deck_count_after
        },
        discard={
            "top": to_card_summary(discarded[-1]) if discarded else None,
            "count": db.query(CardsXGame)
                .filter(CardsXGame.id_game == game.id, CardsXGame.is_in == CardState.DISCARD)
                .count()
        }
    )

    # Check for game end (si se acabó el mazo Y robamos la última carta)
    if deck_count_after == 0 and drawn:
        from app.services.game_service import procesar_ultima_carta
        
        # Construir game_state para procesar_ultima_carta
        game_state_for_end = {
            "game_id": game.id,
            "room_id": room_id,
            "status": "INGAME",
            "turno_actual": game.player_turn_id,
            "jugadores": [
                {"id": p.id, "name": p.name, "is_host": p.is_host, "order": p.order} 
                for p in players
            ],
            "mazos": {
                "deck": 0,
                "discard": response.discard.count,
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
        
        await procesar_ultima_carta(
            game_id=game.id,
            room_id=room_id,
            carta=drawn[-1].card.name,
            game_state=game_state_for_end,
            jugador_que_actuo=user_id
        )
    else:
        game_state_public = {
            "game_id": game.id,
            "room_id": room_id,
            "status": "INGAME",
            "turno_actual": game.player_turn_id,
            "jugadores": [
                {
                    "id": p.id, 
                    "name": p.name, 
                    "is_host": p.is_host, 
                    "order": p.order,
                    "card_count": db.query(CardsXGame).filter(
                        CardsXGame.id_game == game.id,
                        CardsXGame.player_id == p.id,
                        CardsXGame.is_in == CardState.HAND
                    ).count()
                } 
                for p in players
            ],
            "mazos": {
                "deck": response.deck.remaining,  
                "discard": response.discard.count,  
            },
            "timestamp": datetime.now().isoformat()
        }
        
        # Enviar estado público a todos
        ws_service = get_websocket_service()
        await ws_service.emit_to_room(
            room_id=room_id,
            event="game_state_public",
            data=game_state_public
        )
        
        for player in players:
            player_hand = [
                {"id": c.id_card, "name": c.card.name, "type": c.card.type.value, "img": c.card.img_src}
                for c in db.query(CardsXGame).filter(
                    CardsXGame.id_game == game.id,
                    CardsXGame.player_id == player.id,
                    CardsXGame.is_in == CardState.HAND
                ).all()
            ]
            
            player_secrets = [
                {"id": c.id_card, "name": c.card.name, "type": c.card.type.value, "img": c.card.img_src}
                for c in db.query(CardsXGame).filter(
                    CardsXGame.id_game == game.id,
                    CardsXGame.player_id == player.id,
                    CardsXGame.is_in == CardState.SECRET_SET
                ).all()
            ]
            
            game_state_private = {
                "player_id": player.id,
                "mano": player_hand,
                "secretos": player_secrets,
                "timestamp": datetime.now().isoformat()
            }
            
            # Buscar el SID del jugador y enviar directamente
            sids = ws_service.ws_manager.get_sids_in_game(room_id)
            for sid in sids:
                session = ws_service.ws_manager.get_user_session(sid)
                if session and session.get("user_id") == player.id:
                    await ws_service.ws_manager.emit_to_sid(sid, "game_state_private", game_state_private)
                    break
    
    return response