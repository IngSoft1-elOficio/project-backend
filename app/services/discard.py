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
    
    # Capture card IDs and prepare data before any deletion
    card_ids_to_process = [card.id_card for card in ordered_player_cards]
    
    for i, card in enumerate(ordered_player_cards):
        # Eliminar duplicados (si existen) - pero NO la carta actual
        db.query(CardsXGame).filter(
            CardsXGame.id_game == game.id,
            CardsXGame.id_card == card.id_card,
            CardsXGame.player_id == user_id,
            CardsXGame.is_in != CardState.HAND,
            CardsXGame.id != card.id  # ← IMPORTANTE: No eliminar la carta actual
        ).delete(synchronize_session=False)
        
        # Descartar la carta (modificar el objeto existente)
        card.is_in = CardState.DISCARD
        card.position = next_pos + i
        discarded.append(card)
        
        # Log individual discard action with parent reference
        create_card_action(
            db=db,
            game_id=game.id,
            turn_id=current_turn.id,
            player_id=user_id,
            action_type=ActionType.DISCARD,
            source_pile=SourcePile.DISCARD_PILE,
            card_id=card.id_card,
            position=card.position,
            result=ActionResult.SUCCESS,
            parent_action_id=parent_action.id
        )
        
        print(f"📤 Carta {card.id_card} → posición {card.position}")
    
    # Flush changes to database but don't commit yet
    db.flush()
    
    # Commit all changes at once
    db.commit()
    
    # After commit, the objects are still valid - no need to refresh
    # The attributes are already updated in memory
    
    print(f"✅ Total descartado en orden: {card_ids_to_process}")
    
    return discarded