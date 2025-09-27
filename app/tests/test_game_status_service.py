import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi import HTTPException
from datetime import date
from app.db import models, crud
from app.db.database import Base
from app.services.game_status_service import get_game_status_service
from app.schemas.game_status_schema import GameStateView

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

@pytest.fixture
def setup_game_data(db):
    """Fixture que crea datos básicos para los tests."""
    # Crear game
    game = crud.create_game(db, {})
    
    # Crear room asociada
    room = crud.create_room(db, {
        "name": "Mesa Test", 
        "player_qty": 2,  
        "status": "INGAME",
        "id_game": game.id
    })
    
    # Crear jugadores
    player1 = crud.create_player(db, {
        "name": "Ana",
        "avatar_src": "/assets/avatars/detective1.png",
        "birthdate": date(2000, 5, 10),
        "id_room": room.id,
        "is_host": True,
        "order": 1
    })
    
    player2 = crud.create_player(db, {
        "name": "Luis", 
        "avatar_src": "/assets/avatars/detective2.png",
        "birthdate": date(1999, 3, 1),
        "id_room": room.id,
        "is_host": False,
        "order": 2
    })
    
    # Setear turno actual
    crud.update_player_turn(db, game.id, player1.id)
    
    # Crear todas las cartas necesarias
    cards = []
    
    # 6 cartas mano player1: 2 detective, 1 instant, 3 evento
    cards.extend([
        models.Card(name="Carta Detective 1", description="desc", type="DETECTIVE", img_src="detective.png"),
        models.Card(name="Carta Detective 2", description="desc", type="DETECTIVE", img_src="detective.png"),
        models.Card(name="Carta Instant 1", description="desc", type="INSTANT", img_src="instant.png"),
        models.Card(name="Carta Evento 1", description="desc", type="EVENT", img_src="event.png"),
        models.Card(name="Carta Evento 2", description="desc", type="EVENT", img_src="event.png"),
        models.Card(name="Carta Evento 3", description="desc", type="EVENT", img_src="event.png"),
    ])
    
    # 6 cartas mano player2: 2 detective, 1 instant, 3 evento  
    cards.extend([
        models.Card(name="Carta Detective 3", description="desc", type="DETECTIVE", img_src="detective.png"),
        models.Card(name="Carta Detective 4", description="desc", type="DETECTIVE", img_src="detective.png"),
        models.Card(name="Carta Instant 2", description="desc", type="INSTANT", img_src="instant.png"),
        models.Card(name="Carta Evento 4", description="desc", type="EVENT", img_src="event.png"),
        models.Card(name="Carta Evento 5", description="desc", type="EVENT", img_src="event.png"),
        models.Card(name="Carta Evento 6", description="desc", type="EVENT", img_src="event.png"),
    ])
    
    # 3 secretos para cada jugador
    cards.extend([
        models.Card(name="Secreto 1", description="desc", type="SECRET", img_src="secret.png"),
        models.Card(name="Secreto 2", description="desc", type="SECRET", img_src="secret.png"),
        models.Card(name="Secreto 3", description="desc", type="SECRET", img_src="secret.png"),
        models.Card(name="Secreto 4", description="desc", type="SECRET", img_src="secret.png"),
        models.Card(name="Secreto 5", description="desc", type="SECRET", img_src="secret.png"),
        models.Card(name="Secreto 6", description="desc", type="SECRET", img_src="secret.png"),
    ])
    
    # Carta para descarte
    cards.append(models.Card(name="Descarte Evento", description="desc", type="EVENT", img_src="event.png"))
    
    # Cartas para deck (inventar cantidad)
    for i in range(25): 
        cards.append(models.Card(name=f"Deck Carta {i+1}", description="desc", type="EVENT", img_src="event.png"))
    
    # Guardar todas las cartas
    db.add_all(cards)
    db.commit()
    for card in cards:
        db.refresh(card)
    
    # Asignar cartas a manos
    hand_entries = []
    
    # Player1 mano (primeras 6 cartas)
    for i, card in enumerate(cards[:6]):
        hand_entries.append(models.CardsXGame(
            id_game=game.id, id_card=card.id, player_id=player1.id,
            is_in="HAND", position=i+1
        ))
    
    # Player2 mano (siguientes 6 cartas)  
    for i, card in enumerate(cards[6:12]):
        hand_entries.append(models.CardsXGame(
            id_game=game.id, id_card=card.id, player_id=player2.id,
            is_in="HAND", position=i+1
        ))
    
    # Secretos player1 (3 cartas)
    for i, card in enumerate(cards[12:15]):
        hand_entries.append(models.CardsXGame(
            id_game=game.id, id_card=card.id, player_id=player1.id,
            is_in="SECRET_SET", position=i+1
        ))
    
    # Secretos player2 (3 cartas)
    for i, card in enumerate(cards[15:18]):
        hand_entries.append(models.CardsXGame(
            id_game=game.id, id_card=card.id, player_id=player2.id,
            is_in="SECRET_SET", position=i+1
        ))
    
    # Carta en descarte
    hand_entries.append(models.CardsXGame(
        id_game=game.id, id_card=cards[18].id, player_id=None,
        is_in="DISCARD", position=1
    ))
    
    # Cartas en deck
    for i, card in enumerate(cards[19:]):
        hand_entries.append(models.CardsXGame(
            id_game=game.id, id_card=card.id, player_id=None,
            is_in="DECK", position=i+1
        ))
    
    db.add_all(hand_entries)
    db.commit()
    
    return {
        "game": game,
        "room": room,
        "player1": player1,
        "player2": player2,
        "cards": cards
    }

# ------------------------------
# TESTS CASOS EXITOSOS
# ------------------------------

def test_get_game_status_success(db, setup_game_data):
    """Test caso exitoso - devuelve GameStateView completo."""
    data = setup_game_data
    
    result = get_game_status_service(db, data["game"].id, data["player1"].id)
    
    # Verificar tipo de respuesta
    assert isinstance(result, GameStateView)
    
    # Verificar datos del game
    assert result.game.id == data["game"].id
    assert result.game.name == "Mesa Test"
    assert result.game.player_qty == 2  
    assert result.game.status == "in_game"  
    assert result.game.host_id == data["player1"].id
    
    # Verificar jugadores
    assert len(result.players) == 2
    player_view = next(p for p in result.players if p.id == data["player1"].id)
    assert player_view.name == "Ana"
    assert player_view.is_host == True
    assert player_view.avatar == "/assets/avatars/detective1.png"
    assert player_view.order == 1
    
    # Verificar deck (25 cartas)
    assert result.deck.remaining == 25
    
    # Verificar discard (1 carta)
    assert result.discard.count == 1
    assert result.discard.top is not None
    assert result.discard.top.name == "Descarte Evento"
    assert result.discard.top.type == "EVENT"
    
    # Verificar hand del solicitante (6 cartas)
    assert result.hand is not None
    assert result.hand.player_id == data["player1"].id
    assert len(result.hand.cards) == 6
    
    # Verificar tipos de cartas en mano
    hand_types = [card.type for card in result.hand.cards]
    assert hand_types.count("DETECTIVE") == 2
    assert hand_types.count("INSTANT") == 1
    assert hand_types.count("EVENT") == 3
    
    # Verificar secrets del solicitante (3 cartas)
    assert result.secrets is not None
    assert result.secrets.player_id == data["player1"].id
    assert len(result.secrets.cards) == 3
    assert all(card.type == "SECRET" for card in result.secrets.cards)
    
    # Verificar turn info
    assert result.turn.current_player_id == data["player1"].id
    assert data["player1"].id in result.turn.order
    assert data["player2"].id in result.turn.order
    assert result.turn.can_act == True  # Es su turno

def test_get_game_status_other_player(db, setup_game_data):
    """Test jugador que no tiene el turno - no puede actuar pero ve su info."""
    data = setup_game_data
    
    result = get_game_status_service(db, data["game"].id, data["player2"].id)
    
    # Verificar que ve la info general
    assert result.game.id == data["game"].id
    assert len(result.players) == 2
    
    # Verificar que SÍ tiene hand y secrets (player2 tiene sus cartas asignadas)
    assert result.hand is not None
    assert result.hand.player_id == data["player2"].id
    assert len(result.hand.cards) == 6
    
    # Verificar tipos de cartas en mano del player2
    hand_types = [card.type for card in result.hand.cards]
    assert hand_types.count("DETECTIVE") == 2
    assert hand_types.count("INSTANT") == 1
    assert hand_types.count("EVENT") == 3
    
    assert result.secrets is not None
    assert result.secrets.player_id == data["player2"].id
    assert len(result.secrets.cards) == 3
    assert all(card.type == "SECRET" for card in result.secrets.cards)
    
    # Verificar que NO puede actuar (no es su turno)
    assert result.turn.can_act == False
    assert result.turn.current_player_id == data["player1"].id

# ------------------------------
# TESTS CASOS DE ERROR
# ------------------------------

def test_get_game_status_game_not_found(db):
    """Test error 404 - partida no existe."""
    with pytest.raises(HTTPException) as exc_info:
        get_game_status_service(db, 999, 1)
    
    assert exc_info.value.status_code == 404
    assert exc_info.value.detail["code"] == "game_not_found"
    assert exc_info.value.detail["message"] == "La partida no existe"

def test_get_game_status_room_not_found(db):
    """Test error 404 - sala no existe."""
    # Crear game sin room asociada
    game = crud.create_game(db, {})
    
    with pytest.raises(HTTPException) as exc_info:
        get_game_status_service(db, game.id, 1)
    
    assert exc_info.value.status_code == 404
    assert exc_info.value.detail["code"] == "room_not_found"
    assert exc_info.value.detail["message"] == "La sala no existe"

def test_get_game_status_game_not_started(db):
    """Test error 409 - partida no iniciada."""
    game = crud.create_game(db, {})
    room = crud.create_room(db, {
        "name": "Mesa Waiting",
        "player_qty": 4,
        "status": "WAITING",  
        "id_game": game.id
    })
    player = crud.create_player(db, {
        "name": "Test",
        "avatar_src": "test.png",
        "birthdate": date(2000, 1, 1),
        "id_room": room.id,
        "is_host": True
    })
    
    with pytest.raises(HTTPException) as exc_info:
        get_game_status_service(db, game.id, player.id)
    
    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["code"] == "game_not_started"
    assert "no fue iniciada" in exc_info.value.detail["message"]

def test_get_game_status_user_not_in_game(db, setup_game_data):
    """Test error 403 - usuario no pertenece a la partida."""
    data = setup_game_data
    
    # Crear otro jugador en otra room
    other_room = crud.create_room(db, {
        "name": "Otra Mesa",
        "player_qty": 2,
        "status": "WAITING"
    })
    other_player = crud.create_player(db, {
        "name": "Intruso",
        "avatar_src": "intruso.png", 
        "birthdate": date(2000, 1, 1),
        "id_room": other_room.id,
        "is_host": True
    })
    
    with pytest.raises(HTTPException) as exc_info:
        get_game_status_service(db, data["game"].id, other_player.id)
    
    assert exc_info.value.status_code == 403
    assert exc_info.value.detail["code"] == "forbidden"
    assert "no pertenece" in exc_info.value.detail["message"]

def test_get_game_status_user_not_exists(db, setup_game_data):
    """Test error 403 - usuario no existe."""
    data = setup_game_data
    
    with pytest.raises(HTTPException) as exc_info:
        get_game_status_service(db, data["game"].id, 999)
    
    assert exc_info.value.status_code == 403
    assert exc_info.value.detail["code"] == "forbidden"

# ------------------------------
# TESTS DE MAPEOS Y EDGE CASES  
# ------------------------------

def test_status_mapping(db):
    """Test mapeo de status INGAME -> in_game."""
    game = crud.create_game(db, {})
    room = crud.create_room(db, {
        "name": "Test Status",
        "player_qty": 2, 
        "status": "INGAME",
        "id_game": game.id
    })
    player = crud.create_player(db, {
        "name": "Test",
        "avatar_src": "test.png",
        "birthdate": date(2000, 1, 1),
        "id_room": room.id,
        "is_host": True
    })
    
    result = get_game_status_service(db, game.id, player.id)
    assert result.game.status == "in_game"

def test_no_host_found(db):
    """Test cuando no hay host definido."""
    game = crud.create_game(db, {})
    room = crud.create_room(db, {
        "name": "No Host",
        "player_qty": 2,
        "status": "INGAME", 
        "id_game": game.id
    })
    player = crud.create_player(db, {
        "name": "No Host",
        "avatar_src": "test.png",
        "birthdate": date(2000, 1, 1),
        "id_room": room.id,
        "is_host": False  # No host
    })
    
    result = get_game_status_service(db, game.id, player.id)
    assert result.game.host_id == 0  # Default cuando no hay host

def test_empty_deck_and_discard(db):
    """Test con mazo y descarte vacíos."""
    game = crud.create_game(db, {})
    room = crud.create_room(db, {
        "name": "Empty",
        "player_qty": 2,
        "status": "INGAME",
        "id_game": game.id
    })
    player = crud.create_player(db, {
        "name": "Test",
        "avatar_src": "test.png", 
        "birthdate": date(2000, 1, 1),
        "id_room": room.id,
        "is_host": True
    })
    
    result = get_game_status_service(db, game.id, player.id)
    
    assert result.deck.remaining == 0
    assert result.discard.count == 0
    assert result.discard.top is None
    assert result.hand is None
    assert result.secrets is None