"""
Tests para la funcionalidad Not So Fast (NSF)

Cubre:
- not_so_fast_service.py: Validaciones y lógica de negocio
- routes/not_so_fast.py: Endpoint /start-action
- Schemas: StartActionRequest, StartActionResponse
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import date, datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from fastapi import HTTPException

from app.db import models, crud
from app.db.database import Base
from app.db.models import CardState, CardType, ActionType, ActionName, ActionResult
from app.services.not_so_fast_service import NotSoFastService
from app.schemas.not_so_fast_schema import (
    StartActionRequest,
    StartActionResponse,
    AdditionalData
)

# Configuración de BD en memoria para tests
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# BD separada para los tests de endpoint (con StaticPool para persistencia entre llamadas)
ENDPOINT_DB_URL = "sqlite://"
endpoint_engine = create_engine(
    ENDPOINT_DB_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
EndpointTestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=endpoint_engine)


@pytest.fixture(scope="function")
def db():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    yield db
    db.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def test_client():
    """Create a test client for the FastAPI app with persistent DB"""
    from app.main import app
    from app.routes.not_so_fast import get_db
    
    Base.metadata.create_all(bind=endpoint_engine)
    
    def override_get_db():
        try:
            db = EndpointTestingSessionLocal()
            yield db
        finally:
            db.close()
    
    app.dependency_overrides[get_db] = override_get_db
    
    yield TestClient(app)
    
    Base.metadata.drop_all(bind=endpoint_engine)
    app.dependency_overrides.clear()


@pytest.fixture
def game_setup(db):
    """Fixture que crea un juego básico con 4 jugadores y cartas"""
    # Crear juego
    game = crud.create_game(db, {})
    room = crud.create_room(db, {
        "name": "Test Room",
        "status": "INGAME",
        "id_game": game.id
    })
    
    # Crear 4 jugadores
    players = []
    for i in range(1, 5):
        player = crud.create_player(db, {
            "name": f"Player {i}",
            "avatar_src": f"avatar{i}.png",
            "birthdate": date(2000, 1, i),
            "id_room": room.id,
            "is_host": (i == 1)
        })
        players.append(player)
    
    # Actualizar game con player_turn
    game.player_turn_id = players[0].id
    db.commit()
    
    # Crear turno activo para player 1
    turn = models.Turn(
        number=1,
        id_game=game.id,
        player_id=players[0].id,
        status=models.TurnStatus.IN_PROGRESS
    )
    db.add(turn)
    db.commit()
    db.refresh(turn)
    
    # Crear cartas de prueba
    cards = {}
    
    # Cartas EVENT
    cards["point_suspicions"] = models.Card(
        id=101, name="Point your suspicions", type=models.CardType.EVENT,
        description="Event card", img_src="/img.png", qty=1
    )
    cards["cards_off_table"] = models.Card(
        id=24, name="Cards off the table", type=models.CardType.EVENT,
        description="Event card", img_src="/img.png", qty=1
    )
    cards["blackmailed"] = models.Card(
        id=14, name="Blackmailed", type=models.CardType.EVENT,
        description="Event card", img_src="/img.png", qty=1
    )
    
    # Cartas DETECTIVE
    cards["marple"] = models.Card(
        id=1, name="Miss Marple", type=models.CardType.DETECTIVE,
        description="Detective", img_src="/img.png", qty=3
    )
    cards["poirot"] = models.Card(
        id=2, name="Hercule Poirot", type=models.CardType.DETECTIVE,
        description="Detective", img_src="/img.png", qty=3
    )
    cards["tommy"] = models.Card(
        id=8, name="Tommy Beresford", type=models.CardType.DETECTIVE,
        description="Detective", img_src="/img.png", qty=2
    )
    cards["tuppence"] = models.Card(
        id=10, name="Tuppence Beresford", type=models.CardType.DETECTIVE,
        description="Detective", img_src="/img.png", qty=2
    )
    cards["harley"] = models.Card(
        id=4, name="Harley Quin", type=models.CardType.DETECTIVE,
        description="Wildcard", img_src="/img.png", qty=2
    )
    cards["oliver"] = models.Card(
        id=5, name="Ariadne Oliver", type=models.CardType.DETECTIVE,
        description="Special detective", img_src="/img.png", qty=2
    )
    
    # Carta NSF
    cards["nsf"] = models.Card(
        id=13, name="Not So Fast", type=models.CardType.INSTANT,
        description="Counter card", img_src="/img.png", qty=4
    )
    
    for card in cards.values():
        db.add(card)
    db.commit()
    
    return {
        "game": game,
        "room": room,
        "players": players,
        "turn": turn,
        "cards": cards,
        "db": db
    }


# =============================
# TESTS DE VALIDACIÓN
# =============================

def test_validate_event_action_success(game_setup):
    """Test validar acción EVENT correcta"""
    db = game_setup["db"]
    player = game_setup["players"][0]
    game = game_setup["game"]
    point_card = game_setup["cards"]["point_suspicions"]
    
    # Agregar carta a la mano del jugador
    card_entry = crud.assign_card_to_player(
        db, game.id, point_card.id, player.id, 1
    )
    crud.move_card(db, point_card.id, game.id, models.CardState.HAND, 1)
    card_entry.player_id = player.id
    db.commit()
    db.refresh(card_entry)
    
    # Crear servicio y validar
    service = NotSoFastService(db)
    
    # No debería lanzar excepción
    service._validate_action(
        game_id=game.id,
        player_id=player.id,
        card_ids=[card_entry.id],
        action_type="EVENT",
        set_position=None
    )


def test_validate_event_action_multiple_cards_fails(game_setup):
    """Test validar acción EVENT con múltiples cartas (debe fallar)"""
    db = game_setup["db"]
    player = game_setup["players"][0]
    game = game_setup["game"]
    
    service = NotSoFastService(db)
    
    with pytest.raises(HTTPException) as exc_info:
        service._validate_action(
            game_id=game.id,
            player_id=player.id,
            card_ids=[1, 2],  # 2 cartas
            action_type="EVENT",
            set_position=None
        )
    
    assert exc_info.value.status_code == 400
    assert "exactly 1 card" in exc_info.value.detail


def test_validate_event_not_in_hand_fails(game_setup):
    """Test validar acción EVENT con carta que no está en mano"""
    db = game_setup["db"]
    player = game_setup["players"][0]
    game = game_setup["game"]
    point_card = game_setup["cards"]["point_suspicions"]
    
    # Carta en DECK, no en HAND
    card_entry = models.CardsXGame(
        id_game=game.id,
        id_card=point_card.id,
        player_id=player.id,
        is_in=CardState.DECK,
        position=1,
        hidden=True
    )
    db.add(card_entry)
    db.commit()
    db.refresh(card_entry)
    
    service = NotSoFastService(db)
    
    with pytest.raises(HTTPException) as exc_info:
        service._validate_action(
            game_id=game.id,
            player_id=player.id,
            card_ids=[card_entry.id],
            action_type="EVENT",
            set_position=None
        )
    
    assert exc_info.value.status_code == 400
    assert "not in player's hand" in exc_info.value.detail


def test_validate_create_set_success(game_setup):
    """Test validar acción CREATE_SET correcta"""
    db = game_setup["db"]
    player = game_setup["players"][0]
    game = game_setup["game"]
    marple = game_setup["cards"]["marple"]
    poirot = game_setup["cards"]["poirot"]
    
    # Agregar 2 cartas detective a la mano
    card1 = crud.assign_card_to_player(db, game.id, marple.id, player.id, 1)
    card1.is_in = models.CardState.HAND
    card2 = crud.assign_card_to_player(db, game.id, poirot.id, player.id, 2)
    card2.is_in = models.CardState.HAND
    db.commit()
    
    service = NotSoFastService(db)
    
    # No debería lanzar excepción
    service._validate_action(
        game_id=game.id,
        player_id=player.id,
        card_ids=[card1.id, card2.id],
        action_type="CREATE_SET",
        set_position=None
    )


def test_validate_create_set_one_card_fails(game_setup):
    """Test validar CREATE_SET con solo 1 carta (debe fallar)"""
    db = game_setup["db"]
    player = game_setup["players"][0]
    game = game_setup["game"]
    
    service = NotSoFastService(db)
    
    with pytest.raises(HTTPException) as exc_info:
        service._validate_action(
            game_id=game.id,
            player_id=player.id,
            card_ids=[1],  # Solo 1 carta
            action_type="CREATE_SET",
            set_position=None
        )
    
    assert exc_info.value.status_code == 400
    assert "at least 2 cards" in exc_info.value.detail


def test_validate_add_to_set_success(game_setup):
    """Test validar acción ADD_TO_SET correcta"""
    db = game_setup["db"]
    player = game_setup["players"][0]
    game = game_setup["game"]
    marple = game_setup["cards"]["marple"]
    poirot = game_setup["cards"]["poirot"]
    
    # Crear un set existente
    card1 = crud.assign_card_to_player(db, game.id, marple.id, player.id, 1)
    card1.is_in = models.CardState.DETECTIVE_SET
    card1.position = 1
    db.commit()
    
    # Carta para agregar al set
    card2 = crud.assign_card_to_player(db, game.id, poirot.id, player.id, 2)
    card2.is_in = models.CardState.HAND
    db.commit()
    
    service = NotSoFastService(db)
    
    # No debería lanzar excepción
    service._validate_action(
        game_id=game.id,
        player_id=player.id,
        card_ids=[card2.id],
        action_type="ADD_TO_SET",
        set_position=1
    )


def test_validate_add_to_set_harley_fails(game_setup):
    """Test validar ADD_TO_SET con Harley Quin (debe fallar)"""
    db = game_setup["db"]
    player = game_setup["players"][0]
    game = game_setup["game"]
    harley = game_setup["cards"]["harley"]
    
    # Carta Harley en mano
    card_entry = crud.assign_card_to_player(db, game.id, harley.id, player.id, 1)
    card_entry.is_in = models.CardState.HAND
    db.commit()
    
    service = NotSoFastService(db)
    
    with pytest.raises(HTTPException) as exc_info:
        service._validate_action(
            game_id=game.id,
            player_id=player.id,
            card_ids=[card_entry.id],
            action_type="ADD_TO_SET",
            set_position=1
        )
    
    assert exc_info.value.status_code == 400
    assert "Harley Quin" in exc_info.value.detail


def test_validate_add_to_set_oliver_no_position(game_setup):
    """Test validar ADD_TO_SET con Ariadne Oliver sin setPosition (debe pasar)"""
    db = game_setup["db"]
    player = game_setup["players"][0]
    game = game_setup["game"]
    oliver = game_setup["cards"]["oliver"]
    
    # Carta Oliver en mano
    card_entry = crud.assign_card_to_player(db, game.id, oliver.id, player.id, 1)
    card_entry.is_in = models.CardState.HAND
    db.commit()
    
    service = NotSoFastService(db)
    
    # No debería lanzar excepción (Oliver es especial)
    service._validate_action(
        game_id=game.id,
        player_id=player.id,
        card_ids=[card_entry.id],
        action_type="ADD_TO_SET",
        set_position=None  # Sin posición
    )


# =============================
# TESTS DE CANCELABILIDAD
# =============================

def test_event_cancelable_point_suspicions(game_setup):
    """Test que Point your suspicions es cancelable"""
    db = game_setup["db"]
    game = game_setup["game"]
    point_card = game_setup["cards"]["point_suspicions"]
    
    # Agregar carta al juego
    card_entry = crud.assign_card_to_player(db, game.id, point_card.id, None, 1)
    db.commit()
    
    service = NotSoFastService(db)
    
    is_cancelable = service._is_event_cancellable([card_entry.id], game.id)
    assert is_cancelable is True


def test_event_not_cancelable_cards_off_table(game_setup):
    """Test que Cards off the table NO es cancelable"""
    db = game_setup["db"]
    game = game_setup["game"]
    cards_off = game_setup["cards"]["cards_off_table"]
    
    # Agregar carta al juego
    card_entry = crud.assign_card_to_player(db, game.id, cards_off.id, None, 1)
    db.commit()
    
    service = NotSoFastService(db)
    
    is_cancelable = service._is_event_cancellable([card_entry.id], game.id)
    assert is_cancelable is False


def test_create_set_cancelable_without_beresfords(game_setup):
    """Test que crear set sin hermanos Beresford es cancelable"""
    db = game_setup["db"]
    game = game_setup["game"]
    marple = game_setup["cards"]["marple"]
    poirot = game_setup["cards"]["poirot"]
    
    # Set sin Tommy ni Tuppence
    card1 = crud.assign_card_to_player(db, game.id, marple.id, None, 1)
    card2 = crud.assign_card_to_player(db, game.id, poirot.id, None, 2)
    db.commit()
    
    service = NotSoFastService(db)
    
    is_cancelable = service._is_create_set_cancellable([card1.id, card2.id], game.id)
    assert is_cancelable is True


def test_create_set_not_cancelable_with_both_beresfords(game_setup):
    """Test que crear set con Tommy Y Tuppence NO es cancelable"""
    db = game_setup["db"]
    game = game_setup["game"]
    tommy = game_setup["cards"]["tommy"]
    tuppence = game_setup["cards"]["tuppence"]
    
    # Set con ambos hermanos
    card1 = crud.assign_card_to_player(db, game.id, tommy.id, None, 1)
    card2 = crud.assign_card_to_player(db, game.id, tuppence.id, None, 2)
    db.commit()
    
    service = NotSoFastService(db)
    
    is_cancelable = service._is_create_set_cancellable([card1.id, card2.id], game.id)
    assert is_cancelable is False


def test_add_to_set_not_cancelable_completing_beresfords(game_setup):
    """Test que agregar Tommy/Tuppence completando hermanos NO es cancelable"""
    db = game_setup["db"]
    player = game_setup["players"][0]
    game = game_setup["game"]
    tommy = game_setup["cards"]["tommy"]
    tuppence = game_setup["cards"]["tuppence"]
    
    # Set existente con Tommy
    existing_card = crud.assign_card_to_player(db, game.id, tommy.id, player.id, 1)
    existing_card.is_in = models.CardState.DETECTIVE_SET
    existing_card.position = 1
    db.commit()
    
    # Agregar Tuppence (completa hermanos)
    new_card = crud.assign_card_to_player(db, game.id, tuppence.id, player.id, 2)
    db.commit()
    
    service = NotSoFastService(db)
    
    is_cancelable = service._is_add_to_set_cancellable(
        [new_card.id], 1, game.id, player.id
    )
    assert is_cancelable is False


# =============================
# TESTS CHEQUEO NSF
# =============================

def test_check_players_have_nsf_true(game_setup):
    """Test que detecta cuando hay jugadores con NSF"""
    db = game_setup["db"]
    game = game_setup["game"]
    player1 = game_setup["players"][0]
    player2 = game_setup["players"][1]
    nsf_card = game_setup["cards"]["nsf"]
    
    # Player 2 tiene NSF en mano
    card_entry = crud.assign_card_to_player(db, game.id, nsf_card.id, player2.id, 1)
    card_entry.is_in = models.CardState.HAND
    db.commit()
    
    service = NotSoFastService(db)
    
    has_nsf = service._check_players_have_nsf(game.id, player1.id)
    assert has_nsf is True


def test_check_players_have_nsf_false(game_setup):
    """Test que detecta cuando NO hay jugadores con NSF"""
    db = game_setup["db"]
    game = game_setup["game"]
    player1 = game_setup["players"][0]
    
    service = NotSoFastService(db)
    
    has_nsf = service._check_players_have_nsf(game.id, player1.id)
    assert has_nsf is False


def test_check_players_exclude_active_player(game_setup):
    """Test que excluye al jugador activo del chequeo NSF"""
    db = game_setup["db"]
    game = game_setup["game"]
    player1 = game_setup["players"][0]
    nsf_card = game_setup["cards"]["nsf"]
    
    # Solo player1 (activo) tiene NSF
    card_entry = crud.assign_card_to_player(db, game.id, nsf_card.id, player1.id, 1)
    card_entry.is_in = models.CardState.HAND
    db.commit()
    
    service = NotSoFastService(db)
    
    # No debería contar porque es el jugador activo
    has_nsf = service._check_players_have_nsf(game.id, player1.id)
    assert has_nsf is False


# =============================
# TESTS SERVICIO COMPLETO
# =============================


def test_start_action_not_cancelable_no_nsf_window(game_setup):
    """Test start_action con acción cancelable pero sin jugadores con NSF"""
    db = game_setup["db"]
    game = game_setup["game"]
    room = game_setup["room"]
    player1 = game_setup["players"][0]
    point_card = game_setup["cards"]["point_suspicions"]
    
    # Player1 tiene Point your suspicions (cancelable)
    card1 = crud.assign_card_to_player(db, game.id, point_card.id, player1.id, 1)
    card1.is_in = models.CardState.HAND
    db.commit()
    
    # Nadie tiene NSF
    
    service = NotSoFastService(db)
    
    request = StartActionRequest(
        playerId=player1.id,
        cardIds=[card1.id],
        additionalData=AdditionalData(
            actionType="EVENT",
            setPosition=None
        )
    )
    
    response = service.start_action(room.id, request)
    
    # Verificar que NO se activa NSF
    assert response.actionId is not None
    assert response.actionNSFId is None
    assert response.cancellable is False
    assert response.timeRemaining is None
    
    # Verificar que la intención se marcó como CONTINUE
    intention = crud.get_action_by_id(db, response.actionId)
    assert intention.result == models.ActionResult.CONTINUE


def test_start_action_cards_off_table_not_cancelable(game_setup):
    """Test start_action con Cards off the table (inherentemente no cancelable)"""
    db = game_setup["db"]
    game = game_setup["game"]
    room = game_setup["room"]
    player1 = game_setup["players"][0]
    player2 = game_setup["players"][1]
    cards_off = game_setup["cards"]["cards_off_table"]
    nsf_card = game_setup["cards"]["nsf"]
    
    # Player1 tiene Cards off the table
    card1 = crud.assign_card_to_player(db, game.id, cards_off.id, player1.id, 1)
    card1.is_in = models.CardState.HAND
    db.commit()
    
    # Player2 tiene NSF (pero no importa)
    nsf_entry = crud.assign_card_to_player(db, game.id, nsf_card.id, player2.id, 1)
    nsf_entry.is_in = models.CardState.HAND
    db.commit()
    
    service = NotSoFastService(db)
    
    request = StartActionRequest(
        playerId=player1.id,
        cardIds=[card1.id],
        additionalData=AdditionalData(
            actionType="EVENT",
            setPosition=None
        )
    )
    
    response = service.start_action(room.id, request)
    
    # Cards off the table NO es cancelable, aunque haya NSF
    assert response.cancellable is False
    assert response.actionNSFId is None
    
    intention = crud.get_action_by_id(db, response.actionId)
    assert intention.result == models.ActionResult.CONTINUE


def test_start_action_create_set_beresfords(game_setup):
    """Test start_action con CREATE_SET de hermanos Beresford (no cancelable)"""
    db = game_setup["db"]
    game = game_setup["game"]
    room = game_setup["room"]
    player1 = game_setup["players"][0]
    player2 = game_setup["players"][1]
    tommy = game_setup["cards"]["tommy"]
    tuppence = game_setup["cards"]["tuppence"]
    nsf_card = game_setup["cards"]["nsf"]
    
    # Player1 tiene Tommy y Tuppence
    card1 = crud.assign_card_to_player(db, game.id, tommy.id, player1.id, 1)
    card1.is_in = models.CardState.HAND
    card2 = crud.assign_card_to_player(db, game.id, tuppence.id, player1.id, 2)
    card2.is_in = models.CardState.HAND
    db.commit()
    
    # Player2 tiene NSF
    nsf_entry = crud.assign_card_to_player(db, game.id, nsf_card.id, player2.id, 1)
    nsf_entry.is_in = models.CardState.HAND
    db.commit()
    
    service = NotSoFastService(db)
    
    request = StartActionRequest(
        playerId=player1.id,
        cardIds=[card1.id, card2.id],
        additionalData=AdditionalData(
            actionType="CREATE_SET",
            setPosition=None
        )
    )
    
    response = service.start_action(room.id, request)
    
    # Set con hermanos NO es cancelable
    assert response.cancellable is False
    assert response.actionNSFId is None


def test_start_action_not_player_turn_fails(game_setup):
    """Test start_action cuando no es el turno del jugador"""
    db = game_setup["db"]
    room = game_setup["room"]
    player2 = game_setup["players"][1]  # No es su turno
    
    service = NotSoFastService(db)
    
    request = StartActionRequest(
        playerId=player2.id,
        cardIds=[1],
        additionalData=AdditionalData(
            actionType="EVENT",
            setPosition=None
        )
    )
    
    with pytest.raises(HTTPException) as exc_info:
        service.start_action(room.id, request)
    
    assert exc_info.value.status_code == 403
    assert "Not your turn" in exc_info.value.detail


# =============================
# TESTS DE SCHEMA
# =============================

def test_additional_data_schema_validation():
    """Test validación de AdditionalData schema"""
    # Válido con setPosition
    data1 = AdditionalData(actionType="ADD_TO_SET", setPosition=1)
    assert data1.setPosition == 1
    
    # Válido sin setPosition para EVENT
    data2 = AdditionalData(actionType="EVENT", setPosition=None)
    assert data2.setPosition is None
    
    # Válido sin setPosition para CREATE_SET
    data3 = AdditionalData(actionType="CREATE_SET", setPosition=None)
    assert data3.setPosition is None


def test_start_action_request_schema():
    """Test schema StartActionRequest"""
    request = StartActionRequest(
        playerId=5,
        cardIds=[10, 20],
        additionalData=AdditionalData(
            actionType="CREATE_SET",
            setPosition=None
        )
    )
    
    assert request.playerId == 5
    assert len(request.cardIds) == 2
    assert request.additionalData.actionType == "CREATE_SET"


def test_start_action_response_schema():
    """Test schema StartActionResponse"""
    response = StartActionResponse(
        actionId=100,
        actionNSFId=101,
        cancellable=True,
        timeRemaining=5
    )
    
    assert response.actionId == 100
    assert response.actionNSFId == 101
    assert response.cancellable is True
    assert response.timeRemaining == 5
    
    # Response sin NSF
    response2 = StartActionResponse(
        actionId=102,
        actionNSFId=None,
        cancellable=False,
        timeRemaining=None
    )
    
    assert response2.actionNSFId is None
    assert response2.cancellable is False


# ==============================================================================
# TESTS PARA NUEVOS SCHEMAS (PlayNSFRequest, PlayNSFResponse)
# ==============================================================================

def test_play_nsf_request_schema():
    """Test schema PlayNSFRequest para jugar una carta NSF"""
    from app.schemas.not_so_fast_schema import PlayNSFRequest
    
    request = PlayNSFRequest(
        actionId=10,
        playerId=2,
        cardId=150
    )
    
    assert request.actionId == 10
    assert request.playerId == 2
    assert request.cardId == 150


def test_play_nsf_response_schema():
    """Test schema PlayNSFResponse con todos los campos"""
    from app.schemas.not_so_fast_schema import PlayNSFResponse
    
    response = PlayNSFResponse(
        success=True,
        nsfActionId=25,
        nsfStartActionId=24,
        timeRemaining=5,
        message="Player Bob jugó Not So Fast"
    )
    
    assert response.success is True
    assert response.nsfActionId == 25
    assert response.nsfStartActionId == 24
    assert response.timeRemaining == 5
    assert response.message == "Player Bob jugó Not So Fast"


def test_play_nsf_request_validation():
    """Test validación de PlayNSFRequest con valores inválidos"""
    from app.schemas.not_so_fast_schema import PlayNSFRequest
    from pydantic import ValidationError
    
    # Campos faltantes deben fallar
    with pytest.raises(ValidationError):
        PlayNSFRequest(actionId=10)  # Falta playerId y cardId
    
    with pytest.raises(ValidationError):
        PlayNSFRequest(playerId=2, cardId=10)  # Falta actionId


# ==============================================================================
# TESTS PARA SERVICIO play_nsf_card()
# ==============================================================================

def _create_nsf_card_with_id_13(db):
    """Helper: Crea la carta NSF con ID=13 (NOT_SO_FAST_CARD_ID)"""
    # Insertar cartas dummy para que NSF tenga ID=13
    for i in range(1, 13):
        dummy = models.Card(
            id=i,
            name=f"Dummy {i}",
            description="Dummy",
            type="SECRET",
            img_src=f"/dummy{i}.png",
            qty=1
        )
        db.add(dummy)
    
    nsf_card = models.Card(
        id=13,
        name="Not so fast",
        description="NSF",
        type="INSTANT",
        img_src="/nsf.png",
        qty=10
    )
    db.add(nsf_card)
    db.flush()
    return nsf_card


def test_play_nsf_card_success(db):
    """Test: play_nsf_card ejecuta correctamente el flujo completo"""
    # Setup: Crear game, room, players, cards, actions
    game = models.Game(player_turn_id=None)
    db.add(game)
    db.flush()
    
    room = models.Room(
        name="Test Room",
        players_min=2,
        players_max=6,
        status=models.RoomStatus.INGAME,
        id_game=game.id
    )
    db.add(room)
    db.flush()
    
    player = models.Player(
        name="TestPlayer",
        avatar_src="/avatar.jpg",
        birthdate=date(1990, 1, 1),
        id_room=room.id,
        is_host=True,
        order=1
    )
    db.add(player)
    db.flush()
    
    # Crear carta NSF con ID=13
    nsf_card = _create_nsf_card_with_id_13(db)
    
    # Carta NSF en mano del jugador
    card_in_hand = models.CardsXGame(
        id_game=game.id,
        id_card=nsf_card.id,
        is_in=CardState.HAND,
        position=1,
        player_id=player.id,
        hidden=True
    )
    db.add(card_in_hand)
    db.flush()
    
    # Acción XXX (original)
    intention_action = models.ActionsPerTurn(
        id_game=game.id,
        player_id=player.id,
        action_type=ActionType.INIT,
        action_name="Point your suspicions",
        result=ActionResult.PENDING
    )
    db.add(intention_action)
    db.flush()
    
    # Acción YYY (NSF_START)
    nsf_start_action = models.ActionsPerTurn(
        id_game=game.id,
        player_id=player.id,
        action_type=ActionType.INSTANT,
        action_name=ActionName.INSTANT_START,
        result=ActionResult.PENDING,
        triggered_by_action_id=intention_action.id
    )
    db.add(nsf_start_action)
    db.commit()
    
    # Test
    service = NotSoFastService(db)
    nsf_action_id, nsf_start_id, player_name = service.play_nsf_card(
        room_id=room.id,
        action_id=intention_action.id,
        player_id=player.id,
        card_id=card_in_hand.id
    )
    
    # Assert
    assert nsf_action_id is not None
    assert nsf_start_id == nsf_start_action.id
    assert player_name == "TestPlayer"
    
    # Verificar que se creó la acción ZZZ
    nsf_play = crud.get_action_by_id(db, nsf_action_id, game.id)
    assert nsf_play is not None
    assert nsf_play.action_type == ActionType.INSTANT
    assert nsf_play.parent_action_id == nsf_start_action.id
    assert nsf_play.triggered_by_action_id == intention_action.id
    
    # Verificar que YYY tiene action_time_end actualizado
    db.refresh(nsf_start_action)
    assert nsf_start_action.action_time_end is not None


def test_play_nsf_card_not_in_hand(db):
    """Test: play_nsf_card falla si la carta no está en la mano"""
    # Setup
    game = models.Game(player_turn_id=None)
    db.add(game)
    db.flush()
    
    room = models.Room(
        name="Test Room",
        players_min=2,
        players_max=6,
        status=models.RoomStatus.INGAME,
        id_game=game.id
    )
    db.add(room)
    db.flush()
    
    player = models.Player(
        name="TestPlayer",
        avatar_src="/avatar.jpg",
        birthdate=date(1990, 1, 1),
        id_room=room.id,
        is_host=True,
        order=1
    )
    db.add(player)
    db.flush()
    
    nsf_card = _create_nsf_card_with_id_13(db)
    
    # Carta NSF en DISCARD (no en mano)
    card_in_discard = models.CardsXGame(
        id_game=game.id,
        id_card=nsf_card.id,
        is_in=CardState.DISCARD,
        position=1,
        player_id=None,
        hidden=False
    )
    db.add(card_in_discard)
    db.flush()
    
    intention_action = models.ActionsPerTurn(
        id_game=game.id,
        player_id=player.id,
        action_type=ActionType.INIT,
        action_name="Point your suspicions",
        result=ActionResult.PENDING
    )
    db.add(intention_action)
    db.commit()
    
    # Test
    service = NotSoFastService(db)
    
    with pytest.raises(HTTPException) as exc_info:
        service.play_nsf_card(
            room_id=room.id,
            action_id=intention_action.id,
            player_id=player.id,
            card_id=card_in_discard.id
        )
    
    assert exc_info.value.status_code == 400
    assert "not found in player's hand" in exc_info.value.detail


def test_play_nsf_card_no_nsf_window(db):
    """Test: play_nsf_card falla si no hay ventana NSF activa"""
    # Setup
    game = models.Game(player_turn_id=None)
    db.add(game)
    db.flush()
    
    room = models.Room(
        name="Test Room",
        players_min=2,
        players_max=6,
        status=models.RoomStatus.INGAME,
        id_game=game.id
    )
    db.add(room)
    db.flush()
    
    player = models.Player(
        name="TestPlayer",
        avatar_src="/avatar.jpg",
        birthdate=date(1990, 1, 1),
        id_room=room.id,
        is_host=True,
        order=1
    )
    db.add(player)
    db.flush()
    
    nsf_card = _create_nsf_card_with_id_13(db)
    
    card_in_hand = models.CardsXGame(
        id_game=game.id,
        id_card=nsf_card.id,
        is_in=CardState.HAND,
        position=1,
        player_id=player.id,
        hidden=True
    )
    db.add(card_in_hand)
    db.flush()
    
    # Acción XXX sin YYY (sin ventana NSF)
    intention_action = models.ActionsPerTurn(
        id_game=game.id,
        player_id=player.id,
        action_type=ActionType.INIT,
        action_name="Point your suspicions",
        result=ActionResult.PENDING
    )
    db.add(intention_action)
    db.commit()
    
    # Test
    service = NotSoFastService(db)
    
    with pytest.raises(HTTPException) as exc_info:
        service.play_nsf_card(
            room_id=room.id,
            action_id=intention_action.id,
            player_id=player.id,
            card_id=card_in_hand.id
        )
    
    assert exc_info.value.status_code == 400
    assert "NSF window not active" in exc_info.value.detail


def test_play_nsf_card_action_not_found(db):
    """Test: play_nsf_card falla si la acción original no existe"""
    # Setup
    game = models.Game(player_turn_id=None)
    db.add(game)
    db.flush()
    
    room = models.Room(
        name="Test Room",
        players_min=2,
        players_max=6,
        status=models.RoomStatus.INGAME,
        id_game=game.id
    )
    db.add(room)
    db.flush()
    
    player = models.Player(
        name="TestPlayer",
        avatar_src="/avatar.jpg",
        birthdate=date(1990, 1, 1),
        id_room=room.id,
        is_host=True,
        order=1
    )
    db.add(player)
    db.flush()
    
    nsf_card = _create_nsf_card_with_id_13(db)
    
    card_in_hand = models.CardsXGame(
        id_game=game.id,
        id_card=nsf_card.id,
        is_in=CardState.HAND,
        position=1,
        player_id=player.id,
        hidden=True
    )
    db.add(card_in_hand)
    db.commit()
    
    # Test
    service = NotSoFastService(db)
    
    with pytest.raises(HTTPException) as exc_info:
        service.play_nsf_card(
            room_id=room.id,
            action_id=9999,  # Acción que no existe
            player_id=player.id,
            card_id=card_in_hand.id
        )
    
    assert exc_info.value.status_code == 404
    assert "Original action not found" in exc_info.value.detail


# ============================================================================
# TESTS: ENDPOINT POST /instant/not-so-fast
# ============================================================================
# Nota: Los tests de endpoint prueban validaciones HTTP básicas.
# La lógica de negocio completa ya está probada en los tests del servicio.

def test_play_not_so_fast_endpoint_room_not_found(test_client):
    """
    Test: POST /instant/not-so-fast - Room not found
    Precondiciones: Room ID no existe
    Postcondiciones: 404 Not Found
    """
    response = test_client.post(
        "/api/game/999/instant/not-so-fast",
        json={
            "actionId": 1,
            "playerId": 1,
            "cardId": 1
        }
    )
    
    assert response.status_code == 404
    assert "Room not found" in response.json()["detail"]


def test_play_not_so_fast_endpoint_invalid_request(test_client):
    """
    Test: POST /instant/not-so-fast - Invalid request body (missing fields)
    Precondiciones: Request sin campos requeridos
    Postcondiciones: 422 Unprocessable Entity
    """
    response = test_client.post(
        "/api/game/1/instant/not-so-fast",
        json={}  # Missing all required fields
    )
    
    assert response.status_code == 422  # Validation error
    assert "detail" in response.json()


# ============================================================================
# TESTS: ENDPOINT POST /start-action
# ============================================================================
# Nota: Similar a lo anterior, estos tests verifican validaciones HTTP.
# La lógica de negocio está completamente probada en los tests del servicio.

def test_start_action_endpoint_room_not_found(test_client):
    """
    Test: POST /start-action - Room not found
    Precondiciones: Room ID no existe
    Postcondiciones: 404 Not Found
    """
    response = test_client.post(
        "/api/game/999/start-action",
        json={
            "playerId": 1,
            "cardIds": [1, 2],
            "additionalData": {
                "actionType": "EVENT",
                "setPosition": None
            }
        }
    )
    
    assert response.status_code == 404
    assert "Room not found" in response.json()["detail"]


def test_start_action_endpoint_invalid_request(test_client):
    """
    Test: POST /start-action - Invalid request body (missing fields)
    Precondiciones: Request sin campos requeridos
    Postcondiciones: 422 Unprocessable Entity
    """
    response = test_client.post(
        "/api/game/1/start-action",
        json={}  # Missing all required fields
    )
    
    assert response.status_code == 422  # Validation error
    assert "detail" in response.json()
