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