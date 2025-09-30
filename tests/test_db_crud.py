import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db import models, crud
from app.db.database import Base
from datetime import date

# Configuración de BD en memoria para tests
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="function")
def db():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    yield db
    db.close()
    Base.metadata.drop_all(bind=engine)

# ------------------------------
# TESTS ROOM
# ------------------------------
def test_create_and_get_room(db):
    room_data = {"name": "Mesa 1", "player_qty": 4, "status": "WAITING"}
    room = crud.create_room(db, room_data)
    assert room.id is not None
    fetched = crud.get_room_by_id(db, room.id)
    assert fetched.name == "Mesa 1"
    assert fetched.player_qty == 4
    assert fetched.status == "WAITING"

def test_list_rooms(db):
    crud.create_room(db, {"name": "Mesa 1", "player_qty": 4, "status": "WAITING"})
    crud.create_room(db, {"name": "Mesa 2", "player_qty": 3, "status": "WAITING"})
    rooms = crud.list_rooms(db, status="WAITING")
    assert len(rooms) == 2

def test_update_room_status(db):
    room = crud.create_room(db, {"name": "Mesa 1", "player_qty": 4, "status": "WAITING"})
    updated = crud.update_room_status(db, room.id, "INGAME")
    assert updated.status == "INGAME"

# ------------------------------
# TESTS PLAYER
# ------------------------------
def test_create_and_get_player(db):
    room = crud.create_room(db, {"name": "Mesa 1", "player_qty": 4, "status": "WAITING"})
    player_data = {
        "name": "Ana",
        "avatar_src": "avatar1.png",
        "birthdate": date(2000, 5, 10),
        "id_room": room.id,
        "is_host": True
    }
    player = crud.create_player(db, player_data)
    assert player.id is not None
    fetched = crud.get_player_by_id(db, player.id)
    assert fetched.name == "Ana"
    assert fetched.is_host

def test_list_players_by_room(db):
    room = crud.create_room(db, {"name": "Mesa 1", "player_qty": 4, "status": "WAITING"})
    crud.create_player(db, {"name": "Ana", "avatar_src": "avatar1.png", "birthdate": date(2000, 5, 10), "id_room": room.id, "is_host": True})
    crud.create_player(db, {"name": "Luis", "avatar_src": "avatar2.png", "birthdate": date(1999, 3, 1), "id_room": room.id, "is_host": False})
    players = crud.list_players_by_room(db, room.id)
    assert len(players) == 2

def test_set_player_host(db):
    room = crud.create_room(db, {"name": "Mesa 1", "player_qty": 4, "status": "WAITING"})
    player = crud.create_player(db, {"name": "Ana", "avatar_src": "avatar1.png", "birthdate": date(2000, 5, 10), "id_room": room.id, "is_host": False})
    updated = crud.set_player_host(db, player.id)
    assert updated.is_host

# ------------------------------
# TESTS GAME
# ------------------------------
def test_create_and_get_game(db):
    game = crud.create_game(db, {})
    assert game.id is not None
    fetched = crud.get_game_by_id(db, game.id)
    assert fetched.id == game.id

def test_update_player_turn(db):
    game = crud.create_game(db, {})
    updated = crud.update_player_turn(db, game.id, 42)
    assert updated.player_turn_id == 42

# ------------------------------
# TESTS CARD
# ------------------------------
def test_create_and_get_card(db):
    card = models.Card(name="Carta 1", description="desc", type="EVENT", img_src="img.png")
    db.add(card)
    db.commit()
    db.refresh(card)
    fetched = crud.get_card_by_id(db, card.id)
    assert fetched.name == "Carta 1"
    assert fetched.type == "EVENT"

def test_card_uniqueness(db):
    card1 = models.Card(name="Carta 1", description="desc", type="EVENT", img_src="img.png")
    db.add(card1)
    db.commit()
    db.refresh(card1)
    card2 = models.Card(name="Carta 2", description="desc", type="SECRET", img_src="img2.png")
    db.add(card2)
    db.commit()
    db.refresh(card2)
    assert card1.id != card2.id

# ------------------------------
# TESTS CARDSXGAME
# ------------------------------
def test_assign_and_move_card(db):
    game = crud.create_game(db, {})
    card = models.Card(name="Carta 1", description="desc", type="EVENT", img_src="img.png")
    db.add(card)
    db.commit()
    db.refresh(card)
    player = models.Player(name="Ana", avatar_src="avatar1.png", birthdate=date(2000, 5, 10), id_room=None, is_host=True)
    db.add(player)
    db.commit()
    db.refresh(player)
    entry = crud.assign_card_to_player(db, game.id, card.id, player.id, 1)
    assert entry.id is not None
    moved = crud.move_card(db, card.id, game.id, "DISCARD", 2, player.id)
    assert moved.is_in == "DISCARD"
    assert moved.position == 2

def test_list_cards_by_player_and_game(db):
    game = crud.create_game(db, {})
    card1 = models.Card(name="Carta 1", description="desc", type="EVENT", img_src="img.png")
    card2 = models.Card(name="Carta 2", description="desc", type="SECRET", img_src="img2.png")
    db.add_all([card1, card2])
    db.commit()
    db.refresh(card1)
    db.refresh(card2)
    player = models.Player(name="Ana", avatar_src="avatar1.png", birthdate=date(2000, 5, 10), id_room=None, is_host=True)
    db.add(player)
    db.commit()
    db.refresh(player)
    crud.assign_card_to_player(db, game.id, card1.id, player.id, 1)
    crud.assign_card_to_player(db, game.id, card2.id, player.id, 2)
    cards = crud.list_cards_by_player(db, player.id, game.id)
    assert len(cards) == 2
    all_cards = crud.list_cards_by_game(db, game.id)
    assert len(all_cards) == 2

# ------------------------------
# HELPERS DECK/DISCARD
# ------------------------------
def test_get_top_card_by_state_and_count(db):
    game = crud.create_game(db, {})
    card1 = models.Card(name="Carta 1", description="desc", type="EVENT", img_src="img.png")
    card2 = models.Card(name="Carta 2", description="desc", type="SECRET", img_src="img2.png")
    db.add_all([card1, card2])
    db.commit()
    db.refresh(card1)
    db.refresh(card2)
    entry1 = models.CardsXGame(id_game=game.id, id_card=card1.id, is_in="DECK", position=1)
    entry2 = models.CardsXGame(id_game=game.id, id_card=card2.id, is_in="DECK", position=2)
    db.add_all([entry1, entry2])
    db.commit()
    top = crud.get_top_card_by_state(db, game.id, "DECK")
    assert top.id_card == card2.id
    count = crud.count_cards_by_state(db, game.id, "DECK")
    assert count == 2
    # Cambiar uno a DISCARD y probar 
    entry2.is_in = "DISCARD"
    db.commit()
    top_discard = crud.get_top_card_by_state(db, game.id, "DISCARD")
    assert top_discard.id_card == card2.id
    count_discard = crud.count_cards_by_state(db, game.id, "DISCARD")
    assert count_discard == 1