# app/routes/discard.py
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from app.db.database import SessionLocal
from app.db.models import Game, Room, CardsXGame, CardState
from app.schemas.discard_schema import DiscardRequest, DiscardResponse
from app.services.game_service import (
    descartar_cartas,
    robar_cartas_del_mazo,
    actualizar_turno,
    emitir_eventos_ws
)

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
        "type": card.card.type if card.card else None,
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

    # turno
    await actualizar_turno(db, game)

    # armar response usando helper
    response = DiscardResponse(
        action={
            "discarded": [to_card_summary(c) for c in discarded],
            "drawn": [to_card_summary(c) for c in drawn]
        },
        hand={
            "player_id": user_id,
            "cards": [to_card_summary(c) for c in drawn]
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

    # eventos WS
    await emitir_eventos_ws(
        game,
        user_id,
        response.action,
        response.hand.model_dump(),
        response.deck,
        response.discard
    )

    return response
