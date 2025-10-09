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
    room_data = {
        "name": "Mesa 1",
        "players_min": 2,
        "players_max": 4,
        "status": "WAITING"
    }
    room = crud.create_room(db, room_data)
    assert room.id is not None
    fetched = crud.get_room_by_id(db, room.id)
    assert fetched.name == "Mesa 1"
    assert fetched.players_min == 2
    assert fetched.players_max == 4
    assert fetched.status == "WAITING"

    room_data_defaults = {
        "name": "Mesa 2",
        "status": "WAITING"
    }
    room2 = crud.create_room(db, room_data_defaults)
    assert room2.players_min == 2  # valor por defecto
    assert room2.players_max == 6  # valor por defecto

def test_list_rooms(db):

    crud.create_room(db, {"name": "Mesa 1", "status": "WAITING"})
    crud.create_room(db, {"name": "Mesa 2", "status": "WAITING"})
    crud.create_room(db, {"name": "Mesa 3", "status": "INGAME"})
    waiting_rooms = crud.list_rooms(db, status="WAITING")
    assert len(waiting_rooms) == 2
    
    all_rooms = crud.list_rooms(db)
    assert len(all_rooms) == 3

def test_update_room_status(db):
    room = crud.create_room(db, {"name": "Mesa 1", "status": "WAITING"})
    updated = crud.update_room_status(db, room.id, "INGAME")
    assert updated.status == "INGAME"
    

    nonexistent = crud.update_room_status(db, 9999, "INGAME")
    assert nonexistent is None

# ------------------------------
# TESTS PLAYER
# ------------------------------
def test_create_and_get_player(db):
    room = crud.create_room(db, {"name": "Mesa 1", "players_min": 2, "players_max": 4, "status": "WAITING"})
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
    room = crud.create_room(db, {"name": "Mesa 1", "players_min": 2, "players_max": 4, "status": "WAITING"})
    crud.create_player(db, {"name": "Ana", "avatar_src": "avatar1.png", "birthdate": date(2000, 5, 10), "id_room": room.id, "is_host": True})
    crud.create_player(db, {"name": "Luis", "avatar_src": "avatar2.png", "birthdate": date(1999, 3, 1), "id_room": room.id, "is_host": False})
    players = crud.list_players_by_room(db, room.id)
    assert len(players) == 2

def test_set_player_host(db):
    room = crud.create_room(db, {"name": "Mesa 1", "players_min": 2, "players_max": 4, "status": "WAITING"})
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
    card = models.Card(
        name="Carta 1",
        description="desc",
        type="EVENT",
        img_src="img.png",
        qty=3  
    )
    db.add(card)
    db.commit()
    db.refresh(card)
    fetched = crud.get_card_by_id(db, card.id)
    assert fetched.name == "Carta 1"
    assert fetched.type == "EVENT"
    assert fetched.qty == 3

def test_check_card_qty(db):
    card = models.Card(
        name="Limited Card",
        description="desc",
        type="EVENT",
        img_src="img.png",
        qty=2
    )
    db.add(card)
    db.commit()
    db.refresh(card)
    
    # Verificar que inicialmente se puede usar
    assert crud.check_card_qty(db, card.id) is True
    
    # Usar la carta una vez
    game = crud.create_game(db, {})
    crud.assign_card_to_player(db, game.id, card.id, None, 1)
    assert crud.check_card_qty(db, card.id) is True
    
    # Usar la carta una segunda vez
    crud.assign_card_to_player(db, game.id, card.id, None, 2)
    assert crud.check_card_qty(db, card.id) is False
    
    # Verificar card_id inválido
    assert crud.check_card_qty(db, 9999) is False

def test_card_uniqueness_and_types(db):
    card_types = [
        ("Event Card", "EVENT"),
        ("Secret Card", "SECRET"),
        ("Instant Card", "INSTANT"),
        ("Detective Card", "DETECTIVE"),
        ("Devious Card", "DEVIUOS"),
        ("End Card", "END")
    ]
    cards = []
    for i, (name, type_) in enumerate(card_types):
        card = models.Card(
            name=name,
            description=f"Description for {name}",
            type=type_,
            img_src=f"img{i}.png",
            qty=1
        )
        db.add(card)
        cards.append(card)
    
    db.commit()
    for card in cards:
        db.refresh(card)
    
    ids = [card.id for card in cards]
    assert len(ids) == len(set(ids))  
    
    for card in cards:
        fetched = crud.get_card_by_id(db, card.id)
        assert fetched is not None
        assert fetched.name == card.name
        assert fetched.type == card.type

# ------------------------------
# TESTS CARDSXGAME
# ------------------------------
def test_assign_card_to_player(db):
    game = crud.create_game(db, {})
    card = models.Card(name="Carta 1", description="desc", type="EVENT", img_src="img.png", qty=1)
    db.add(card)
    db.commit()
    db.refresh(card)
    player = models.Player(name="Ana", avatar_src="avatar1.png", birthdate=date(2000, 5, 10), id_room=None, is_host=True)
    db.add(player)
    db.commit()
    db.refresh(player)
    
    entry = crud.assign_card_to_player(db, game.id, card.id, player.id, 1)
    assert entry.id is not None
    assert entry.hidden is True  
    
    card2 = models.Card(name="Carta 2", description="desc", type="EVENT", img_src="img.png", qty=1)
    db.add(card2)
    db.commit()
    entry2 = crud.assign_card_to_player(db, game.id, card2.id, player.id, 2, hidden=False)
    assert entry2.hidden is False

def test_move_card_states(db):
    game = crud.create_game(db, {})
    card = models.Card(name="Carta 1", description="desc", type="EVENT", img_src="img.png", qty=1)
    db.add(card)
    db.commit()
    db.refresh(card)
    entry = models.CardsXGame(id_game=game.id, id_card=card.id, is_in="HAND", position=1, hidden=True)
    db.add(entry)
    db.commit()
    
    moved_draft = crud.move_card(db, card.id, game.id, "DRAFT", 1)
    assert moved_draft.is_in == "DRAFT"
    assert moved_draft.hidden is False
    
    moved_discard_top = crud.move_card(db, card.id, game.id, "DISCARD", 1)
    assert moved_discard_top.hidden is False
    
    moved_discard_second = crud.move_card(db, card.id, game.id, "DISCARD", 2)
    assert moved_discard_second.hidden is True
    
    moved_deck = crud.move_card(db, card.id, game.id, "DECK", 1)
    assert moved_deck.hidden is True

def test_list_cards_by_player_and_game(db):
    game = crud.create_game(db, {})
    card1 = models.Card(name="Carta 1", description="desc", type="EVENT", img_src="img.png", qty=2)
    card2 = models.Card(name="Carta 2", description="desc", type="SECRET", img_src="img2.png", qty=1)
    db.add_all([card1, card2])
    db.commit()

    player = models.Player(name="Ana", avatar_src="avatar1.png", birthdate=date(2000, 5, 10), id_room=None, is_host=True)
    db.add(player)
    db.commit()
    db.refresh(player)
    
    crud.assign_card_to_player(db, game.id, card1.id, player.id, 1)
    crud.assign_card_to_player(db, game.id, card2.id, player.id, 2)
    
    player_cards = crud.list_cards_by_player(db, player.id, game.id)
    assert len(player_cards) == 2
    assert all(card.player_id == player.id for card in player_cards)
    
    all_cards = crud.list_cards_by_game(db, game.id)
    assert len(all_cards) == 2
    
    crud.move_card(db, card1.id, game.id, "DECK", 1)
    deck_cards = db.query(models.CardsXGame).filter(
        models.CardsXGame.id_game == game.id,
        models.CardsXGame.is_in == "DECK"
    ).all()
    assert len(deck_cards) == 1

# ------------------------------
# HELPERS DECK/DISCARD/DRAFT
# ------------------------------
def test_get_top_card_by_state_and_count(db):
    game = crud.create_game(db, {})
    
    cards = [
        models.Card(name=f"Carta {i}", description=f"desc {i}", 
                   type="EVENT", img_src=f"img{i}.png", qty=1)
        for i in range(1, 6)
    ]
    db.add_all(cards)
    db.commit()
    for card in cards:
        db.refresh(card)
    
    # Test DECK
    deck_entries = [
        models.CardsXGame(id_game=game.id, id_card=cards[0].id, is_in="DECK", position=1, hidden=True),
        models.CardsXGame(id_game=game.id, id_card=cards[1].id, is_in="DECK", position=2, hidden=True)
    ]
    db.add_all(deck_entries)
    
    # Test DISCARD
    discard_entries = [
        models.CardsXGame(id_game=game.id, id_card=cards[2].id, is_in="DISCARD", position=1, hidden=False),
        models.CardsXGame(id_game=game.id, id_card=cards[3].id, is_in="DISCARD", position=2, hidden=True)
    ]
    db.add_all(discard_entries)
    
    # Test DRAFT
    draft_entry = models.CardsXGame(id_game=game.id, id_card=cards[4].id, is_in="DRAFT", position=1, hidden=False)
    db.add(draft_entry)
    
    db.commit()
    
    # Verificar DECK
    top_deck = crud.get_top_card_by_state(db, game.id, "DECK")
    assert top_deck.id_card == cards[1].id
    assert top_deck.hidden is True
    deck_count = crud.count_cards_by_state(db, game.id, "DECK")
    assert deck_count == 2
    
    # Verificar DISCARD
    top_discard = crud.get_top_card_by_state(db, game.id, "DISCARD")
    assert top_discard.id_card == cards[3].id
    assert top_discard.position == 2
    discard_count = crud.count_cards_by_state(db, game.id, "DISCARD")
    assert discard_count == 2
    
    # Verificar DRAFT
    top_draft = crud.get_top_card_by_state(db, game.id, "DRAFT")
    assert top_draft.id_card == cards[4].id
    assert top_draft.hidden is False
    draft_count = crud.count_cards_by_state(db, game.id, "DRAFT")
    assert draft_count == 1
    
    # Verificar estado inexistente
    nonexistent = crud.get_top_card_by_state(db, game.id, "NONEXISTENT")
    assert nonexistent is None
    nonexistent_count = crud.count_cards_by_state(db, game.id, "NONEXISTENT")
    assert nonexistent_count == 0