from sqlalchemy.orm import Session
from . import models

# ------------------------------
# ROOM
# ------------------------------
def create_room(db: Session, room_data: dict):
    if 'players_min' not in room_data:
        room_data['players_min'] = 2
    if 'players_max' not in room_data:
        room_data['players_max'] = 6
    
    room = models.Room(**room_data)
    db.add(room)
    db.commit()
    db.refresh(room)
    return room

def get_room_by_id(db: Session, room_id: int):
    return db.query(models.Room).filter(models.Room.id == room_id).first()

def list_rooms(db: Session, status: str = None):
    query = db.query(models.Room)
    if status:
        query = query.filter(models.Room.status == status)
    return query.all()

def update_room_status(db: Session, room_id: int, status: str):
    room = get_room_by_id(db, room_id)
    if room:
        room.status = status
        db.commit()
        db.refresh(room)
    return room

# ------------------------------
# PLAYER
# ------------------------------
def create_player(db: Session, player_data: dict):
    player = models.Player(**player_data)
    db.add(player)
    db.commit()
    db.refresh(player)
    return player

def get_player_by_id(db: Session, player_id: int):
    return db.query(models.Player).filter(models.Player.id == player_id).first()

def list_players_by_room(db: Session, room_id: int):
    return db.query(models.Player).filter(models.Player.id_room == room_id).all()

def set_player_host(db: Session, player_id: int):
    player = get_player_by_id(db, player_id)
    if player:
        player.is_host = True
        db.commit()
        db.refresh(player)
    return player


# ------------------------------
# GAME
# ------------------------------
def create_game(db: Session, game_data: dict):
    game = models.Game(**game_data)
    db.add(game)
    db.commit()
    db.refresh(game)
    return game

def get_game_by_id(db: Session, game_id: int):
    return db.query(models.Game).filter(models.Game.id == game_id).first()

def update_player_turn(db: Session, game_id: int, next_player_id: int):
    game = db.query(models.Game).filter(models.Game.id == game_id).first()
    if game:
        game.player_turn_id = next_player_id
        db.commit()
        db.refresh(game)
    return game

# ------------------------------
# CARDSXGAME
# ------------------------------
def assign_card_to_player(db: Session, game_id: int, card_id: int, player_id: int, position: int, hidden: bool = True):
    card_entry = models.CardsXGame(
        id_game=game_id,
        id_card=card_id,
        player_id=player_id,
        is_in='HAND',
        position=position,
        hidden=hidden
    )
    db.add(card_entry)
    db.commit()
    db.refresh(card_entry)
    return card_entry

def move_card(db: Session, card_id: int, game_id: int, new_state: str, new_position: int, player_id: int = None, hidden: bool = None):
    card_entry = db.query(models.CardsXGame).filter(
        models.CardsXGame.id_card == card_id,
        models.CardsXGame.id_game == game_id
    ).first()
    if card_entry:
        card_entry.is_in = new_state
        card_entry.position = new_position
        if player_id is not None:
            card_entry.player_id = player_id
        if hidden is None:
            if new_state == 'DRAFT':
                hidden = False 
            elif new_state == 'DISCARD':
                hidden = new_position > 1 
            else:
                hidden = True  
        card_entry.hidden = hidden
        db.commit()
        db.refresh(card_entry)
    return card_entry

def list_cards_by_player(db: Session, player_id: int, game_id: int):
    return db.query(models.CardsXGame).filter(
        models.CardsXGame.player_id == player_id,
        models.CardsXGame.id_game == game_id
    ).all()

def list_cards_by_game(db: Session, game_id: int):
    return db.query(models.CardsXGame).filter(
        models.CardsXGame.id_game == game_id
    ).all()

# ------------------------------
# CARD 
# ------------------------------
def get_card_by_id(db: Session, card_id: int):
    return db.query(models.Card).filter(models.Card.id == card_id).first()

# ------------------------------
# HELPERS para DECK/DISCARD/DRAFT
# ------------------------------
def get_top_card_by_state(db: Session, game_id: int, state: str):
    """
    Devuelve la carta con mayor position en el estado dado (DECK o DISCARD) para un game_id.
    """
    return db.query(models.CardsXGame).filter(
        models.CardsXGame.id_game == game_id,
        models.CardsXGame.is_in == state
    ).order_by(models.CardsXGame.position.desc()).first()

def count_cards_by_state(db: Session, game_id: int, state: str):
    """
    Devuelve la cantidad de cartas en el estado dado (DECK, DISCARD o DRAFT) para un game_id.
    """
    return db.query(models.CardsXGame).filter(
        models.CardsXGame.id_game == game_id,
        models.CardsXGame.is_in == state
    ).count()

def check_card_qty(db: Session, card_id: int):
    """
    Verifica si una carta puede ser usada más veces según su qty.
    Retorna True si la carta aún tiene usos disponibles.
    """
    card = db.query(models.Card).filter(models.Card.id == card_id).first()
    if not card:
        return False
    
    used_qty = db.query(models.CardsXGame).filter(
        models.CardsXGame.id_card == card_id
    ).count()
    
    return used_qty < card.qty

# ------------------------------
# PLAY DETECTIVE SET
# ------------------------------

def get_active_turn_for_player(db: Session, game_id: int, player_id: int):
    """
    Obtiene el turno IN_PROGRESS de un jugador en un juego.
    
    Args:
        db: Sesión de base de datos
        game_id: ID del juego
        player_id: ID del jugador
    
    Returns:
        Turn o None si no hay turno activo
    """
    return db.query(models.Turn).filter(
        models.Turn.id_game == game_id,
        models.Turn.player_id == player_id,
        models.Turn.status == models.TurnStatus.IN_PROGRESS
    ).first()


def get_current_turn(db: Session, game_id: int):
    """
    Obtiene el turno actualmente en progreso para un juego.
    
    Args:
        db: Sesión de base de datos
        game_id: ID del juego
    
    Returns:
        Turn con status IN_PROGRESS o None si no hay turno activo
    """
    return db.query(models.Turn).filter(
        models.Turn.id_game == game_id,
        models.Turn.status == models.TurnStatus.IN_PROGRESS
    ).first()


def get_cards_in_hand_by_ids(db: Session, card_ids: list, player_id: int, game_id: int):
    """
    Obtiene cartas específicas que están en la mano de un jugador.
    
    Args:
        db: Sesión de base de datos
        card_ids: Lista de IDs de CardsXGame a buscar
        player_id: ID del jugador dueño
        game_id: ID del juego
    
    Returns:
        Lista de CardsXGame que cumplen las condiciones
    """
    return db.query(models.CardsXGame).filter(
        models.CardsXGame.id.in_(card_ids),
        models.CardsXGame.id_game == game_id,
        models.CardsXGame.player_id == player_id,
        models.CardsXGame.is_in == models.CardState.HAND
    ).all()


def get_max_position_by_state(db: Session, game_id: int, state: str):
    """
    Obtiene la posición máxima de cartas en un estado específico.
    
    Args:
        db: Sesión de base de datos
        game_id: ID del juego
        state: CardState (ej: 'DETECTIVE_SET', 'DISCARD', etc)
    
    Returns:
        int: Posición máxima encontrada, o 0 si no hay cartas en ese estado
    """
    result = db.query(models.CardsXGame.position).filter(
        models.CardsXGame.id_game == game_id,
        models.CardsXGame.is_in == state
    ).order_by(models.CardsXGame.position.desc()).first()
    
    return result[0] if result else 0


def get_max_position_for_player_by_state(db: Session, game_id: int, player_id: int, state: str):
    """
    Obtiene la posición máxima de cartas de un jugador en un estado específico.
    
    Args:
        db: Sesión de base de datos
        game_id: ID del juego
        player_id: ID del jugador
        state: CardState (ej: 'DETECTIVE_SET', 'SECRET_SET', etc)
    
    Returns:
        int: Posición máxima encontrada, o 0 si no hay cartas
    """
    result = db.query(models.CardsXGame.position).filter(
        models.CardsXGame.id_game == game_id,
        models.CardsXGame.player_id == player_id,
        models.CardsXGame.is_in == state
    ).order_by(models.CardsXGame.position.desc()).first()
    
    return result[0] if result else 0


def update_cards_state(db: Session, cards: list, new_state: str, position: int, hidden: bool):
    """
    Actualiza el estado de múltiples cartas.
    
    Args:
        db: Sesión de base de datos
        cards: Lista de objetos CardsXGame a actualizar
        new_state: Nuevo CardState
        position: Nueva posición
        hidden: Nueva visibilidad
    """
    for card in cards:
        card.is_in = new_state
        card.position = position
        card.hidden = hidden
    db.commit()


def create_action(db: Session, action_data: dict):
    """
    Crea una nueva acción en ActionsPerTurn.
    
    Args:
        db: Sesión de base de datos
        action_data: Diccionario con los campos de la acción
    
    Returns:
        ActionsPerTurn creado con su ID
    """
    action = models.ActionsPerTurn(**action_data)
    db.add(action)
    db.flush()  # Para obtener el ID sin hacer commit completo
    return action


def create_card_action(db: Session, game_id: int, turn_id: int, player_id: int, 
                      action_type: str, source_pile: str, card_id: int = None,
                      position: int = None, result: str = "SUCCESS", action_name: str = None,
                      parent_action_id: int = None):
    """
    Crea una acción de carta (discard, draw, draft) en ActionsPerTurn.
    
    Args:
        db: Sesión de base de datos
        game_id: ID del juego
        turn_id: ID del turno actual
        player_id: ID del jugador que realiza la acción
        action_type: Tipo de acción (DISCARD, DRAW)
        source_pile: Pila origen/destino (DISCARD_PILE, DRAW_PILE, DRAFT_PILE)
        card_id: ID de la carta involucrada (opcional)
        position: Posición de la carta (opcional)
        result: Resultado de la acción (por defecto SUCCESS)
        action_name: Nombre de la acción (opcional, se auto-genera si no se provee)
        parent_action_id: ID de la acción padre (opcional, para acciones hijas)
    
    Returns:
        ActionsPerTurn creado
    """
    from datetime import datetime
    
    # Auto-generar action_name si no se provee
    if not action_name:
        if action_type == models.ActionType.DISCARD:
            action_name = models.ActionName.END_TURN_DISCARD
        elif action_type == models.ActionType.DRAW:
            if source_pile == models.SourcePile.DRAW_PILE:
                action_name = models.ActionName.DRAW_FROM_DECK
            elif source_pile == models.SourcePile.DRAFT_PILE:
                action_name = models.ActionName.DRAFT_PHASE
            else:
                action_name = "Draw"  # fallback genérico
        else:
            action_name = "Card Action"  # fallback genérico
    
    action_data = {
        'id_game': game_id,
        'turn_id': turn_id,
        'player_id': player_id,
        'action_time': datetime.now(),
        'action_name': action_name,
        'action_type': action_type,
        'source_pile': source_pile,
        'result': result
    }
    
    # Agregar parent_action_id si se proporciona
    if parent_action_id is not None:
        action_data['parent_action_id'] = parent_action_id
    
    # Agregar campos opcionales si se proporcionan
    if card_id:
        if action_type == models.ActionType.DISCARD:
            action_data['card_given_id'] = card_id
        elif action_type == models.ActionType.DRAW:
            action_data['card_received_id'] = card_id
    
    if position is not None:
        action_data['position_card'] = position
    
    return create_action(db, action_data)


def create_parent_card_action(db: Session, game_id: int, turn_id: int, player_id: int,
                             action_type: str, action_name: str, source_pile: str = None):
    """
    Crea una acción padre para múltiples cartas (ej: descarte múltiple, robar múltiple).
    
    Args:
        db: Sesión de base de datos
        game_id: ID del juego
        turn_id: ID del turno actual
        player_id: ID del jugador que realiza la acción
        action_type: Tipo de acción (DISCARD, DRAW)
        action_name: Nombre de la acción
        source_pile: Pila origen/destino (opcional)
    
    Returns:
        ActionsPerTurn padre creado
    """
    from datetime import datetime
    
    action_data = {
        'id_game': game_id,
        'turn_id': turn_id,
        'player_id': player_id,
        'action_time': datetime.now(),
        'action_name': action_name,
        'action_type': action_type,
        'result': models.ActionResult.SUCCESS,
        'parent_action_id': None  # Es acción padre
    }
    
    if source_pile:
        action_data['source_pile'] = source_pile
    
    return create_action(db, action_data)


def is_player_in_social_disgrace(db: Session, player_id: int, game_id: int) -> bool:
    """
    Verifica si un jugador está en desgracia social.
    Un jugador está en desgracia social cuando TODOS sus secretos están revelados (hidden=False).
    
    Args:
        db: Sesión de base de datos
        player_id: ID del jugador
        game_id: ID del juego
    
    Returns:
        True si el jugador está en desgracia social, False en caso contrario
    """
    # Obtener todos los secretos del jugador
    secrets = db.query(models.CardsXGame).filter(
        models.CardsXGame.player_id == player_id,
        models.CardsXGame.id_game == game_id,
        models.CardsXGame.is_in == models.CardState.SECRET_SET
    ).all()
    
    # Si no tiene secretos, no está en desgracia (caso edge)
    if not secrets:
        return False
    
    # Está en desgracia si TODOS los secretos están revelados (hidden=False)
    return all(not secret.hidden for secret in secrets)


def get_players_not_in_disgrace(db: Session, game_id: int, exclude_player_id: int = None):
    """
    Obtiene la lista de IDs de jugadores que NO están en desgracia social en un juego.
    Opcionalmente excluye un jugador específico (típicamente el jugador activo).
    
    Args:
        db: Sesión de base de datos
        game_id: ID del juego
        exclude_player_id: ID del jugador a excluir (opcional)
    
    Returns:
        Lista de IDs de jugadores disponibles para ser objetivo de acciones
    """
    # Obtener el juego y su room
    game = db.query(models.Game).filter(models.Game.id == game_id).first()
    if not game or not game.rooms:
        return []
    
    room = game.rooms[0]
    
    # Obtener todos los jugadores del room
    query = db.query(models.Player).filter(models.Player.id_room == room.id)
    
    # Excluir jugador si se especifica
    if exclude_player_id is not None:
        query = query.filter(models.Player.id != exclude_player_id)
    
    players = query.all()
    
    # Filtrar solo los que NO están en desgracia social
    available_players = []
    for player in players:
        if not is_player_in_social_disgrace(db, player.id, game_id):
            available_players.append(player.id)
    
    return available_players


# ------------------------------
# DETECTIVE ACTION
# ------------------------------

def get_action_by_id(db: Session, action_id: int):
    """
    Obtiene una acción por su ID.
    
    Args:
        db: Sesión de base de datos
        action_id: ID de la acción en ActionsPerTurn
    
    Returns:
        ActionsPerTurn o None si no existe
    """
    return db.query(models.ActionsPerTurn).filter(
        models.ActionsPerTurn.id == action_id
    ).first()


def update_action_result(db: Session, action_id: int, result: models.ActionResult):
    """
    Actualiza el resultado de una acción.
    
    Args:
        db: Sesión de base de datos
        action_id: ID de la acción
        result: Nuevo ActionResult (SUCCESS, FAILED, CANCELLED, etc)
    """
    action = get_action_by_id(db, action_id)
    if action:
        action.result = result
        db.flush()
    return action


def get_card_info_by_id(db: Session, card_id: int):
    """
    Obtiene información completa de una carta desde la tabla Card.
    
    Args:
        db: Sesión de base de datos
        card_id: ID de la carta en Card.id
    
    Returns:
        Card con name, img_src, etc.
    """
    return db.query(models.Card).filter(models.Card.id == card_id).first()


def update_card_visibility(db: Session, cards_x_game_id: int, hidden: bool):
    """
    Actualiza la visibilidad (hidden) de una carta en CardsXGame.
    
    Args:
        db: Sesión de base de datos
        cards_x_game_id: ID en CardsXGame.id 
        hidden: True para ocultar, False para revelar
    """
    card = db.query(models.CardsXGame).filter(
        models.CardsXGame.id == cards_x_game_id
    ).first()
    
    if card:
        card.hidden = hidden
        db.flush()
    
    return card


def get_max_position_for_player_secrets(db: Session, game_id: int, player_id: int):
    """
    Obtiene la posición máxima de secretos de un jugador específico.
    
    Args:
        db: Sesión de base de datos
        game_id: ID del juego
        player_id: ID del jugador
    
    Returns:
        int: Posición máxima encontrada, o 0 si no tiene secretos
    """
    result = db.query(models.CardsXGame.position).filter(
        models.CardsXGame.id_game == game_id,
        models.CardsXGame.player_id == player_id,
        models.CardsXGame.is_in == models.CardState.SECRET_SET
    ).order_by(models.CardsXGame.position.desc()).first()
    
    return result[0] if result else 0


def transfer_secret_card(
    db: Session,
    card_id: int,
    new_player_id: int,
    new_position: int,
    face_down: bool
):
    """
    Transfiere una carta de secreto a otro jugador.
    
    Args:
        db: Sesión de base de datos
        card_id: ID en CardsXGame.id
        new_player_id: ID del nuevo dueño
        new_position: Nueva posición en el SECRET_SET del nuevo dueño
        face_down: Si la carta se transfiere oculta (True) o revelada (False)
    """
    card = db.query(models.CardsXGame).filter(
        models.CardsXGame.id == card_id
    ).first()
    
    if card:
        card.player_id = new_player_id
        card.position = new_position
        card.hidden = face_down
        db.flush()
    
    return card