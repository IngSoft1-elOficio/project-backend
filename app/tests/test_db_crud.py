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