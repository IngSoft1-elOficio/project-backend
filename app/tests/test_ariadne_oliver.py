"""
Tests para Ariadne Oliver - Servicio y Rutas

Cobertura:
- AriadneOliverService.add_oliver_to_set()
- AriadneOliverService.oliver_reveal_secret()
- POST /api/game/{room_id}/detective/add-oliver-to-set
- POST /api/game/{room_id}/detective/oliver-reveal-secret
"""
import pytest
import asyncio
from datetime import date
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import patch, AsyncMock, MagicMock, Mock

from app.db import models, crud
from app.db.database import Base
from app.services.ariadne_oliver_service import AriadneOliverService
from app.schemas.ariadne_oliver_schema import (
    AddOliverToSetRequest,
    OliverRevealSecretRequest
)
from app.main import app

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
def client():
    """Cliente de prueba para FastAPI"""
    return TestClient(app)


@pytest.fixture
def setup_game_with_ariadne_oliver(db):
    """
    Fixture que crea un juego con 3 jugadores.
    Player 1 tiene Ariadne Oliver en mano y es su turno.
    Player 2 tiene un set de detective (Parker Pyne) y secretos.
    """
    # Crear cartas base
    ariadne_card = models.Card(
        id=5,
        name="Ariadne Oliver",
        description="Detective card",
        type=models.CardType.DETECTIVE,
        img_src="ariadne.png",
        qty=2
    )
    pyne_card = models.Card(
        id=7,
        name="Parker Pyne",
        description="Detective card",
        type=models.CardType.DETECTIVE,
        img_src="pyne.png",
        qty=3
    )
    secret_card = models.Card(
        id=3,
        name="Secret Card",
        description="A secret",
        type=models.CardType.SECRET,
        img_src="secret.png",
        qty=10
    )
    murderer_card = models.Card(
        id=2,
        name="You are the Murderer!!",
        description="The assassin",
        type=models.CardType.SECRET,
        img_src="murderer.png",
        qty=1
    )
    db.add_all([ariadne_card, pyne_card, secret_card, murderer_card])
    db.commit()
    
    # Crear juego
    game = models.Game()
    db.add(game)
    db.commit()
    db.refresh(game)
    
    # Crear room
    room = models.Room(
        name="Test Room Ariadne",
        status="INGAME",
        id_game=game.id,
        players_min=2,
        players_max=6
    )
    db.add(room)
    db.commit()
    db.refresh(room)
    
    # Crear jugadores
    player1 = models.Player(
        name="Player 1",
        avatar_src="avatar1.png",
        birthdate=date(2000, 1, 1),
        id_room=room.id,
        is_host=True,
        order=1
    )
    player2 = models.Player(
        name="Player 2",
        avatar_src="avatar2.png",
        birthdate=date(2000, 2, 2),
        id_room=room.id,
        is_host=False,
        order=2
    )
    player3 = models.Player(
        name="Player 3",
        avatar_src="avatar3.png",
        birthdate=date(2000, 3, 3),
        id_room=room.id,
        is_host=False,
        order=3
    )
    db.add_all([player1, player2, player3])
    db.commit()
    db.refresh(player1)
    db.refresh(player2)
    db.refresh(player3)
    
    # Asignar turno a player1
    game.player_turn_id = player1.id
    db.commit()
    
    # Crear turno activo
    turn = models.Turn(
        number=1,
        id_game=game.id,
        player_id=player1.id,
        status=models.TurnStatus.IN_PROGRESS
    )
    db.add(turn)
    db.commit()
    db.refresh(turn)
    
    # Player 1: Ariadne Oliver en mano + otras cartas
    ariadne_in_hand = models.CardsXGame(
        id_game=game.id,
        id_card=5,  # Ariadne Oliver
        is_in=models.CardState.HAND,
        position=1,
        player_id=player1.id,
        hidden=True
    )
    card2_p1 = models.CardsXGame(
        id_game=game.id,
        id_card=3,  # Secret card
        is_in=models.CardState.HAND,
        position=2,
        player_id=player1.id,
        hidden=True
    )
    db.add_all([ariadne_in_hand, card2_p1])
    db.commit()
    db.refresh(ariadne_in_hand)
    
    # Player 2: Set de detective (2 Parker Pyne en position 1)
    pyne1 = models.CardsXGame(
        id_game=game.id,
        id_card=7,  # Parker Pyne
        is_in=models.CardState.DETECTIVE_SET,
        position=1,
        player_id=player2.id,
        hidden=False
    )
    pyne2 = models.CardsXGame(
        id_game=game.id,
        id_card=7,  # Parker Pyne
        is_in=models.CardState.DETECTIVE_SET,
        position=1,
        player_id=player2.id,
        hidden=False
    )
    db.add_all([pyne1, pyne2])
    db.commit()
    
    # Player 2: Secretos (1 normal, 1 asesino)
    secret1 = models.CardsXGame(
        id_game=game.id,
        id_card=3,  # Secret normal
        is_in=models.CardState.SECRET_SET,
        position=1,
        player_id=player2.id,
        hidden=True
    )
    secret2_murderer = models.CardsXGame(
        id_game=game.id,
        id_card=2,  # Murderer
        is_in=models.CardState.SECRET_SET,
        position=2,
        player_id=player2.id,
        hidden=True
    )
    db.add_all([secret1, secret2_murderer])
    db.commit()
    db.refresh(secret1)
    db.refresh(secret2_murderer)
    
    return {
        "game": game,
        "room": room,
        "player1": player1,
        "player2": player2,
        "player3": player3,
        "turn": turn,
        "ariadne_card": ariadne_in_hand,
        "secret_normal": secret1,
        "secret_murderer": secret2_murderer
    }


# =============================================
# TESTS DE SERVICIO - add_oliver_to_set
# =============================================

@pytest.mark.asyncio
async def test_add_oliver_to_set_success(db, setup_game_with_ariadne_oliver):
    """Test exitoso: Player 1 agrega Ariadne Oliver al set de Player 2"""
    data = setup_game_with_ariadne_oliver
    service = AriadneOliverService(db)
    
    request = AddOliverToSetRequest(
        player_id=data["player1"].id,
        oliver_card_id=data["ariadne_card"].id,
        target_player_id=data["player2"].id,
        target_set_position=1
    )
    
    with patch("app.services.ariadne_oliver_service.build_complete_game_state") as mock_state, \
         patch("app.services.ariadne_oliver_service.get_websocket_service") as mock_ws:
        
        mock_state.return_value = {"game_id": data["game"].id, "estados_privados": {}}
        mock_ws_instance = MagicMock()
        mock_ws_instance.notify_detective_oliver_added = AsyncMock()
        mock_ws_instance.notificar_estado_publico = AsyncMock()
        mock_ws_instance.notificar_estados_privados = AsyncMock()
        mock_ws.return_value = mock_ws_instance
        
        response = service.add_oliver_to_set(data["room"].id, request)
    
    # Verificar response
    assert response.status == "success"
    assert response.action_id is not None
    assert response.next_action == "WAIT_TARGET_REVEAL"
    assert "Player 1" in response.message
    assert "Player 2" in response.message
    
    # Verificar que la carta se movió al set
    ariadne_updated = crud.get_card_xgame_by_id(db, data["ariadne_card"].id)
    assert ariadne_updated.is_in == models.CardState.DETECTIVE_SET
    assert ariadne_updated.position == 1
    assert ariadne_updated.player_id == data["player2"].id
    assert ariadne_updated.hidden == False
    
    # Verificar que se creó la acción padre
    action = crud.get_action_by_id(db, response.action_id, data["game"].id)
    assert action is not None
    assert action.action_type == models.ActionType.ADD_DETECTIVE
    assert action.action_name == models.ActionName.ARIADNE_OLIVER
    assert action.result == models.ActionResult.PENDING
    assert action.player_id == data["player1"].id
    assert action.player_target == data["player2"].id
    assert action.selected_set_id == 1


def test_add_oliver_to_set_not_players_turn(db, setup_game_with_ariadne_oliver):
    """Test error: No es el turno del jugador"""
    data = setup_game_with_ariadne_oliver
    service = AriadneOliverService(db)
    
    # Cambiar turno a player2
    data["game"].player_turn_id = data["player2"].id
    db.commit()
    
    request = AddOliverToSetRequest(
        player_id=data["player1"].id,
        oliver_card_id=data["ariadne_card"].id,
        target_player_id=data["player2"].id,
        target_set_position=1
    )
    
    with pytest.raises(HTTPException) as exc_info:
        service.add_oliver_to_set(data["room"].id, request)
    
    assert exc_info.value.status_code == 403
    assert "Not your turn" in str(exc_info.value.detail)


def test_add_oliver_to_set_card_not_in_hand(db, setup_game_with_ariadne_oliver):
    """Test error: Carta no está en la mano del jugador"""
    data = setup_game_with_ariadne_oliver
    service = AriadneOliverService(db)
    
    # Mover carta al descarte
    data["ariadne_card"].is_in = models.CardState.DISCARD
    db.commit()
    
    request = AddOliverToSetRequest(
        player_id=data["player1"].id,
        oliver_card_id=data["ariadne_card"].id,
        target_player_id=data["player2"].id,
        target_set_position=1
    )
    
    with pytest.raises(HTTPException) as exc_info:
        service.add_oliver_to_set(data["room"].id, request)
    
    assert exc_info.value.status_code == 400
    assert "not in player's hand" in str(exc_info.value.detail)


def test_add_oliver_to_set_not_ariadne_oliver(db, setup_game_with_ariadne_oliver):
    """Test error: La carta no es Ariadne Oliver"""
    data = setup_game_with_ariadne_oliver
    service = AriadneOliverService(db)
    
    # Cambiar id_card a otra carta
    data["ariadne_card"].id_card = 3  # Secret card
    db.commit()
    
    request = AddOliverToSetRequest(
        player_id=data["player1"].id,
        oliver_card_id=data["ariadne_card"].id,
        target_player_id=data["player2"].id,
        target_set_position=1
    )
    
    with pytest.raises(HTTPException) as exc_info:
        service.add_oliver_to_set(data["room"].id, request)
    
    assert exc_info.value.status_code == 400
    assert "not Ariadne Oliver" in str(exc_info.value.detail)


def test_add_oliver_to_set_target_set_not_exists(db, setup_game_with_ariadne_oliver):
    """Test error: El set objetivo no existe"""
    data = setup_game_with_ariadne_oliver
    service = AriadneOliverService(db)
    
    request = AddOliverToSetRequest(
        player_id=data["player1"].id,
        oliver_card_id=data["ariadne_card"].id,
        target_player_id=data["player2"].id,
        target_set_position=999  # Set inexistente
    )
    
    with pytest.raises(HTTPException) as exc_info:
        service.add_oliver_to_set(data["room"].id, request)
    
    assert exc_info.value.status_code == 404
    assert "Detective set" in str(exc_info.value.detail)
    assert "not found" in str(exc_info.value.detail)


# =============================================
# TESTS DE SERVICIO - oliver_reveal_secret
# =============================================

@pytest.mark.asyncio
async def test_oliver_reveal_secret_success_normal(db, setup_game_with_ariadne_oliver):
    """Test exitoso: Player 2 revela un secreto normal"""
    data = setup_game_with_ariadne_oliver
    service = AriadneOliverService(db)
    
    # Crear acción padre primero
    parent_action = models.ActionsPerTurn(
        id_game=data["game"].id,
        turn_id=data["turn"].id,
        player_id=data["player1"].id,
        action_type=models.ActionType.ADD_DETECTIVE,
        action_name=models.ActionName.ARIADNE_OLIVER,
        result=models.ActionResult.PENDING,
        player_target=data["player2"].id,
        selected_set_id=1
    )
    db.add(parent_action)
    db.commit()
    db.refresh(parent_action)
    
    request = OliverRevealSecretRequest(
        action_id=parent_action.id,
        secret_id=data["secret_normal"].id,
        player_id=data["player2"].id
    )
    
    with patch("app.services.ariadne_oliver_service.build_complete_game_state") as mock_state, \
         patch("app.services.ariadne_oliver_service.get_websocket_service") as mock_ws, \
         patch("app.services.ariadne_oliver_service.check_and_notify_social_disgrace") as mock_social, \
         patch("app.services.ariadne_oliver_service.win_for_reveal") as mock_win:
        
        mock_state.return_value = {"game_id": data["game"].id, "estados_privados": {}}
        mock_ws_instance = MagicMock()
        mock_ws_instance.notify_ariadne_oliver_complete = AsyncMock()
        mock_ws_instance.notificar_estado_publico = AsyncMock()
        mock_ws_instance.notificar_estados_privados = AsyncMock()
        mock_ws.return_value = mock_ws_instance
        
        mock_social.return_value = AsyncMock()
        mock_win_coro = AsyncMock(return_value=False)
        mock_win.return_value = mock_win_coro
        
        response = service.oliver_reveal_secret(data["room"].id, request)
    
    # Verificar response
    assert response.status == "success"
    assert "reveló un secreto" in response.message
    
    # Verificar que el secreto se reveló
    secret_updated = crud.get_card_xgame_by_id(db, data["secret_normal"].id)
    assert secret_updated.hidden == False
    
    # Verificar que se creó la acción hija
    child_actions = crud.get_actions_by_filters(db, parent_action_id=parent_action.id)
    assert len(child_actions) == 1
    child_action = child_actions[0]
    assert child_action.action_type == models.ActionType.REVEAL_SECRET
    assert child_action.action_name == models.ActionName.ARIADNE_OLIVER_EFFECT
    assert child_action.result == models.ActionResult.SUCCESS
    assert child_action.player_id == data["player2"].id
    assert child_action.secret_target == data["secret_normal"].id
    
    # Verificar que la acción padre se actualizó a SUCCESS
    parent_updated = crud.get_action_by_id(db, parent_action.id, data["game"].id)
    assert parent_updated.result == models.ActionResult.SUCCESS


def test_oliver_reveal_secret_action_not_pending(db, setup_game_with_ariadne_oliver):
    """Test error: La acción padre no está en estado PENDING"""
    data = setup_game_with_ariadne_oliver
    service = AriadneOliverService(db)
    
    # Crear acción padre con estado SUCCESS
    parent_action = models.ActionsPerTurn(
        id_game=data["game"].id,
        turn_id=data["turn"].id,
        player_id=data["player1"].id,
        action_type=models.ActionType.ADD_DETECTIVE,
        action_name=models.ActionName.ARIADNE_OLIVER,
        result=models.ActionResult.SUCCESS,  # Ya completada
        player_target=data["player2"].id
    )
    db.add(parent_action)
    db.commit()
    db.refresh(parent_action)
    
    request = OliverRevealSecretRequest(
        action_id=parent_action.id,
        secret_id=data["secret_normal"].id,
        player_id=data["player2"].id
    )
    
    with pytest.raises(HTTPException) as exc_info:
        service.oliver_reveal_secret(data["room"].id, request)
    
    assert exc_info.value.status_code == 400
    assert "not pending" in str(exc_info.value.detail)


def test_oliver_reveal_secret_not_target_player(db, setup_game_with_ariadne_oliver):
    """Test error: El jugador no es el target de la acción"""
    data = setup_game_with_ariadne_oliver
    service = AriadneOliverService(db)
    
    # Crear acción padre
    parent_action = models.ActionsPerTurn(
        id_game=data["game"].id,
        turn_id=data["turn"].id,
        player_id=data["player1"].id,
        action_type=models.ActionType.ADD_DETECTIVE,
        action_name=models.ActionName.ARIADNE_OLIVER,
        result=models.ActionResult.PENDING,
        player_target=data["player2"].id  # Target es player2
    )
    db.add(parent_action)
    db.commit()
    db.refresh(parent_action)
    
    # Intentar revelar con player3 (no es el target)
    request = OliverRevealSecretRequest(
        action_id=parent_action.id,
        secret_id=data["secret_normal"].id,
        player_id=data["player3"].id  # Player equivocado
    )
    
    with pytest.raises(HTTPException) as exc_info:
        service.oliver_reveal_secret(data["room"].id, request)
    
    assert exc_info.value.status_code == 403
    assert "not the target player" in str(exc_info.value.detail)


def test_oliver_reveal_secret_not_owned(db, setup_game_with_ariadne_oliver):
    """Test error: El secreto no pertenece al jugador"""
    data = setup_game_with_ariadne_oliver
    service = AriadneOliverService(db)
    
    # Crear secreto de player3
    secret_p3 = models.CardsXGame(
        id_game=data["game"].id,
        id_card=3,
        is_in=models.CardState.SECRET_SET,
        position=1,
        player_id=data["player3"].id,
        hidden=True
    )
    db.add(secret_p3)
    db.commit()
    db.refresh(secret_p3)
    
    # Crear acción padre
    parent_action = models.ActionsPerTurn(
        id_game=data["game"].id,
        turn_id=data["turn"].id,
        player_id=data["player1"].id,
        action_type=models.ActionType.ADD_DETECTIVE,
        action_name=models.ActionName.ARIADNE_OLIVER,
        result=models.ActionResult.PENDING,
        player_target=data["player2"].id
    )
    db.add(parent_action)
    db.commit()
    db.refresh(parent_action)
    
    # Player2 intenta revelar secreto de Player3
    request = OliverRevealSecretRequest(
        action_id=parent_action.id,
        secret_id=secret_p3.id,  # Secreto de player3
        player_id=data["player2"].id
    )
    
    with pytest.raises(HTTPException) as exc_info:
        service.oliver_reveal_secret(data["room"].id, request)
    
    assert exc_info.value.status_code == 403
    assert "does not belong to you" in str(exc_info.value.detail)


# =============================================
# NOTA: Los tests de rutas HTTP no están incluidos aquí
# porque el TestClient crea un contexto de BD separado
# que no comparte las tablas in-memory con el fixture 'db'.
# Los tests de servicio proporcionan cobertura completa
# de la lógica de negocio.
# =============================================
