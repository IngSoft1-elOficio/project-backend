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

# ------------------------------
# TESTS PLAY DETECTIVE SET
# ------------------------------
def test_get_active_turn_for_player(db):
    """Test obtener turno activo de un jugador"""
    game = crud.create_game(db, {})
    room = crud.create_room(db, {"name": "Mesa 1", "status": "INGAME", "id_game": game.id})
    player = crud.create_player(db, {
        "name": "Ana",
        "avatar_src": "avatar1.png",
        "birthdate": date(2000, 5, 10),
        "id_room": room.id,
        "is_host": True
    })
    
    # Crear un turno IN_PROGRESS
    turn = models.Turn(
        number=1,
        id_game=game.id,
        player_id=player.id,
        status=models.TurnStatus.IN_PROGRESS
    )
    db.add(turn)
    db.commit()
    db.refresh(turn)
    
    # Obtener turno activo
    active_turn = crud.get_active_turn_for_player(db, game.id, player.id)
    assert active_turn is not None
    assert active_turn.id == turn.id
    assert active_turn.status == models.TurnStatus.IN_PROGRESS
    
    # Verificar que no encuentra turno de otro jugador
    other_turn = crud.get_active_turn_for_player(db, game.id, 9999)
    assert other_turn is None
    
    # Verificar que no encuentra turno FINISHED
    turn.status = models.TurnStatus.FINISHED
    db.commit()
    finished_turn = crud.get_active_turn_for_player(db, game.id, player.id)
    assert finished_turn is None


def test_get_cards_in_hand_by_ids(db):
    """Test obtener cartas específicas de la mano de un jugador"""
    game = crud.create_game(db, {})
    room = crud.create_room(db, {"name": "Mesa 1", "status": "INGAME", "id_game": game.id})
    player = crud.create_player(db, {
        "name": "Ana",
        "avatar_src": "avatar1.png",
        "birthdate": date(2000, 5, 10),
        "id_room": room.id,
        "is_host": True
    })
    
    # Crear cartas
    cards = [
        models.Card(name=f"Carta {i}", description="desc", type="DETECTIVE", img_src=f"img{i}.png", qty=1)
        for i in range(1, 5)
    ]
    db.add_all(cards)
    db.commit()
    
    # Asignar 3 cartas a la mano del jugador
    card_entries = []
    for i, card in enumerate(cards[:3]):
        db.refresh(card)
        entry = models.CardsXGame(
            id_game=game.id,
            id_card=card.id,
            is_in=models.CardState.HAND,
            position=i+1,
            player_id=player.id,
            hidden=True
        )
        db.add(entry)
        card_entries.append(entry)
    
    db.commit()
    for entry in card_entries:
        db.refresh(entry)
    
    # Obtener cartas específicas
    card_ids = [card_entries[0].id, card_entries[1].id, card_entries[2].id]
    fetched_cards = crud.get_cards_in_hand_by_ids(db, card_ids, player.id, game.id)
    
    assert len(fetched_cards) == 3
    assert all(card.is_in == models.CardState.HAND for card in fetched_cards)
    assert all(card.player_id == player.id for card in fetched_cards)
    
    # Verificar que no encuentra cartas de otro estado
    card_entries[0].is_in = models.CardState.DISCARD
    db.commit()
    fetched_cards_2 = crud.get_cards_in_hand_by_ids(db, card_ids, player.id, game.id)
    assert len(fetched_cards_2) == 2  # Solo 2 porque una está en DISCARD


def test_get_max_position_by_state(db):
    """Test obtener posición máxima para un estado"""
    game = crud.create_game(db, {})
    
    # Sin cartas, debe retornar 0
    max_pos = crud.get_max_position_by_state(db, game.id, models.CardState.DETECTIVE_SET)
    assert max_pos == 0
    
    # Crear cartas en DETECTIVE_SET con diferentes posiciones
    card1 = models.Card(name="Carta 1", description="desc", type="DETECTIVE", img_src="img1.png", qty=1)
    card2 = models.Card(name="Carta 2", description="desc", type="DETECTIVE", img_src="img2.png", qty=1)
    card3 = models.Card(name="Carta 3", description="desc", type="DETECTIVE", img_src="img3.png", qty=1)
    db.add_all([card1, card2, card3])
    db.commit()
    
    entry1 = models.CardsXGame(id_game=game.id, id_card=card1.id, is_in=models.CardState.DETECTIVE_SET, position=1, hidden=False)
    entry2 = models.CardsXGame(id_game=game.id, id_card=card2.id, is_in=models.CardState.DETECTIVE_SET, position=1, hidden=False)
    entry3 = models.CardsXGame(id_game=game.id, id_card=card3.id, is_in=models.CardState.DETECTIVE_SET, position=3, hidden=False)
    db.add_all([entry1, entry2, entry3])
    db.commit()
    
    # La posición máxima debe ser 3
    max_pos = crud.get_max_position_by_state(db, game.id, models.CardState.DETECTIVE_SET)
    assert max_pos == 3
    
    # Verificar otro estado
    max_pos_hand = crud.get_max_position_by_state(db, game.id, models.CardState.HAND)
    assert max_pos_hand == 0


def test_get_max_position_for_player_by_state(db):
    """Test obtener posición máxima para un jugador y estado específico"""
    game = crud.create_game(db, {})
    room = crud.create_room(db, {"name": "Mesa 1", "status": "INGAME", "id_game": game.id})
    player1 = crud.create_player(db, {
        "name": "Player 1",
        "avatar_src": "avatar1.png",
        "birthdate": date(2000, 1, 1),
        "id_room": room.id,
        "is_host": True
    })
    player2 = crud.create_player(db, {
        "name": "Player 2",
        "avatar_src": "avatar2.png",
        "birthdate": date(2000, 2, 2),
        "id_room": room.id,
        "is_host": False
    })
    
    # Sin cartas, debe retornar 0
    max_pos = crud.get_max_position_for_player_by_state(
        db, game.id, player1.id, models.CardState.DETECTIVE_SET
    )
    assert max_pos == 0
    
    # Crear cartas
    card1 = models.Card(name="Carta 1", description="desc", type="DETECTIVE", img_src="img1.png", qty=1)
    card2 = models.Card(name="Carta 2", description="desc", type="DETECTIVE", img_src="img2.png", qty=1)
    card3 = models.Card(name="Carta 3", description="desc", type="DETECTIVE", img_src="img3.png", qty=1)
    card4 = models.Card(name="Carta 4", description="desc", type="DETECTIVE", img_src="img4.png", qty=1)
    db.add_all([card1, card2, card3, card4])
    db.commit()
    
    # Player 1 tiene 2 sets: position 1 y 2
    entry1 = models.CardsXGame(id_game=game.id, id_card=card1.id, player_id=player1.id, 
                               is_in=models.CardState.DETECTIVE_SET, position=1, hidden=False)
    entry2 = models.CardsXGame(id_game=game.id, id_card=card2.id, player_id=player1.id, 
                               is_in=models.CardState.DETECTIVE_SET, position=2, hidden=False)
    # Player 2 tiene 1 set: position 1
    entry3 = models.CardsXGame(id_game=game.id, id_card=card3.id, player_id=player2.id, 
                               is_in=models.CardState.DETECTIVE_SET, position=1, hidden=False)
    entry4 = models.CardsXGame(id_game=game.id, id_card=card4.id, player_id=player2.id, 
                               is_in=models.CardState.DETECTIVE_SET, position=1, hidden=False)
    db.add_all([entry1, entry2, entry3, entry4])
    db.commit()
    
    # Player 1 debe tener max position = 2
    max_pos_p1 = crud.get_max_position_for_player_by_state(
        db, game.id, player1.id, models.CardState.DETECTIVE_SET
    )
    assert max_pos_p1 == 2
    
    # Player 2 debe tener max position = 1 (no 2!)
    max_pos_p2 = crud.get_max_position_for_player_by_state(
        db, game.id, player2.id, models.CardState.DETECTIVE_SET
    )
    assert max_pos_p2 == 1


def test_update_cards_state(db):
    """Test actualizar estado de múltiples cartas"""
    game = crud.create_game(db, {})
    room = crud.create_room(db, {"name": "Mesa 1", "status": "INGAME", "id_game": game.id})
    player = crud.create_player(db, {
        "name": "Ana",
        "avatar_src": "avatar1.png",
        "birthdate": date(2000, 5, 10),
        "id_room": room.id,
        "is_host": True
    })
    
    # Crear cartas en HAND
    cards = [
        models.Card(name=f"Carta {i}", description="desc", type="DETECTIVE", img_src=f"img{i}.png", qty=1)
        for i in range(1, 4)
    ]
    db.add_all(cards)
    db.commit()
    
    card_entries = []
    for i, card in enumerate(cards):
        db.refresh(card)
        entry = models.CardsXGame(
            id_game=game.id,
            id_card=card.id,
            is_in=models.CardState.HAND,
            position=i+1,
            player_id=player.id,
            hidden=True
        )
        db.add(entry)
        card_entries.append(entry)
    
    db.commit()
    for entry in card_entries:
        db.refresh(entry)
    
    # Actualizar todas las cartas a DETECTIVE_SET
    crud.update_cards_state(db, card_entries, models.CardState.DETECTIVE_SET, position=1, hidden=False)
    
    # Verificar cambios
    for entry in card_entries:
        db.refresh(entry)
        assert entry.is_in == models.CardState.DETECTIVE_SET
        assert entry.position == 1
        assert entry.hidden is False


def test_create_action(db):
    """Test crear acción en ActionsPerTurn"""
    game = crud.create_game(db, {})
    room = crud.create_room(db, {"name": "Mesa 1", "status": "INGAME", "id_game": game.id})
    player = crud.create_player(db, {
        "name": "Ana",
        "avatar_src": "avatar1.png",
        "birthdate": date(2000, 5, 10),
        "id_room": room.id,
        "is_host": True
    })
    
    turn = models.Turn(
        number=1,
        id_game=game.id,
        player_id=player.id,
        status=models.TurnStatus.IN_PROGRESS
    )
    db.add(turn)
    db.commit()
    db.refresh(turn)
    
    action_data = {
        "id_game": game.id,
        "turn_id": turn.id,
        "player_id": player.id,
        "action_name": "play_Marple_set",
        "action_type": models.ActionType.DETECTIVE_SET,
        "result": models.ActionResult.PENDING
    }
    
    action = crud.create_action(db, action_data)
    
    # Verificar que se creó con ID
    assert action.id is not None
    assert action.action_name == "play_Marple_set"
    assert action.action_type == models.ActionType.DETECTIVE_SET
    assert action.result == models.ActionResult.PENDING
    
    # Verificar que se puede hacer commit después
    db.commit()
    db.refresh(action)
    assert action.id is not None


def test_is_player_in_social_disgrace(db):
    """Test verificar si jugador está en desgracia social"""
    game = crud.create_game(db, {})
    room = crud.create_room(db, {"name": "Mesa 1", "status": "INGAME", "id_game": game.id})
    player = crud.create_player(db, {
        "name": "Ana",
        "avatar_src": "avatar1.png",
        "birthdate": date(2000, 5, 10),
        "id_room": room.id,
        "is_host": True
    })
    
    # Crear secretos
    secrets = [
        models.Card(name=f"Secret {i}", description="desc", type="SECRET", img_src=f"img{i}.png", qty=1)
        for i in range(1, 4)
    ]
    db.add_all(secrets)
    db.commit()
    
    # Caso 1: Jugador sin secretos (no está en desgracia)
    assert crud.is_player_in_social_disgrace(db, player.id, game.id) is False
    
    # Caso 2: Jugador con secretos ocultos (no está en desgracia)
    secret_entries = []
    for i, secret in enumerate(secrets):
        db.refresh(secret)
        entry = models.CardsXGame(
            id_game=game.id,
            id_card=secret.id,
            is_in=models.CardState.SECRET_SET,
            position=i+1,
            player_id=player.id,
            hidden=True  # Todos ocultos
        )
        db.add(entry)
        secret_entries.append(entry)
    
    db.commit()
    assert crud.is_player_in_social_disgrace(db, player.id, game.id) is False
    
    # Caso 3: Jugador con algunos secretos revelados (no está en desgracia)
    secret_entries[0].hidden = False
    secret_entries[1].hidden = False
    db.commit()
    assert crud.is_player_in_social_disgrace(db, player.id, game.id) is False
    
    # Caso 4: Jugador con TODOS los secretos revelados (SÍ está en desgracia)
    secret_entries[2].hidden = False
    db.commit()
    assert crud.is_player_in_social_disgrace(db, player.id, game.id) is True


def test_get_players_not_in_disgrace(db):
    """Test obtener jugadores no en desgracia social"""
    game = crud.create_game(db, {})
    room = crud.create_room(db, {"name": "Mesa 1", "status": "INGAME", "id_game": game.id})
    
    # Crear 3 jugadores
    player1 = crud.create_player(db, {
        "name": "Ana",
        "avatar_src": "avatar1.png",
        "birthdate": date(2000, 5, 10),
        "id_room": room.id,
        "is_host": True
    })
    player2 = crud.create_player(db, {
        "name": "Luis",
        "avatar_src": "avatar2.png",
        "birthdate": date(1999, 3, 1),
        "id_room": room.id,
        "is_host": False
    })
    player3 = crud.create_player(db, {
        "name": "Maria",
        "avatar_src": "avatar3.png",
        "birthdate": date(2001, 7, 15),
        "id_room": room.id,
        "is_host": False
    })
    
    # Crear secretos para cada jugador
    secrets = [
        models.Card(name=f"Secret {i}", description="desc", type="SECRET", img_src=f"img{i}.png", qty=1)
        for i in range(1, 10)
    ]
    db.add_all(secrets)
    db.commit()
    
    # Player1: 3 secretos ocultos (NO en desgracia)
    for i in range(3):
        db.refresh(secrets[i])
        entry = models.CardsXGame(
            id_game=game.id,
            id_card=secrets[i].id,
            is_in=models.CardState.SECRET_SET,
            position=i+1,
            player_id=player1.id,
            hidden=True
        )
        db.add(entry)
    
    # Player2: 3 secretos revelados (SÍ en desgracia)
    for i in range(3, 6):
        db.refresh(secrets[i])
        entry = models.CardsXGame(
            id_game=game.id,
            id_card=secrets[i].id,
            is_in=models.CardState.SECRET_SET,
            position=i-2,
            player_id=player2.id,
            hidden=False  # Todos revelados
        )
        db.add(entry)
    
    # Player3: 2 ocultos, 1 revelado (NO en desgracia)
    for i in range(6, 9):
        db.refresh(secrets[i])
        entry = models.CardsXGame(
            id_game=game.id,
            id_card=secrets[i].id,
            is_in=models.CardState.SECRET_SET,
            position=i-5,
            player_id=player3.id,
            hidden=(i < 8)  # Primeros 2 ocultos, último revelado
        )
        db.add(entry)
    
    db.commit()
    
    # Caso 1: Sin excluir a nadie
    available_players = crud.get_players_not_in_disgrace(db, game.id)
    assert len(available_players) == 2
    assert player1.id in available_players
    assert player3.id in available_players
    assert player2.id not in available_players  # Está en desgracia
    
    # Caso 2: Excluyendo a player1 (el activo)
    available_players_2 = crud.get_players_not_in_disgrace(db, game.id, exclude_player_id=player1.id)
    assert len(available_players_2) == 1
    assert player3.id in available_players_2
    assert player1.id not in available_players_2  # Excluido
    assert player2.id not in available_players_2  # En desgracia
    
    # Caso 3: Juego sin rooms
    game_no_room = crud.create_game(db, {})
    empty_list = crud.get_players_not_in_disgrace(db, game_no_room.id)
    assert empty_list == []


# ------------------------------
# TESTS TURN AND ACTIONS
# ------------------------------

def test_get_current_turn(db):
    """Test para obtener el turno actual de un juego."""
    # Crear sala, jugador y juego
    room_data = {"name": "Test Room", "status": "INGAME"}
    room = crud.create_room(db, room_data)
    
    player_data = {"name": "Player1", "avatar_src": "avatar1.png", "birthdate": date(2000, 1, 1), "id_room": room.id, "order": 1}
    player = crud.create_player(db, player_data)
    
    game_data = {"id": 10, "player_turn_id": player.id}
    game = crud.create_game(db, game_data)
    
    # Crear turno activo
    turn = models.Turn(
        number=1,
        id_game=game.id,
        player_id=player.id,
        status=models.TurnStatus.IN_PROGRESS
    )
    db.add(turn)
    db.commit()
    
    # Test: obtener turno actual
    current_turn = crud.get_current_turn(db, game.id)
    assert current_turn is not None
    assert current_turn.id == turn.id
    assert current_turn.status == models.TurnStatus.IN_PROGRESS
    
    # Test: no hay turno activo
    turn.status = models.TurnStatus.FINISHED
    db.commit()
    no_turn = crud.get_current_turn(db, game.id)
    assert no_turn is None


def test_create_card_action(db):
    """Test para crear acciones de cartas con la función helper."""
    from datetime import datetime
    
    # Crear sala, jugador y juego
    room_data = {"name": "Test Room", "status": "INGAME"}
    room = crud.create_room(db, room_data)
    
    player_data = {"name": "Player1", "avatar_src": "avatar1.png", "birthdate": date(2000, 1, 1), "id_room": room.id, "order": 1}
    player = crud.create_player(db, player_data)
    
    game_data = {"id": 10, "player_turn_id": player.id}
    game = crud.create_game(db, game_data)
    
    # Crear turno
    turn = models.Turn(
        number=1,
        id_game=game.id,
        player_id=player.id,
        status=models.TurnStatus.IN_PROGRESS
    )
    db.add(turn)
    db.commit()
    
    # Crear carta para testing
    card = models.Card(id=1, name="Test Card", description="Test description", type="event", img_src="test.png", qty=1)
    db.add(card)
    cards_x_game = models.CardsXGame(
        id=1,
        id_game=game.id,
        id_card=card.id,
        player_id=player.id,
        is_in=models.CardState.HAND,
        position=0
    )
    db.add(cards_x_game)
    db.commit()
    
    # Test: acción de descarte
    discard_action = crud.create_card_action(
        db=db,
        game_id=game.id,
        turn_id=turn.id,
        player_id=player.id,
        action_type=models.ActionType.DISCARD,
        source_pile=models.SourcePile.DISCARD_PILE,
        card_id=cards_x_game.id,
        position=0
    )
    
    assert discard_action.id_game == game.id
    assert discard_action.turn_id == turn.id
    assert discard_action.player_id == player.id
    assert discard_action.action_name == models.ActionName.END_TURN_DISCARD
    assert discard_action.action_type == models.ActionType.DISCARD
    assert discard_action.source_pile == models.SourcePile.DISCARD_PILE
    assert discard_action.card_given_id == cards_x_game.id
    assert discard_action.position_card == 0
    assert discard_action.result == models.ActionResult.SUCCESS
    
    # Test: acción de robar
    draw_action = crud.create_card_action(
        db=db,
        game_id=game.id,
        turn_id=turn.id,
        player_id=player.id,
        action_type=models.ActionType.DRAW,
        source_pile=models.SourcePile.DRAW_PILE,
        card_id=cards_x_game.id
    )
    
    assert draw_action.action_name == models.ActionName.DRAW_FROM_DECK
    assert draw_action.action_type == models.ActionType.DRAW
    assert draw_action.source_pile == models.SourcePile.DRAW_PILE
    assert draw_action.card_received_id == cards_x_game.id
    assert draw_action.position_card is None
    
    # Test: acción de draft
    draft_action = crud.create_card_action(
        db=db,
        game_id=game.id,
        turn_id=turn.id,
        player_id=player.id,
        action_type=models.ActionType.DRAW,
        source_pile=models.SourcePile.DRAFT_PILE,
        card_id=cards_x_game.id
    )
    
    assert draft_action.action_name == models.ActionName.DRAFT_PHASE
    assert draft_action.action_type == models.ActionType.DRAW
    assert draft_action.source_pile == models.SourcePile.DRAFT_PILE
    
    db.commit()
    
    # Verificar que se crearon 3 acciones
    actions = db.query(models.ActionsPerTurn).filter(
        models.ActionsPerTurn.id_game == game.id
    ).all()
    assert len(actions) == 3


# ------------------------------
# TESTS DETECTIVE ACTION
# ------------------------------
def test_get_action_by_id(db):
    """Test obtener acción por ID"""
    game = crud.create_game(db, {})
    room = crud.create_room(db, {"name": "Mesa 1", "status": "INGAME", "id_game": game.id})
    player = crud.create_player(db, {
        "name": "Ana",
        "avatar_src": "avatar1.png",
        "birthdate": date(2000, 5, 10),
        "id_room": room.id,
        "is_host": True
    })
    
    turn = models.Turn(
        number=1,
        id_game=game.id,
        player_id=player.id,
        status=models.TurnStatus.IN_PROGRESS
    )
    db.add(turn)
    db.commit()
    db.refresh(turn)
    
    # Crear acción
    action_data = {
        "id_game": game.id,
        "turn_id": turn.id,
        "player_id": player.id,
        "action_name": "play_Poirot_set",
        "action_type": models.ActionType.DETECTIVE_SET,
        "result": models.ActionResult.PENDING
    }
    action = crud.create_action(db, action_data)
    db.commit()
    db.refresh(action)
    
    # Obtener por ID
    fetched_action = crud.get_action_by_id(db, action.id)
    assert fetched_action is not None
    assert fetched_action.id == action.id
    assert fetched_action.action_name == "play_Poirot_set"
    assert fetched_action.result == models.ActionResult.PENDING
    
    # Acción inexistente
    nonexistent = crud.get_action_by_id(db, 9999)
    assert nonexistent is None


def test_update_action_result(db):
    """Test actualizar resultado de una acción"""
    game = crud.create_game(db, {})
    room = crud.create_room(db, {"name": "Mesa 1", "status": "INGAME", "id_game": game.id})
    player = crud.create_player(db, {
        "name": "Ana",
        "avatar_src": "avatar1.png",
        "birthdate": date(2000, 5, 10),
        "id_room": room.id,
        "is_host": True
    })
    
    turn = models.Turn(
        number=1,
        id_game=game.id,
        player_id=player.id,
        status=models.TurnStatus.IN_PROGRESS
    )
    db.add(turn)
    db.commit()
    db.refresh(turn)
    
    # Crear acción PENDING
    action_data = {
        "id_game": game.id,
        "turn_id": turn.id,
        "player_id": player.id,
        "action_name": "play_Marple_set",
        "action_type": models.ActionType.DETECTIVE_SET,
        "result": models.ActionResult.PENDING
    }
    action = crud.create_action(db, action_data)
    db.commit()
    db.refresh(action)
    
    assert action.result == models.ActionResult.PENDING
    
    # Actualizar a SUCCESS
    updated_action = crud.update_action_result(db, action.id, models.ActionResult.SUCCESS)
    db.commit()
    db.refresh(updated_action)
    
    assert updated_action.result == models.ActionResult.SUCCESS
    
    # Actualizar a FAILED
    updated_action_2 = crud.update_action_result(db, action.id, models.ActionResult.FAILED)
    db.commit()
    db.refresh(updated_action_2)
    
    assert updated_action_2.result == models.ActionResult.FAILED
    
    # Acción inexistente
    nonexistent = crud.update_action_result(db, 9999, models.ActionResult.SUCCESS)
    assert nonexistent is None


def test_get_card_info_by_id(db):
    """Test obtener información completa de una carta"""
    # Crear carta
    card = models.Card(
        name="Hercule Poirot",
        description="The famous detective",
        type="DETECTIVE",
        img_src="/assets/cards/poirot.png",
        qty=3
    )
    db.add(card)
    db.commit()
    db.refresh(card)
    
    # Obtener info de la carta
    card_info = crud.get_card_info_by_id(db, card.id)
    
    assert card_info is not None
    assert card_info.id == card.id
    assert card_info.name == "Hercule Poirot"
    assert card_info.img_src == "/assets/cards/poirot.png"
    assert card_info.type == "DETECTIVE"
    assert card_info.qty == 3
    
    # Carta inexistente
    nonexistent = crud.get_card_info_by_id(db, 9999)
    assert nonexistent is None


def test_update_card_visibility(db):
    """Test actualizar visibilidad de una carta en CardsXGame"""
    game = crud.create_game(db, {})
    room = crud.create_room(db, {"name": "Mesa 1", "status": "INGAME", "id_game": game.id})
    player = crud.create_player(db, {
        "name": "Ana",
        "avatar_src": "avatar1.png",
        "birthdate": date(2000, 5, 10),
        "id_room": room.id,
        "is_host": True
    })
    
    # Crear carta secreta oculta
    secret_card = models.Card(
        name="You are the Murderer!!",
        description="Secret card",
        type="SECRET",
        img_src="/assets/cards/murderer.png",
        qty=1
    )
    db.add(secret_card)
    db.commit()
    db.refresh(secret_card)
    
    secret_entry = models.CardsXGame(
        id_game=game.id,
        id_card=secret_card.id,
        is_in=models.CardState.SECRET_SET,
        position=1,
        player_id=player.id,
        hidden=True  # Oculto inicialmente
    )
    db.add(secret_entry)
    db.commit()
    db.refresh(secret_entry)
    
    assert secret_entry.hidden is True
    
    # Revelar el secreto (hidden=False)
    updated_card = crud.update_card_visibility(db, secret_entry.id, hidden=False)
    db.commit()
    db.refresh(updated_card)
    
    assert updated_card.hidden is False
    
    # Ocultar de nuevo (hidden=True)
    updated_card_2 = crud.update_card_visibility(db, secret_entry.id, hidden=True)
    db.commit()
    db.refresh(updated_card_2)
    
    assert updated_card_2.hidden is True
    
    # Carta inexistente
    nonexistent = crud.update_card_visibility(db, 9999, hidden=False)
    assert nonexistent is None


def test_get_max_position_for_player_secrets(db):
    """Test obtener posición máxima de secretos de un jugador"""
    game = crud.create_game(db, {})
    room = crud.create_room(db, {"name": "Mesa 1", "status": "INGAME", "id_game": game.id})
    player1 = crud.create_player(db, {
        "name": "Ana",
        "avatar_src": "avatar1.png",
        "birthdate": date(2000, 5, 10),
        "id_room": room.id,
        "is_host": True
    })
    player2 = crud.create_player(db, {
        "name": "Luis",
        "avatar_src": "avatar2.png",
        "birthdate": date(1999, 3, 1),
        "id_room": room.id,
        "is_host": False
    })
    
    # Caso 1: Jugador sin secretos (posición máxima = 0)
    max_pos = crud.get_max_position_for_player_secrets(db, game.id, player1.id)
    assert max_pos == 0
    
    # Crear secretos
    secrets = [
        models.Card(name=f"Secret {i}", description="desc", type="SECRET", img_src=f"img{i}.png", qty=1)
        for i in range(1, 6)
    ]
    db.add_all(secrets)
    db.commit()
    
    # Player1: 3 secretos en posiciones 1, 2, 5
    for i, pos in enumerate([1, 2, 5]):
        db.refresh(secrets[i])
        entry = models.CardsXGame(
            id_game=game.id,
            id_card=secrets[i].id,
            is_in=models.CardState.SECRET_SET,
            position=pos,
            player_id=player1.id,
            hidden=True
        )
        db.add(entry)
    
    # Player2: 2 secretos en posiciones 1, 2
    for i in range(3, 5):
        db.refresh(secrets[i])
        entry = models.CardsXGame(
            id_game=game.id,
            id_card=secrets[i].id,
            is_in=models.CardState.SECRET_SET,
            position=i-2,
            player_id=player2.id,
            hidden=True
        )
        db.add(entry)
    
    db.commit()
    
    # Caso 2: Player1 debe tener posición máxima 5
    max_pos_p1 = crud.get_max_position_for_player_secrets(db, game.id, player1.id)
    assert max_pos_p1 == 5
    
    # Caso 3: Player2 debe tener posición máxima 2
    max_pos_p2 = crud.get_max_position_for_player_secrets(db, game.id, player2.id)
    assert max_pos_p2 == 2


def test_transfer_secret_card(db):
    """Test transferir un secreto de un jugador a otro"""
    game = crud.create_game(db, {})
    room = crud.create_room(db, {"name": "Mesa 1", "status": "INGAME", "id_game": game.id})
    player1 = crud.create_player(db, {
        "name": "Ana",
        "avatar_src": "avatar1.png",
        "birthdate": date(2000, 5, 10),
        "id_room": room.id,
        "is_host": True
    })
    player2 = crud.create_player(db, {
        "name": "Luis",
        "avatar_src": "avatar2.png",
        "birthdate": date(1999, 3, 1),
        "id_room": room.id,
        "is_host": False
    })
    
    # Crear secreto de player1
    secret_card = models.Card(
        name="You are the Murderer!!",
        description="Secret card",
        type="SECRET",
        img_src="/assets/cards/murderer.png",
        qty=1
    )
    db.add(secret_card)
    db.commit()
    db.refresh(secret_card)
    
    secret_entry = models.CardsXGame(
        id_game=game.id,
        id_card=secret_card.id,
        is_in=models.CardState.SECRET_SET,
        position=2,
        player_id=player1.id,
        hidden=False  # Revelado
    )
    db.add(secret_entry)
    db.commit()
    db.refresh(secret_entry)
    
    # Verificar estado inicial
    assert secret_entry.player_id == player1.id
    assert secret_entry.position == 2
    assert secret_entry.hidden is False
    
    # Transferir a player2 en posición 5, face-down
    transferred = crud.transfer_secret_card(
        db=db,
        card_id=secret_entry.id,
        new_player_id=player2.id,
        new_position=5,
        face_down=True
    )
    db.commit()
    db.refresh(transferred)
    
    # Verificar que cambió de dueño, posición y visibilidad
    assert transferred.player_id == player2.id
    assert transferred.position == 5
    assert transferred.hidden is True  # Face-down
    assert transferred.is_in == models.CardState.SECRET_SET  # Sigue siendo secreto
    
    # Transferir de vuelta a player1, face-up
    transferred_back = crud.transfer_secret_card(
        db=db,
        card_id=secret_entry.id,
        new_player_id=player1.id,
        new_position=3,
        face_down=False
    )
    db.commit()
    db.refresh(transferred_back)
    
    assert transferred_back.player_id == player1.id
    assert transferred_back.position == 3
    assert transferred_back.hidden is False  # Face-up
    
    # Carta inexistente
    nonexistent = crud.transfer_secret_card(db, 9999, player2.id, 1, True)
    assert nonexistent is None


def test_get_player_secrets(db):
    """Test obtener todos los secretos de un jugador"""
    game = crud.create_game(db, {})
    room = crud.create_room(db, {"name": "Sala Test", "status": "INGAME", "id_game": game.id})
    player = crud.create_player(db, {
        "name": "María",
        "avatar_src": "avatar.png",
        "birthdate": date(2000, 1, 1),
        "id_room": room.id,
        "is_host": True
    })
    
    # Crear cartas de secreto
    secret1 = models.Card(name="Secret 1", description="...", type="SECRET", img_src="/s1.png", qty=1)
    secret2 = models.Card(name="Secret 2", description="...", type="SECRET", img_src="/s2.png", qty=1)
    db.add_all([secret1, secret2])
    db.commit()
    
    # Crear entradas en CardsXGame: 1 revelado, 1 oculto
    entry1 = models.CardsXGame(
        id_game=game.id, id_card=secret1.id, is_in=models.CardState.SECRET_SET,
        position=1, player_id=player.id, hidden=False
    )
    entry2 = models.CardsXGame(
        id_game=game.id, id_card=secret2.id, is_in=models.CardState.SECRET_SET,
        position=2, player_id=player.id, hidden=True
    )
    db.add_all([entry1, entry2])
    db.commit()
    
    # Obtener secretos del jugador
    secrets = crud.get_player_secrets(db, game.id, player.id)
    
    # Verificar que obtiene ambos secretos
    assert len(secrets) == 2
    assert entry1 in secrets
    assert entry2 in secrets
    
    # Jugador sin secretos
    player2 = crud.create_player(db, {
        "name": "Pedro",
        "avatar_src": "avatar2.png",
        "birthdate": date(1999, 5, 5),
        "id_room": room.id,
        "is_host": False
    })
    secrets_empty = crud.get_player_secrets(db, game.id, player2.id)
    assert len(secrets_empty) == 0


def test_check_player_in_social_disgrace(db):
    """Test verificar si un jugador está en desgracia social"""
    game = crud.create_game(db, {})
    room = crud.create_room(db, {"name": "Sala Test", "status": "INGAME", "id_game": game.id})
    player = crud.create_player(db, {
        "name": "Carlos",
        "avatar_src": "avatar.png",
        "birthdate": date(1998, 7, 15),
        "id_room": room.id,
        "is_host": True
    })
    
    # Inicialmente no está en desgracia
    is_in_disgrace = crud.check_player_in_social_disgrace(db, game.id, player.id)
    assert is_in_disgrace is False
    
    # Agregar a desgracia social
    crud.add_player_to_social_disgrace(db, game.id, player.id)
    db.commit()
    
    # Ahora sí está en desgracia
    is_in_disgrace = crud.check_player_in_social_disgrace(db, game.id, player.id)
    assert is_in_disgrace is True


def test_get_social_disgrace_record(db):
    """Test obtener el registro de desgracia social de un jugador"""
    game = crud.create_game(db, {})
    room = crud.create_room(db, {"name": "Sala Test", "status": "INGAME", "id_game": game.id})
    player = crud.create_player(db, {
        "name": "Julia",
        "avatar_src": "avatar.png",
        "birthdate": date(2001, 3, 20),
        "id_room": room.id,
        "is_host": True
    })
    
    # Sin registro
    record = crud.get_social_disgrace_record(db, game.id, player.id)
    assert record is None
    
    # Crear registro
    disgrace_record = models.SocialDisgracePlayer(id_game=game.id, player_id=player.id)
    db.add(disgrace_record)
    db.commit()
    db.refresh(disgrace_record)
    
    # Obtener registro
    record = crud.get_social_disgrace_record(db, game.id, player.id)
    assert record is not None
    assert record.id_game == game.id
    assert record.player_id == player.id
    assert record.entered_at is not None


def test_add_player_to_social_disgrace(db):
    """Test agregar un jugador a desgracia social"""
    game = crud.create_game(db, {})
    room = crud.create_room(db, {"name": "Sala Test", "status": "INGAME", "id_game": game.id})
    player = crud.create_player(db, {
        "name": "Roberto",
        "avatar_src": "avatar.png",
        "birthdate": date(1997, 11, 8),
        "id_room": room.id,
        "is_host": True
    })
    
    # Agregar a desgracia
    record = crud.add_player_to_social_disgrace(db, game.id, player.id)
    db.commit()
    
    # Verificar que se creó el registro
    assert record is not None
    assert record.id_game == game.id
    assert record.player_id == player.id
    assert record.entered_at is not None
    
    # Intentar agregar de nuevo al mismo jugador (debe retornar el existente)
    record2 = crud.add_player_to_social_disgrace(db, game.id, player.id)
    db.commit()
    assert record2.id == record.id  # Es el mismo registro


def test_remove_player_from_social_disgrace(db):
    """Test eliminar un jugador de desgracia social"""
    game = crud.create_game(db, {})
    room = crud.create_room(db, {"name": "Sala Test", "status": "INGAME", "id_game": game.id})
    player = crud.create_player(db, {
        "name": "Laura",
        "avatar_src": "avatar.png",
        "birthdate": date(2000, 9, 12),
        "id_room": room.id,
        "is_host": True
    })
    
    # Agregar a desgracia
    crud.add_player_to_social_disgrace(db, game.id, player.id)
    db.commit()
    
    # Verificar que está en desgracia
    assert crud.check_player_in_social_disgrace(db, game.id, player.id) is True
    
    # Eliminar de desgracia
    result = crud.remove_player_from_social_disgrace(db, game.id, player.id)
    db.commit()
    
    # Verificar que se eliminó
    assert result is True
    assert crud.check_player_in_social_disgrace(db, game.id, player.id) is False
    
    # Intentar eliminar de nuevo (no existe)
    result2 = crud.remove_player_from_social_disgrace(db, game.id, player.id)
    assert result2 is False


def test_get_players_in_social_disgrace_with_info(db):
    """Test obtener lista completa de jugadores en desgracia social con su info"""
    game = crud.create_game(db, {})
    room = crud.create_room(db, {"name": "Sala Test", "status": "INGAME", "id_game": game.id})
    
    # Crear 3 jugadores
    player1 = crud.create_player(db, {
        "name": "Ana",
        "avatar_src": "avatar1.png",
        "birthdate": date(2000, 1, 1),
        "id_room": room.id,
        "is_host": True
    })
    player2 = crud.create_player(db, {
        "name": "Luis",
        "avatar_src": "avatar2.png",
        "birthdate": date(1999, 2, 2),
        "id_room": room.id,
        "is_host": False
    })
    player3 = crud.create_player(db, {
        "name": "Sara",
        "avatar_src": "avatar3.png",
        "birthdate": date(2001, 3, 3),
        "id_room": room.id,
        "is_host": False
    })
    
    # Solo player1 y player3 en desgracia
    crud.add_player_to_social_disgrace(db, game.id, player1.id)
    crud.add_player_to_social_disgrace(db, game.id, player3.id)
    db.commit()
    
    # Obtener lista
    disgrace_list = crud.get_players_in_social_disgrace_with_info(db, game.id)
    
    # Verificar que hay 2 jugadores
    assert len(disgrace_list) == 2
    
    # Verificar estructura de datos
    player_ids = [p["player_id"] for p in disgrace_list]
    assert player1.id in player_ids
    assert player3.id in player_ids
    assert player2.id not in player_ids
    
    # Verificar que tiene los campos necesarios
    for player_info in disgrace_list:
        assert "player_id" in player_info
        assert "player_name" in player_info
        assert "avatar_src" in player_info
        assert "entered_at" in player_info
    
    # Verificar nombres
    names = [p["player_name"] for p in disgrace_list]
    assert "Ana" in names
    assert "Sara" in names
    
    # Juego sin jugadores en desgracia
    game2 = crud.create_game(db, {})
    empty_list = crud.get_players_in_social_disgrace_with_info(db, game2.id)
    assert len(empty_list) == 0


def test_get_room_by_game_id(db):
    """Test obtener la sala asociada a un juego"""
    game = crud.create_game(db, {})
    room = crud.create_room(db, {
        "name": "Sala Principal",
        "status": "INGAME",
        "id_game": game.id
    })
    
    # Obtener sala por game_id
    found_room = crud.get_room_by_game_id(db, game.id)
    
    # Verificar que encontró la sala correcta
    assert found_room is not None
    assert found_room.id == room.id
    assert found_room.name == "Sala Principal"
    assert found_room.id_game == game.id
    
    # Juego sin sala asociada
    game2 = crud.create_game(db, {})
    no_room = crud.get_room_by_game_id(db, game2.id)
    assert no_room is None


# ------------------------------
# TESTS NOT SO FAST (NSF)
# ------------------------------
def test_get_actions_by_filters(db):
    """Test filtrar acciones por parent_action_id, triggered_by_action_id y action_name"""
    game = crud.create_game(db, {})
    room = crud.create_room(db, {"name": "Mesa 1", "status": "INGAME", "id_game": game.id})
    player = crud.create_player(db, {
        "name": "Ana",
        "avatar_src": "avatar1.png",
        "birthdate": date(2000, 5, 10),
        "id_room": room.id,
        "is_host": True
    })
    
    turn = models.Turn(
        number=1,
        id_game=game.id,
        player_id=player.id,
        status=models.TurnStatus.IN_PROGRESS
    )
    db.add(turn)
    db.commit()
    db.refresh(turn)
    
    # Crear acción de intención (XXX)
    intention_action = crud.create_action(db, {
        "id_game": game.id,
        "turn_id": turn.id,
        "player_id": player.id,
        "action_name": "Point your suspicions",
        "action_type": models.ActionType.INIT,
        "result": models.ActionResult.PENDING
    })
    db.commit()
    db.refresh(intention_action)
    
    # Crear acción NSF start (YYY)
    nsf_start_action = crud.create_action(db, {
        "id_game": game.id,
        "turn_id": turn.id,
        "player_id": player.id,
        "action_name": models.ActionName.INSTANT_START,
        "action_type": models.ActionType.INSTANT,
        "result": models.ActionResult.PENDING,
        "triggered_by_action_id": intention_action.id
    })
    db.commit()
    db.refresh(nsf_start_action)
    
    # Crear 3 acciones NSF jugadas (ZZZ1, ZZZ2, ZZZ3)
    nsf_actions = []
    for i in range(3):
        nsf_action = crud.create_action(db, {
            "id_game": game.id,
            "turn_id": turn.id,
            "player_id": player.id,
            "action_name": "NOT_SO_FAST",
            "action_type": models.ActionType.INSTANT,
            "result": models.ActionResult.PENDING,
            "parent_action_id": nsf_start_action.id,
            "triggered_by_action_id": intention_action.id
        })
        db.commit()
        db.refresh(nsf_action)
        nsf_actions.append(nsf_action)
    
    # Crear otra acción de otro jugador para noise
    other_action = crud.create_action(db, {
        "id_game": game.id,
        "turn_id": turn.id,
        "player_id": player.id,
        "action_name": "OTHER_ACTION",
        "action_type": models.ActionType.DISCARD,
        "result": models.ActionResult.SUCCESS
    })
    db.commit()
    
    # Test 1: Filtrar por parent_action_id
    filtered_by_parent = crud.get_actions_by_filters(
        db, 
        parent_action_id=nsf_start_action.id
    )
    assert len(filtered_by_parent) == 3
    assert all(action.parent_action_id == nsf_start_action.id for action in filtered_by_parent)
    
    # Test 2: Filtrar por triggered_by_action_id
    filtered_by_trigger = crud.get_actions_by_filters(
        db,
        triggered_by_action_id=intention_action.id
    )
    assert len(filtered_by_trigger) == 4  # YYY + 3 ZZZ
    assert all(action.triggered_by_action_id == intention_action.id for action in filtered_by_trigger)
    
    # Test 3: Filtrar por action_name
    filtered_by_name = crud.get_actions_by_filters(
        db,
        action_name="NOT_SO_FAST"
    )
    assert len(filtered_by_name) == 3
    assert all(action.action_name == "NOT_SO_FAST" for action in filtered_by_name)
    
    # Test 4: Filtrar por combinación (parent + trigger)
    filtered_combined = crud.get_actions_by_filters(
        db,
        parent_action_id=nsf_start_action.id,
        triggered_by_action_id=intention_action.id
    )
    assert len(filtered_combined) == 3  # Solo las ZZZ
    
    # Test 5: Filtrar por combinación completa (parent + trigger + name)
    filtered_all = crud.get_actions_by_filters(
        db,
        parent_action_id=nsf_start_action.id,
        triggered_by_action_id=intention_action.id,
        action_name="NOT_SO_FAST"
    )
    assert len(filtered_all) == 3
    
    # Test 6: Sin filtros (debería traer todas las acciones del juego)
    all_actions = crud.get_actions_by_filters(db)
    assert len(all_actions) >= 5  # XXX + YYY + 3 ZZZ + OTHER
    
    # Test 7: Filtro que no matchea nada
    no_match = crud.get_actions_by_filters(
        db,
        parent_action_id=9999
    )
    assert len(no_match) == 0


# ==============================================================================
# TESTS PARA NUEVAS FUNCIONES NSF (endpoint /instant/not-so-fast)
# ==============================================================================

def test_get_nsf_start_action_success(db):
    """Test: get_nsf_start_action encuentra la acción YYY correcta."""
    from datetime import date
    
    # Setup
    game = models.Game(player_turn_id=None)
    db.add(game)
    db.flush()
    
    player = models.Player(name="Player1", avatar_src="/avatar.jpg", birthdate=date(1990, 1, 1), is_host=True, order=1)
    db.add(player)
    db.flush()
    
    # Crear acción XXX (INIT)
    intention = models.ActionsPerTurn(
        id_game=game.id,
        player_id=player.id,
        action_type=models.ActionType.INIT,
        action_name="Point your suspicions",
        result=models.ActionResult.PENDING
    )
    db.add(intention)
    db.flush()
    
    # Crear acción YYY (INSTANT_START) triggered by XXX
    nsf_start = models.ActionsPerTurn(
        id_game=game.id,
        player_id=player.id,
        action_type=models.ActionType.INSTANT,
        action_name="Instant Start",
        result=models.ActionResult.PENDING,
        triggered_by_action_id=intention.id
    )
    db.add(nsf_start)
    db.commit()
    
    # Test
    result = crud.get_nsf_start_action(db, intention.id, game.id)
    
    # Assert
    assert result is not None
    assert result.id == nsf_start.id
    assert result.action_type == models.ActionType.INSTANT
    assert result.action_name == "Instant Start"
    assert result.triggered_by_action_id == intention.id


def test_get_nsf_start_action_not_found(db):
    """Test: get_nsf_start_action retorna None si no existe YYY."""
    from datetime import date
    
    # Setup
    game = models.Game(player_turn_id=None)
    db.add(game)
    db.flush()
    
    player = models.Player(name="Player1", avatar_src="/avatar.jpg", birthdate=date(1990, 1, 1), is_host=True, order=1)
    db.add(player)
    db.flush()
    
    # Crear acción XXX sin YYY
    intention = models.ActionsPerTurn(
        id_game=game.id,
        player_id=player.id,
        action_type=models.ActionType.INIT,
        action_name="Point your suspicions",
        result=models.ActionResult.PENDING
    )
    db.add(intention)
    db.commit()
    
    # Test
    result = crud.get_nsf_start_action(db, intention.id, game.id)
    
    # Assert
    assert result is None


def test_move_card_to_discard(db):
    """Test: move_card_to_discard mueve una carta de HAND a DISCARD."""
    from datetime import date
    
    # Setup
    game = models.Game(player_turn_id=None)
    db.add(game)
    db.flush()
    
    player = models.Player(name="Player1", avatar_src="/avatar.jpg", birthdate=date(1990, 1, 1), is_host=True, order=1)
    db.add(player)
    db.flush()
    
    card = models.Card(name="Not so fast", description="NSF card", type="INSTANT", img_src="/nsf.png", qty=10)
    db.add(card)
    db.flush()
    
    # Carta en la mano del jugador
    card_in_hand = models.CardsXGame(
        id_game=game.id,
        id_card=card.id,
        is_in=models.CardState.HAND,
        position=1,
        player_id=player.id,
        hidden=True
    )
    db.add(card_in_hand)
    db.flush()
    
    # Carta ya en discard (para calcular nueva posición)
    existing_discard = models.CardsXGame(
        id_game=game.id,
        id_card=card.id,
        is_in=models.CardState.DISCARD,
        position=1,
        player_id=None,
        hidden=False
    )
    db.add(existing_discard)
    db.commit()
    
    # Test
    crud.move_card_to_discard(db, card_in_hand.id, game.id)
    
    # Assert
    db.refresh(card_in_hand)
    assert card_in_hand.is_in == models.CardState.DISCARD
    assert card_in_hand.position == 1  # Tope del descarte
    assert card_in_hand.player_id is None
    assert card_in_hand.hidden is False
    
    # Verificar que la carta anterior se movió a posición 2
    db.refresh(existing_discard)
    assert existing_discard.position == 2


def test_create_nsf_play_action(db):
    """Test: create_nsf_play_action crea una acción ZZZ correcta."""
    from datetime import date
    
    # Setup
    game = models.Game(player_turn_id=None)
    db.add(game)
    db.flush()
    
    player = models.Player(name="Player2", avatar_src="/avatar.jpg", birthdate=date(1990, 1, 1), is_host=False, order=2)
    db.add(player)
    db.flush()
    
    # Acción XXX
    intention = models.ActionsPerTurn(
        id_game=game.id,
        player_id=player.id,
        action_type=models.ActionType.INIT,
        action_name="Point your suspicions",
        result=models.ActionResult.PENDING
    )
    db.add(intention)
    db.flush()
    
    # Acción YYY
    nsf_start = models.ActionsPerTurn(
        id_game=game.id,
        player_id=player.id,
        action_type=models.ActionType.INSTANT,
        action_name="Instant Start",
        result=models.ActionResult.PENDING,
        triggered_by_action_id=intention.id
    )
    db.add(nsf_start)
    db.commit()
    
    # Test
    from datetime import datetime, timedelta
    
    nsf_play = crud.create_nsf_play_action(
        db=db,
        game_id=game.id,
        turn_id=None,
        player_id=player.id,
        nsf_start_action_id=nsf_start.id,
        original_action_id=intention.id,
        card_id=1,
        action_time_end=datetime.now() + timedelta(seconds=5)
    )
    
    # Assert
    assert nsf_play is not None
    assert nsf_play.action_type == models.ActionType.INSTANT
    assert nsf_play.action_name == models.ActionName.INSTANT_PLAY
    assert nsf_play.player_id == player.id
    assert nsf_play.parent_action_id == nsf_start.id
    assert nsf_play.triggered_by_action_id == intention.id
    assert nsf_play.result == models.ActionResult.PENDING


def test_update_action_time_end(db):
    """Test: update_action_time_end actualiza el action_time_end."""
    from datetime import datetime, timedelta
    
    # Setup
    game = models.Game(player_turn_id=None)
    db.add(game)
    db.flush()
    
    player = models.Player(name="Player1", avatar_src="/avatar.jpg", birthdate=date(1990, 1, 1), is_host=True, order=1)
    db.add(player)
    db.flush()
    
    action = models.ActionsPerTurn(
        id_game=game.id,
        player_id=player.id,
        action_type=models.ActionType.INSTANT,
        action_name="Instant Start",
        result=models.ActionResult.PENDING
    )
    db.add(action)
    db.commit()
    
    # Test
    new_time = datetime.now() + timedelta(seconds=5)
    crud.update_action_time_end(db, action.id, new_time)
    
    # Assert
    db.refresh(action)
    assert action.action_time_end is not None
    assert abs((action.action_time_end - new_time).total_seconds()) < 1  # Margen de 1 segundo


def test_get_action_by_id_with_game_id_filter(db):
    """Test: get_action_by_id con game_id filtra correctamente."""
    from datetime import date
    
    # Setup
    game1 = models.Game(player_turn_id=None)
    game2 = models.Game(player_turn_id=None)
    db.add_all([game1, game2])
    db.flush()
    
    player = models.Player(name="Player1", avatar_src="/avatar.jpg", birthdate=date(1990, 1, 1), is_host=True, order=1)
    db.add(player)
    db.flush()
    
    # Acción en game1
    action_game1 = models.ActionsPerTurn(
        id_game=game1.id,
        player_id=player.id,
        action_type=models.ActionType.INIT,
        action_name="Action Game 1",
        result=models.ActionResult.PENDING
    )
    db.add(action_game1)
    db.commit()
    
    # Test 1: Buscar con game_id correcto
    result = crud.get_action_by_id(db, action_game1.id, game1.id)
    assert result is not None
    assert result.id == action_game1.id
    
    # Test 2: Buscar con game_id incorrecto
    result_wrong = crud.get_action_by_id(db, action_game1.id, game2.id)
    assert result_wrong is None
    
    # Test 3: Buscar sin game_id (debería funcionar)
    result_no_filter = crud.get_action_by_id(db, action_game1.id)
    assert result_no_filter is not None
    assert result_no_filter.id == action_game1.id


# ------------------------------
# TESTS DEAD CARD FOLLY - CRUD
# ------------------------------

def test_get_player_neighbor_by_direction_left(db):
    """Test obtener vecino izquierdo (orden descendente)"""
    # Setup: crear room y 4 jugadores con orders 1, 2, 3, 4
    room = crud.create_room(db, {"name": "Mesa DCF", "status": "INGAME"})
    
    player1 = crud.create_player(db, {
        "name": "Player 1",
        "avatar_src": "avatar1.png",
        "birthdate": date(2000, 1, 1),
        "id_room": room.id,
        "order": 1
    })
    player2 = crud.create_player(db, {
        "name": "Player 2",
        "avatar_src": "avatar2.png",
        "birthdate": date(2000, 2, 2),
        "id_room": room.id,
        "order": 2
    })
    player3 = crud.create_player(db, {
        "name": "Player 3",
        "avatar_src": "avatar3.png",
        "birthdate": date(2000, 3, 3),
        "id_room": room.id,
        "order": 3
    })
    player4 = crud.create_player(db, {
        "name": "Player 4",
        "avatar_src": "avatar4.png",
        "birthdate": date(2000, 4, 4),
        "id_room": room.id,
        "order": 4
    })
    
    # Test: LEFT desde player 3 debería retornar player 2
    neighbor = crud.get_player_neighbor_by_direction(db, player3.id, room.id, models.Direction.LEFT)
    assert neighbor is not None
    assert neighbor.id == player2.id
    assert neighbor.order == 2
    
    # Test: LEFT desde player 2 debería retornar player 1
    neighbor = crud.get_player_neighbor_by_direction(db, player2.id, room.id, models.Direction.LEFT)
    assert neighbor is not None
    assert neighbor.id == player1.id
    assert neighbor.order == 1
    
    # Test: LEFT desde player 1 debería retornar player 4 (wraparound)
    neighbor = crud.get_player_neighbor_by_direction(db, player1.id, room.id, models.Direction.LEFT)
    assert neighbor is not None
    assert neighbor.id == player4.id
    assert neighbor.order == 4


def test_get_player_neighbor_by_direction_right(db):
    """Test obtener vecino derecho (orden ascendente)"""
    # Setup: crear room y 4 jugadores
    room = crud.create_room(db, {"name": "Mesa DCF", "status": "INGAME"})
    
    player1 = crud.create_player(db, {
        "name": "Player 1",
        "avatar_src": "avatar1.png",
        "birthdate": date(2000, 1, 1),
        "id_room": room.id,
        "order": 1
    })
    player2 = crud.create_player(db, {
        "name": "Player 2",
        "avatar_src": "avatar2.png",
        "birthdate": date(2000, 2, 2),
        "id_room": room.id,
        "order": 2
    })
    player3 = crud.create_player(db, {
        "name": "Player 3",
        "avatar_src": "avatar3.png",
        "birthdate": date(2000, 3, 3),
        "id_room": room.id,
        "order": 3
    })
    player4 = crud.create_player(db, {
        "name": "Player 4",
        "avatar_src": "avatar4.png",
        "birthdate": date(2000, 4, 4),
        "id_room": room.id,
        "order": 4
    })
    
    # Test: RIGHT desde player 1 debería retornar player 2
    neighbor = crud.get_player_neighbor_by_direction(db, player1.id, room.id, models.Direction.RIGHT)
    assert neighbor is not None
    assert neighbor.id == player2.id
    assert neighbor.order == 2
    
    # Test: RIGHT desde player 3 debería retornar player 4
    neighbor = crud.get_player_neighbor_by_direction(db, player3.id, room.id, models.Direction.RIGHT)
    assert neighbor is not None
    assert neighbor.id == player4.id
    assert neighbor.order == 4
    
    # Test: RIGHT desde player 4 debería retornar player 1 (wraparound)
    neighbor = crud.get_player_neighbor_by_direction(db, player4.id, room.id, models.Direction.RIGHT)
    assert neighbor is not None
    assert neighbor.id == player1.id
    assert neighbor.order == 1


def test_get_player_neighbor_by_direction_edge_cases(db):
    """Test casos edge: jugador inexistente, solo 1 jugador, room vacío"""
    # Setup: crear room con 1 solo jugador
    room = crud.create_room(db, {"name": "Mesa Solo", "status": "INGAME"})
    
    player1 = crud.create_player(db, {
        "name": "Solo Player",
        "avatar_src": "avatar1.png",
        "birthdate": date(2000, 1, 1),
        "id_room": room.id,
        "order": 1
    })
    
    # Test: Solo 1 jugador, no hay vecinos
    neighbor = crud.get_player_neighbor_by_direction(db, player1.id, room.id, models.Direction.LEFT)
    assert neighbor is None
    
    neighbor = crud.get_player_neighbor_by_direction(db, player1.id, room.id, models.Direction.RIGHT)
    assert neighbor is None
    
    # Test: Jugador inexistente
    neighbor = crud.get_player_neighbor_by_direction(db, 9999, room.id, models.Direction.LEFT)
    assert neighbor is None
    
    # Test: Room inexistente
    neighbor = crud.get_player_neighbor_by_direction(db, player1.id, 9999, models.Direction.LEFT)
    assert neighbor is None


def test_swap_cards_between_players(db):
    """Test intercambiar cartas entre dos jugadores"""
    # Setup: crear game, players, y cartas
    game = crud.create_game(db, {})
    room = crud.create_room(db, {"name": "Mesa Swap", "status": "INGAME", "id_game": game.id})
    
    player1 = crud.create_player(db, {
        "name": "Player 1",
        "avatar_src": "avatar1.png",
        "birthdate": date(2000, 1, 1),
        "id_room": room.id,
        "order": 1
    })
    player2 = crud.create_player(db, {
        "name": "Player 2",
        "avatar_src": "avatar2.png",
        "birthdate": date(2000, 2, 2),
        "id_room": room.id,
        "order": 2
    })
    
    # Crear cartas en base de datos
    card_a = models.Card(name="Card A", description="desc", type="EVENT", img_src="a.png", qty=1)
    card_b = models.Card(name="Card B", description="desc", type="EVENT", img_src="b.png", qty=1)
    db.add_all([card_a, card_b])
    db.commit()
    db.refresh(card_a)
    db.refresh(card_b)
    
    # Player 1 tiene Card A en position 2
    card_xgame_p1 = models.CardsXGame(
        id_game=game.id,
        id_card=card_a.id,
        player_id=player1.id,
        is_in=models.CardState.HAND,
        position=2,
        hidden=False
    )
    
    # Player 2 tiene Card B en position 1
    card_xgame_p2 = models.CardsXGame(
        id_game=game.id,
        id_card=card_b.id,
        player_id=player2.id,
        is_in=models.CardState.HAND,
        position=1,
        hidden=False
    )
    
    db.add_all([card_xgame_p1, card_xgame_p2])
    db.commit()
    db.refresh(card_xgame_p1)
    db.refresh(card_xgame_p2)
    
    # Guardar valores originales
    original_p1_card = card_xgame_p1.id_card
    original_p2_card = card_xgame_p2.id_card
    
    # Test: hacer swap
    result_give, result_receive = crud.swap_cards_between_players(db, card_xgame_p1.id, card_xgame_p2.id)
    db.commit()
    db.refresh(card_xgame_p1)
    db.refresh(card_xgame_p2)
    
    # Verificar que las cartas se intercambiaron
    assert card_xgame_p1.id_card == original_p2_card  # Player 1 ahora tiene Card B
    assert card_xgame_p2.id_card == original_p1_card  # Player 2 ahora tiene Card A
    
    # Verificar que positions y player_id NO cambiaron
    assert card_xgame_p1.player_id == player1.id
    assert card_xgame_p1.position == 2
    assert card_xgame_p2.player_id == player2.id
    assert card_xgame_p2.position == 1
    
    # Verificar que is_in y hidden NO cambiaron
    assert card_xgame_p1.is_in == models.CardState.HAND
    assert card_xgame_p2.is_in == models.CardState.HAND
    assert card_xgame_p1.hidden is False
    assert card_xgame_p2.hidden is False


def test_swap_cards_between_players_invalid(db):
    """Test swap con IDs inválidos"""
    # Test: IDs inexistentes
    result_give, result_receive = crud.swap_cards_between_players(db, 9999, 8888)
    assert result_give is None
    assert result_receive is None
    
    # Setup: crear una carta válida
    game = crud.create_game(db, {})
    room = crud.create_room(db, {"name": "Mesa Test", "status": "INGAME", "id_game": game.id})
    player = crud.create_player(db, {
        "name": "Player 1",
        "avatar_src": "avatar1.png",
        "birthdate": date(2000, 1, 1),
        "id_room": room.id,
        "order": 1
    })
    
    card = models.Card(name="Test Card", description="desc", type="EVENT", img_src="test.png", qty=1)
    db.add(card)
    db.commit()
    db.refresh(card)
    
    card_xgame = models.CardsXGame(
        id_game=game.id,
        id_card=card.id,
        player_id=player.id,
        is_in=models.CardState.HAND,
        position=1,
        hidden=False
    )
    db.add(card_xgame)
    db.commit()
    db.refresh(card_xgame)
    
    # Test: un ID válido, otro inválido
    result_give, result_receive = crud.swap_cards_between_players(db, card_xgame.id, 9999)
    assert result_give is None
    assert result_receive is None
