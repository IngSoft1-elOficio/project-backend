from sqlalchemy.orm import Session
from app.db.models import CardsXGame, CardState, Game, ActionType, SourcePile, ActionResult, ActionName
from app.db.crud import get_current_turn, create_parent_card_action, create_card_action
from typing import List

async def robar_cartas_del_mazo(db, game, user_id, cantidad):
    print(f"🎴 Robando {cantidad} carta(s) del mazo para jugador {user_id}")
    
    # Get current turn for action logging
    current_turn = get_current_turn(db, game.id)
    if not current_turn:
        raise ValueError(f"No active turn found for game {game.id}")

    # Create parent action for the complete draw operation
    parent_action = create_parent_card_action(
        db=db,
        game_id=game.id,
        turn_id=current_turn.id,
        player_id=user_id,
        action_type=ActionType.DRAW,
        action_name=ActionName.DRAW_FROM_DECK,
        source_pile=SourcePile.DRAW_PILE
    )
    
    drawn = (
        db.query(CardsXGame)
        .filter(CardsXGame.id_game == game.id,
                CardsXGame.is_in == CardState.DECK)
        .order_by(CardsXGame.position)  
        .limit(cantidad)
        .all()
    )
    
    for card in drawn:
        # Log individual draw action before modifying the card with parent reference
        create_card_action(
            db=db,
            game_id=game.id,
            turn_id=current_turn.id,
            player_id=user_id,
            action_type=ActionType.DRAW,
            source_pile=SourcePile.DRAW_PILE,
            card_id=card.id_card,
            position=card.position,
            result=ActionResult.SUCCESS,
            parent_action_id=parent_action.id
        )
        
        # resetear dueño
        card.player_id = user_id
        card.is_in = CardState.HAND
        print(f"  ✓ Carta {card.id_card} ({card.card.name if card.card else 'N/A'}) → mano del jugador")

    db.commit()
    print(f"✅ Total robado: {len(drawn)} carta(s)")
    return drawn