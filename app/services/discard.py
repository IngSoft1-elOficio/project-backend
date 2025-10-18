# app/services/discard.py
from sqlalchemy.orm import Session
from app.db.models import CardsXGame, CardState, Game, ActionType, SourcePile, ActionResult, ActionName
from app.db.crud import get_current_turn, create_parent_card_action, create_card_action
from typing import List

async def descartar_cartas(db, game, user_id, ordered_player_cards):
    discarded = []

    # Get current turn for action logging
    current_turn = get_current_turn(db, game.id)
    if not current_turn:
        raise ValueError(f"No active turn found for game {game.id}")

    # Create parent action for the complete discard operation
    parent_action = create_parent_card_action(
        db=db,
        game_id=game.id,
        turn_id=current_turn.id,
        player_id=user_id,
        action_type=ActionType.DISCARD,
        action_name=ActionName.END_TURN_DISCARD,
        source_pile=SourcePile.DISCARD_PILE
    )

    next_pos = db.query(CardsXGame).filter(
        CardsXGame.id_game == game.id,
        CardsXGame.is_in == CardState.DISCARD
    ).count()
    print(f"🔢 Próxima posición en descarte: {next_pos}")

    for i, card in enumerate(ordered_player_cards):
        # Eliminar duplicados (si existen)
        db.query(CardsXGame).filter(
            CardsXGame.id_game == game.id,
            CardsXGame.id_card == card.id_card,
            CardsXGame.player_id == user_id,
            CardsXGame.is_in != CardState.HAND
        ).delete(synchronize_session=False)
        
        # Descartar la carta (ya tenemos el objeto, no necesitamos buscarlo)
        card.is_in = CardState.DISCARD
        card.position = next_pos + i  # Ahora i empieza en 0, así que está bien
        discarded.append(card)
        
        # Log individual discard action
        create_card_action(
            db=db,
            game_id=game.id,
            turn_id=current_turn.id,
            player_id=user_id,
            action_type=ActionType.DISCARD,
            source_pile=SourcePile.DISCARD_PILE,
            card_id=card.id_card,
            position=card.position,
            result=ActionResult.SUCCESS
        )
        
        print(f"  Carta {card.id_card} → posición {card.position}")
    
    # Capture card IDs before commit (to avoid ObjectDeletedError)
    discarded_card_ids = [c.id_card for c in discarded]
    
    db.commit()
    
    # Refresh objects to make them accessible after commit
    for card in discarded:
        db.refresh(card)
    
    print(f"✅ Total descartado en orden: {discarded_card_ids}")
    return discarded