from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from app.db.database import SessionLocal
from typing import Optional
from datetime import datetime, timedelta

from app.db import models, crud
from app.sockets.socket_service import get_websocket_service
from app.services.game_status_service import build_complete_game_state
from app.schemas.look_ashes_schema import LookAshesPlayRequest, LookAshesSelectRequest

router = APIRouter(prefix="/api/game", tags=["event_cards"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ---------------------------------------
# LOOK INTO THE ASHES - STEP 1: PLAY CARD
# ---------------------------------------

@router.post("/{room_id}/look-into-ashes/play")
async def play_look_into_ashes(
    room_id: int,
    request: LookAshesPlayRequest,
    http_user_id: int = Header(..., alias="http-user-id"),  # Fixed: Use alias for kebab-case
    db: Session = Depends(get_db)
):
    """
    Step 1: Player plays "Look Into The Ashes" event card
    Shows top 5 cards from discard pile (private to player)
    
    Returns:
        action_id: ActionsPerTurn.id to use in next step
        available_cards: Top 5 cards from discard (private info)
    """

    print(f"Received room: {room_id} player: {http_user_id} card: {request.card_id}")
    
    # Get room and game
    room = crud.get_room_by_id(db, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    
    if not room.id_game:
        raise HTTPException(status_code=400, detail="Room has no active game")
    
    game = crud.get_game_by_id(db, room.id_game)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    
    # Validate it's player's turn
    if game.player_turn_id != http_user_id:
        raise HTTPException(status_code=403, detail="Not your turn")
    
    # Validate event card is in player's hand
    event_card = db.query(models.CardsXGame).filter(
        models.CardsXGame.id == request.card_id,
        models.CardsXGame.player_id == http_user_id,
        models.CardsXGame.id_game == room.id_game,
        models.CardsXGame.is_in == models.CardState.HAND
    ).first()
    
    if not event_card:
        raise HTTPException(
            status_code=404, 
            detail="Event card not found in your hand"
        )
    
    # Validate card type is EVENT
    if event_card.card.type != models.CardType.EVENT:
        raise HTTPException(
            status_code=400,
            detail="Card is not an event card"
        )
    
    # Get top 5 cards from discard pile
    discard_cards = db.query(models.CardsXGame).join(models.Card).filter(
        models.CardsXGame.id_game == room.id_game,
        models.CardsXGame.is_in == models.CardState.DISCARD
    ).order_by(
        models.CardsXGame.position.desc()  # Most recent first
    ).limit(5).all()
    
    if not discard_cards:
        raise HTTPException(
            status_code=400, 
            detail="Discard pile is empty"
        )
    
    # Get current turn using crud helper
    current_turn = crud.get_current_turn(db, room.id_game)
    
    if not current_turn:
        raise HTTPException(
            status_code=400,
            detail="No active turn found"
        )
    
    # Move event card to DISCARD immediately
    max_discard_pos = crud.get_max_position_by_state(db, room.id_game, models.CardState.DISCARD)
    
    event_card.is_in = models.CardState.DISCARD
    event_card.player_id = None
    event_card.position = max_discard_pos + 1
    event_card.hidden = False  # Events in discard are visible
    
    # Create action in ActionsPerTurn using crud helper
    action_data = {
        'id_game': room.id_game,
        'turn_id': current_turn.id,
        'player_id': http_user_id,
        'action_name': models.ActionName.LOOK_INTO_THE_ASHES.value,
        'action_type': models.ActionType.EVENT_CARD,
        'result': models.ActionResult.SUCCESS,
        'selected_card_id': event_card.id  # CardsXGame.id of the event card
    }
    
    action = crud.create_action(db, action_data)
    db.commit()
    db.refresh(action)
    
    # Notify all players (WITHOUT showing which cards)
    ws_service = get_websocket_service()
    await ws_service.notificar_event_action_started(
        room_id=room_id,
        player_id=http_user_id,
        event_type="look_ashes",
        card_name="Look Into The Ashes",
        step="viewing_cards"
    )
    
    # Format cards for response (PRIVATE - only to requesting player)
    available_cards = [
        {
            "id": c.id,  # CardsXGame.id
            "name": c.card.name,
            "description": c.card.description,
            "type": c.card.type.value,
            "img_src": c.card.img_src,
            "position": c.position
        }
        for c in discard_cards
    ]
    
    return {
        "success": True,
        "action_id": action.id,  # ActionsPerTurn.id
        "available_cards": available_cards
    }

# -----------------------------------------
# LOOK INTO THE ASHES - STEP 2: SELECT CARD
# -----------------------------------------

@router.post("/{room_id}/look-into-ashes/select")
async def select_card_from_ashes(
    room_id: int,
    request: LookAshesSelectRequest,
    http_user_id: int = Header(..., alias="http-user-id"),  # Fixed: Use alias
    db: Session = Depends(get_db)
):
    """
    Step 2: Player selects one card from the 5 shown
    Moves card to player's hand
    
    Returns:
        success: True if card was taken
    """
    
    # Get room and game
    room = crud.get_room_by_id(db, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    
    game = crud.get_game_by_id(db, room.id_game)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    
    # Get parent action using crud helper
    parent_action = crud.get_action_by_id(db, request.action_id)
    
    if not parent_action:
        raise HTTPException(status_code=404, detail="Parent action not found")
    
    # Validate parent action belongs to this player and game
    if (parent_action.id_game != room.id_game or 
        parent_action.player_id != http_user_id or
        parent_action.action_name != models.ActionName.LOOK_INTO_THE_ASHES.value or
        parent_action.result != models.ActionResult.SUCCESS):
        raise HTTPException(
            status_code=400,
            detail="Invalid parent action"
        )
    
    # Check action is not too old (10 minutes timeout)
    if parent_action.action_time < datetime.now() - timedelta(minutes=10):
        raise HTTPException(
            status_code=400,
            detail="Action expired"
        )
    
    # Get the selected card
    selected_card = db.query(models.CardsXGame).filter(
        models.CardsXGame.id == request.selected_card_id,
        models.CardsXGame.id_game == room.id_game,
        models.CardsXGame.is_in == models.CardState.DISCARD
    ).first()
    
    if not selected_card:
        raise HTTPException(
            status_code=404, 
            detail="Selected card not found in discard pile"
        )
    
    # Validate selected card is within top 5 of discard
    top_5 = db.query(models.CardsXGame).filter(
        models.CardsXGame.id_game == room.id_game,
        models.CardsXGame.is_in == models.CardState.DISCARD
    ).order_by(models.CardsXGame.position.desc()).limit(5).all()
    
    top_5_ids = [c.id for c in top_5]
    
    if request.selected_card_id not in top_5_ids:
        raise HTTPException(
            status_code=400,
            detail="Selected card is not in the top 5 of discard pile"
        )
    
    # Store old position before moving
    old_position = selected_card.position
    
    # Get current hand size using crud helper
    hand_count = db.query(models.CardsXGame).filter(
        models.CardsXGame.player_id == http_user_id,
        models.CardsXGame.id_game == room.id_game,
        models.CardsXGame.is_in == models.CardState.HAND
    ).count()
    
    # Move card to player's hand
    selected_card.is_in = models.CardState.HAND
    selected_card.player_id = http_user_id
    selected_card.position = hand_count  # Add to end of hand
    selected_card.hidden = True
    
    # Create completion action using crud helper
    completion_action_data = {
        'id_game': room.id_game,
        'turn_id': parent_action.turn_id,
        'player_id': http_user_id,
        'action_type': models.ActionType.DRAW,
        'action_name': None,  # Not needed for DRAW type
        'result': models.ActionResult.SUCCESS,
        'parent_action_id': parent_action.id,
        'card_received_id': selected_card.id,  # Card taken
        'source_pile': models.SourcePile.DISCARD_PILE,
        'position_card': old_position
    }
    
    completion_action = crud.create_action(db, completion_action_data)
    db.commit()
    
    # Notify all players (WITHOUT revealing which card was taken)
    ws_service = get_websocket_service()
    
    await ws_service.notificar_event_action_complete(
        room_id=room_id,
        player_id=http_user_id,
        event_type="look_ashes"
    )
    
    # Update full game state
    game_state = build_complete_game_state(db, room.id_game)
    await ws_service.notificar_estado_completo(
        room_id=room_id,
        game_state=game_state,
        partida_finalizada=False
    )
    
    return {
        "success": True,
        "card_taken": {
            "id": selected_card.id,
            "name": selected_card.card.name
        }
    }