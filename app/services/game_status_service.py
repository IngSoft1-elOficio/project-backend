from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.db import crud, models
from app.schemas.game_status_schema import (
    GameStateView, GameView, PlayerView, CardSummary, 
    DeckView, DiscardView, HandView, SecretsView, TurnInfo,
    STATUS_MAPPING
)
from typing import Dict, Any, Optional, List

def get_game_status_service(db: Session, game_id: int, user_id: int) -> GameStateView:
    """Recupera el estado de la partida y valida la pertenencia del usuario."""
    
    # Validaciones
    game, room, player = _validate_game_access(db, game_id, user_id)
    
    # Obtener datos base
    players = crud.list_players_by_room(db, room.id)
    
    # Construir componentes del estado
    return GameStateView(
        game=_build_game_view(game, room, players),
        players=_build_players_view(players),
        deck=_build_deck_view(db, game_id),
        discard=_build_discard_view(db, game_id),
        hand=_build_hand_view(db, game_id, user_id),
        secrets=_build_secrets_view(db, game_id, user_id),
        turn=_build_turn_info(game, players, user_id)
    )

def _validate_game_access(db: Session, game_id: int, user_id: int):
    """Valida que el juego existe y el usuario puede acceder."""
    
    # Verificar game
    game = crud.get_game_by_id(db, game_id)
    if not game:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "game_not_found", "message": "La partida no existe", "details": None}
        )

    # Verificar room
    room = db.query(models.Room).filter(models.Room.id_game == game_id).first()
    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "room_not_found", "message": "La sala no existe", "details": None}
        )
    
    # Verificar partida iniciada
    if room.status != "INGAME":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "game_not_started", 
                "message": "La partida aún no fue iniciada", 
                "details": {"room_id": room.id}
            }
        )

    # Verificar pertenencia del usuario
    player = crud.get_player_by_id(db, user_id)
    if not player or player.id_room != room.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "forbidden", "message": "El usuario no pertenece a esta partida", "details": None}
        )

    return game, room, player

def _build_game_view(game, room, players):
    """Construye GameView con datos básicos del juego."""
    host_player = next((p for p in players if p.is_host), None)
    
    return GameView(
        id=game.id,
        name=room.name,
        players_min=room.players_min,
        players_max=room.players_max,
        status=STATUS_MAPPING.get(room.status, room.status.lower()),
        host_id=host_player.id if host_player else 0
    )

def _build_players_view(players):
    """Construye lista de PlayerView."""
    return [
        PlayerView(
            id=p.id,
            name=p.name,
            avatar=p.avatar_src,
            birthdate=p.birthdate.strftime("%Y-%m-%d"),
            is_host=p.is_host,
            order=p.order
        ) for p in players
    ]

def _build_deck_view(db: Session, game_id: int):
    deck_count = crud.count_cards_by_state(db, game_id, "DECK")
    draft_entries = db.query(models.CardsXGame).filter(
        models.CardsXGame.id_game == game_id,
        models.CardsXGame.is_in == "DRAFT"
    ).order_by(models.CardsXGame.position.asc()).all()
    draft = [
        CardSummary(
            id=entry.id,  # id único de CardsXGame
            card_id=entry.card.id,  # id base de la carta
            name=entry.card.name,
            type=entry.card.type,
            img=entry.card.img_src
        ) for entry in draft_entries if entry.card
    ]
    return DeckView(remaining=deck_count, draft=draft)

def _build_discard_view(db: Session, game_id: int):
    """Construye DiscardView con carta superior y contador."""
    top_discard_entry = crud.get_top_card_by_state(db, game_id, "DISCARD")
    discard_count = crud.count_cards_by_state(db, game_id, "DISCARD")
    
    top_card = None
    if top_discard_entry and top_discard_entry.card:
        top_card = CardSummary(
            id=top_discard_entry.card.id,
            name=top_discard_entry.card.name,
            type=top_discard_entry.card.type,
            img=top_discard_entry.card.img_src
        )
    
    return DiscardView(top=top_card, count=discard_count)

def _build_hand_view(db: Session, game_id: int, user_id: int):
    """Construye HandView del usuario solicitante."""
    player_cards = crud.list_cards_by_player(db, user_id, game_id)
    
    hand_cards = [
        CardSummary(
            id=cxg.card.id,
            name=cxg.card.name,
            type=cxg.card.type,
            img=cxg.card.img_src
        ) for cxg in player_cards 
        if cxg.is_in == "HAND" and cxg.card
    ]
    
    return HandView(player_id=user_id, cards=hand_cards) if hand_cards else None

def _build_secrets_view(db: Session, game_id: int, user_id: int):
    """Construye SecretsView del usuario solicitante."""
    player_cards = crud.list_cards_by_player(db, user_id, game_id)
    
    secret_cards = [
        CardSummary(
            id=cxg.card.id,
            name=cxg.card.name,
            type=cxg.card.type,
            img=cxg.card.img_src
        ) for cxg in player_cards 
        if cxg.is_in == "SECRET_SET" and cxg.card
    ]
    
    return SecretsView(player_id=user_id, cards=secret_cards) if secret_cards else None

def _build_turn_info(game, players, user_id: int):
    """Construye TurnInfo con información de turnos."""
    turn_order = [p.id for p in sorted(players, key=lambda x: x.order or 999)]
    
    return TurnInfo(
        current_player_id=game.player_turn_id,
        order=turn_order,
        can_act=game.player_turn_id == user_id
    )

def build_complete_game_state(db: Session, game_id: int) -> Dict[str, Any]:
    """
    Build complete game state with public and private data
    Returns structure compatible with notificar_estado_completo
    """
    
    # Get game using CRUD
    game = crud.get_game_by_id(db, game_id)
    if not game:
        return {}
    
    # Get room
    room = db.query(models.Room).filter(models.Room.id_game == game_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="Sala no encontrada")
    
    # Get all players in room using CRUD
    players = crud.list_players_by_room(db, room.id)
    
    # Build public player data
    jugadores = []
    for player in players:
        # Count cards by state for this player
        hand_count = db.query(models.CardsXGame).filter(
            models.CardsXGame.player_id == player.id,
            models.CardsXGame.id_game == game_id,
            models.CardsXGame.is_in == models.CardState.HAND
        ).count()
        
        revealed_secrets_count = db.query(models.CardsXGame).filter(
            models.CardsXGame.player_id == player.id,
            models.CardsXGame.id_game == game_id,
            models.CardsXGame.is_in == models.CardState.SECRET_SET,
            models.CardsXGame.hidden == False  # Revealed secrets
        ).count()
        
        has_detective_set = db.query(models.CardsXGame).filter(
            models.CardsXGame.player_id == player.id,
            models.CardsXGame.id_game == game_id,
            models.CardsXGame.is_in == models.CardState.DETECTIVE_SET
        ).count() > 0

        # Count total secrets (SECRET_SET)
        total_secrets_count = db.query(models.CardsXGame).filter(
            models.CardsXGame.player_id == player.id,
            models.CardsXGame.id_game == game_id,
            models.CardsXGame.is_in == models.CardState.SECRET_SET
        ).count()

        # Count revealed secrets (hidden == False)
        revealed_secrets = db.query(models.CardsXGame).join(models.Card).filter(
            models.CardsXGame.player_id == player.id,
            models.CardsXGame.id_game == game_id,
            models.CardsXGame.is_in == models.CardState.SECRET_SET,
            models.CardsXGame.hidden == False
        ).all()

        revealed_secrets_list = [
            {
                "id": c.id,
                "name": c.card.name,
                "img_src": c.card.img_src,
                "type": c.card.type.value
            }
            for c in revealed_secrets
        ]
        
        jugadores.append({
            "player_id": player.id,
            "name": player.name,
            "avatar_src": player.avatar_src,
            "order": player.order,
            "is_host": player.is_host,
            "hand_size": hand_count,
            "total_secrets_count": total_secrets_count,
            "revealed_secrets_count": len(revealed_secrets_list),
            "revealed_secrets": revealed_secrets_list,
            "detective_set": has_detective_set
        })

    # Build mazos (decks) data using CRUD helpers
    deck_count = crud.count_cards_by_state(db, game_id, models.CardState.DECK.value)
    discard_count = crud.count_cards_by_state(db, game_id, models.CardState.DISCARD.value)

    discard_top = (
        db.query(models.CardsXGame)
        .join(models.Card)
        .filter(
            models.CardsXGame.id_game == game_id,
            models.CardsXGame.is_in == models.CardState.DISCARD
        )
        .order_by(models.CardsXGame.position.desc())  
        .first()
    )

   # Get top 3 cards from DECK (not DRAFT)
    get_draft = db.query(models.CardsXGame).join(models.Card).filter(
        models.CardsXGame.id_game == game_id,
        models.CardsXGame.is_in == models.CardState.DECK
    ).order_by(models.CardsXGame.position.desc()).limit(3).all()

    draft = [
        {
            "id": c.id,  # CardsXGame.id
            "name": c.card.name,
            "img_src": c.card.img_src,
            "type": c.card.type.value
        }
        for c in get_draft
    ]
    
    mazos = {
        "deck": {
            "count": deck_count,
            "draft": draft    
        },
        "discard": {
            "count": discard_count,
            "top": discard_top.card.img_src if discard_top else ""
        }
    }
    
    sets = []

    # Get all DETECTIVE_SET cards for this game
    detective_set_cards = db.query(models.CardsXGame).filter(
        models.CardsXGame.id_game == game_id,
        models.CardsXGame.is_in == models.CardState.DETECTIVE_SET
    ).all()

    # Count manually by player
    detective_counts = {}
    for c in detective_set_cards:
        if c.player_id is None:
            continue
        detective_counts[c.player_id] = detective_counts.get(c.player_id, 0) + 1

    for player_id, count in detective_counts.items():
        sets.append({
            "owner_id": player_id,
            "set_type": models.CardState.DETECTIVE_SET.value,
            "count": count
        })

    # Build private states for each player
    estados_privados = {}
    for player in players:
        # Get hand cards using relationship
        hand_cards = db.query(models.CardsXGame).join(models.Card).filter(
            models.CardsXGame.player_id == player.id,
            models.CardsXGame.id_game == game_id,
            models.CardsXGame.is_in == models.CardState.HAND
        ).all()
        
        mano = [
            {
                "id": c.id,  # CardsXGame.id (instance ID)
                "name": c.card.name,
                "description": c.card.description,
                "type": c.card.type.value,
                "img_src": c.card.img_src
            }
            for c in hand_cards
        ]
        
        # Get secrets (SECRET_SET state)
        secret_cards = db.query(models.CardsXGame).join(models.Card).filter(
            models.CardsXGame.player_id == player.id,
            models.CardsXGame.id_game == game_id,
            models.CardsXGame.is_in == models.CardState.SECRET_SET
        ).all()
        
        secretos = [
            {
                "id": c.id,  # CardsXGame.id
                "name": c.card.name,
                "description": c.card.description,
                "img_src": c.card.img_src,
                "revealed": not c.hidden  
            }
            for c in secret_cards
        ]
        
        estados_privados[player.id] = {
            "user_id": player.id,
            "mano": mano,
            "secretos": secretos
        }
    
    # Build complete state
    return {
        "game_id": game_id,
        "status": room.status.value,
        "turno_actual": game.player_turn_id,
        "jugadores": jugadores,
        "mazos": mazos,
        "sets": sets, 
        "estados_privados": estados_privados
    }