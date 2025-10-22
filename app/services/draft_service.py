from sqlalchemy.orm import Session
from app.db.models import CardsXGame, ActionType, SourcePile, ActionResult, ActionName
from app.db.crud import get_current_turn, create_card_action, create_parent_card_action
from app.services.game_status_service import _build_deck_view
from app.schemas.discard_schema import CardSummary
from app.schemas.take_deck import CardSummary

def list_draft_cards(db: Session, game_id: int) -> list[CardSummary]:
    list_draft = _build_deck_view(db, game_id)
    return list_draft.draft

def pick_card_from_draft(db: Session, card_id: int, user_id: int) -> CardSummary:
    # Buscar la carta en el draft
    draft_entry = db.query(CardsXGame).filter(
        CardsXGame.id == card_id,
        CardsXGame.is_in == 'DRAFT'
    ).first()
    if not draft_entry:
        return None

    game_id = draft_entry.id_game
    selected_pos = draft_entry.position

    # Get current turn for action logging
    current_turn = get_current_turn(db, game_id)
    if not current_turn:
        raise ValueError(f"No active turn found for game {game_id}")

    # Create parent action for the draft pick operation (pick + replenish)
    parent_action = create_parent_card_action(
        db=db,
        game_id=game_id,
        turn_id=current_turn.id,
        player_id=user_id,
        action_type=ActionType.DRAW,
        action_name=ActionName.DRAFT_PHASE,
        source_pile=SourcePile.DRAFT_PILE
    )

    # Buscar la posicion maxima en la mano
    max_pos = db.query(CardsXGame.position).filter(
        CardsXGame.id_game == game_id,
        CardsXGame.player_id == user_id,
        CardsXGame.is_in == 'HAND'
    ).order_by(CardsXGame.position.desc()).first()
    next_pos = (max_pos[0] if max_pos else 0) + 1

    # Log draft pick action (child of parent)
    create_card_action(
        db=db,
        game_id=game_id,
        turn_id=current_turn.id,
        player_id=user_id,
        action_type=ActionType.DRAW,
        source_pile=SourcePile.DRAFT_PILE,
        card_id=draft_entry.id_card,
        position=selected_pos,
        result=ActionResult.SUCCESS,
        parent_action_id=parent_action.id
    )

    # Mover la carta a la mano del jugador
    draft_entry.is_in = 'HAND'
    draft_entry.player_id = user_id
    draft_entry.position = next_pos
    db.commit()
    db.refresh(draft_entry)

    # Reponer el draft con la carta del tope del mazo
    top_deck = db.query(CardsXGame).filter(
        CardsXGame.id_game == game_id,
        CardsXGame.is_in == 'DECK'
    ).order_by(CardsXGame.position.asc()).first()
    if top_deck:
        # Log deck-to-draft replenishment action (child of parent)
        create_card_action(
            db=db,
            game_id=game_id,
            turn_id=current_turn.id,
            player_id=user_id,  # Who triggered the replenishment
            action_type=ActionType.DRAW,  # Moving from deck to draft
            source_pile=SourcePile.DRAFT_PILE,
            card_id=top_deck.id_card,
            position=top_deck.position,
            result=ActionResult.SUCCESS,
            parent_action_id=parent_action.id
        )
        
        top_deck.is_in = 'DRAFT'
        top_deck.position = selected_pos
        db.commit()
        db.refresh(top_deck)

    # Retornar la carta robada
    return CardSummary(
        id = draft_entry.id,
        name = draft_entry.card.name if draft_entry.card else None,
        type = draft_entry.card.type.value if draft_entry.card and draft_entry.card.type else None,
        img = draft_entry.card.img_src if draft_entry.card else None
    )