# app/tests/test_detective_action_service.py
import pytest
from datetime import date
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import models
from app.db.database import Base
from app.services.detective_action_service import DetectiveActionService
from app.schemas.detective_action_schema import DetectiveActionRequest
from app.schemas.detective_set_schema import SetType

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
def setup_game_with_players(db):
    """Fixture que crea un juego con jugadores y turno activo"""
    # Crear juego
    game = models.Game()
    db.add(game)
    db.commit()
    db.refresh(game)
    
    # Crear room
    room = models.Room(
        name="Test Room",
        status="INGAME",
        id_game=game.id,
        players_min=2,
        players_max=4
    )
    db.add(room)
    db.commit()
    db.refresh(room)
    
    # Crear jugadores
    player1 = models.Player(
        name="Ana",
        avatar_src="avatar1.png",
        birthdate=date(2000, 5, 10),
        id_room=room.id,
        is_host=True
    )
    player2 = models.Player(
        name="Luis",
        avatar_src="avatar2.png",
        birthdate=date(1999, 3, 1),
        id_room=room.id,
        is_host=False
    )
    db.add_all([player1, player2])
    db.commit()
    db.refresh(player1)
    db.refresh(player2)
    
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
    
    return {
        "game": game,
        "room": room,
        "player1": player1,  # Owner del set
        "player2": player2,  # Target
        "turn": turn
    }


@pytest.fixture
def setup_detective_cards(db):
    """Fixture que crea cartas detective y secretos"""
    # Crear cartas detective
    poirot = models.Card(
        name="Hercule Poirot",
        description="Famous detective",
        type="DETECTIVE",
        img_src="/assets/cards/poirot.png",
        qty=3
    )
    marple = models.Card(
        name="Miss Marple",
        description="Clever detective",
        type="DETECTIVE",
        img_src="/assets/cards/marple.png",
        qty=3
    )
    pyne = models.Card(
        name="Parker Pyne",
        description="Secret keeper",
        type="DETECTIVE",
        img_src="/assets/cards/pyne.png",
        qty=2
    )
    harley_quin = models.Card(
        name="Harley Quin",
        description="Wildcard",
        type="DETECTIVE",
        img_src="/assets/cards/harley.png",
        qty=1
    )
    
    # Crear cartas secretas
    murderer = models.Card(
        name="You are the Murderer!!",
        description="Secret card",
        type="SECRET",
        img_src="/assets/cards/murderer.png",
        qty=1
    )
    accomplice = models.Card(
        name="You are the Accomplice",
        description="Secret card",
        type="SECRET",
        img_src="/assets/cards/accomplice.png",
        qty=1
    )
    innocent = models.Card(
        name="You are Innocent",
        description="Secret card",
        type="SECRET",
        img_src="/assets/cards/innocent.png",
        qty=6
    )
    
    db.add_all([poirot, marple, pyne, harley_quin, murderer, accomplice, innocent])
    db.commit()
    
    return {
        "poirot": poirot,
        "marple": marple,
        "pyne": pyne,
        "harley_quin": harley_quin,
        "murderer": murderer,
        "accomplice": accomplice,
        "innocent": innocent
    }


# ------------------------------
# TESTS DE VALIDACIÓN
# ------------------------------

def test_get_game_not_found(db):
    """Test que falla si el juego no existe"""
    service = DetectiveActionService(db)
    
    with pytest.raises(HTTPException) as exc_info:
        service._get_game(9999)
    
    assert exc_info.value.status_code == 404
    assert "Game not found" in str(exc_info.value.detail)


def test_get_pending_action_not_found(db, setup_game_with_players):
    """Test que falla si la acción no existe"""
    data = setup_game_with_players
    service = DetectiveActionService(db)
    
    with pytest.raises(HTTPException) as exc_info:
        service._get_pending_action(9999, data["game"].id)
    
    assert exc_info.value.status_code == 404
    assert "Action not found" in str(exc_info.value.detail)


def test_get_pending_action_wrong_game(db, setup_game_with_players):
    """Test que falla si la acción pertenece a otro juego"""
    data = setup_game_with_players
    service = DetectiveActionService(db)
    
    # Crear acción en el juego correcto
    action = models.ActionsPerTurn(
        id_game=data["game"].id,
        turn_id=data["turn"].id,
        player_id=data["player1"].id,
        action_name="play_Poirot_set",
        action_type=models.ActionType.DETECTIVE_SET,
        result=models.ActionResult.PENDING
    )
    db.add(action)
    db.commit()
    db.refresh(action)
    
    # Intentar obtenerla con otro game_id
    with pytest.raises(HTTPException) as exc_info:
        service._get_pending_action(action.id, 9999)
    
    assert exc_info.value.status_code == 400
    assert "does not belong to this game" in str(exc_info.value.detail)


def test_get_pending_action_not_pending(db, setup_game_with_players):
    """Test que falla si la acción no está PENDING"""
    data = setup_game_with_players
    service = DetectiveActionService(db)
    
    # Crear acción ya completada
    action = models.ActionsPerTurn(
        id_game=data["game"].id,
        turn_id=data["turn"].id,
        player_id=data["player1"].id,
        action_name="play_Poirot_set",
        action_type=models.ActionType.DETECTIVE_SET,
        result=models.ActionResult.SUCCESS  # Ya completada
    )
    db.add(action)
    db.commit()
    db.refresh(action)
    
    with pytest.raises(HTTPException) as exc_info:
        service._get_pending_action(action.id, data["game"].id)
    
    assert exc_info.value.status_code == 409
    assert "not pending" in str(exc_info.value.detail)


def test_validate_executor_poirot_wrong_executor(db, setup_game_with_players):
    """Test que falla si el executor no es el owner para Poirot"""
    data = setup_game_with_players
    service = DetectiveActionService(db)
    
    # Poirot: el activo (owner) debe ejecutar
    with pytest.raises(HTTPException) as exc_info:
        service._validate_executor(
            executor_id=data["player2"].id,  # Otro jugador
            owner_id=data["player1"].id,
            set_type=SetType.POIROT,
            target_player_id=data["player2"].id
        )
    
    assert exc_info.value.status_code == 403
    assert "Only the set owner can execute" in str(exc_info.value.detail)


def test_validate_executor_satterthwaite_wrong_executor(db, setup_game_with_players):
    """Test que falla si el executor no es el target para Satterthwaite"""
    data = setup_game_with_players
    service = DetectiveActionService(db)
    
    # Satterthwaite: el target debe ejecutar
    with pytest.raises(HTTPException) as exc_info:
        service._validate_executor(
            executor_id=data["player1"].id,  # Owner
            owner_id=data["player1"].id,
            set_type=SetType.SATTERTHWAITE,
            target_player_id=data["player2"].id
        )
    
    assert exc_info.value.status_code == 403
    assert "Only the target player can execute" in str(exc_info.value.detail)


def test_validate_secret_pyne_cannot_hide_hidden(db, setup_game_with_players, setup_detective_cards):
    """Test que Pyne no puede ocultar secretos ya ocultos"""
    data = setup_game_with_players
    cards = setup_detective_cards
    service = DetectiveActionService(db)
    
    # Crear secreto oculto
    secret = models.CardsXGame(
        id_game=data["game"].id,
        id_card=cards["murderer"].id,
        is_in=models.CardState.SECRET_SET,
        position=1,
        player_id=data["player2"].id,
        hidden=True  # Oculto
    )
    db.add(secret)
    db.commit()
    db.refresh(secret)
    
    with pytest.raises(HTTPException) as exc_info:
        service._validate_secret(secret, SetType.PYNE)
    
    assert exc_info.value.status_code == 400
    assert "can only hide revealed secrets" in str(exc_info.value.detail)


def test_validate_secret_poirot_cannot_reveal_revealed(db, setup_game_with_players, setup_detective_cards):
    """Test que Poirot no puede revelar secretos ya revelados"""
    data = setup_game_with_players
    cards = setup_detective_cards
    service = DetectiveActionService(db)
    
    # Crear secreto revelado
    secret = models.CardsXGame(
        id_game=data["game"].id,
        id_card=cards["murderer"].id,
        is_in=models.CardState.SECRET_SET,
        position=1,
        player_id=data["player2"].id,
        hidden=False  # Revelado
    )
    db.add(secret)
    db.commit()
    db.refresh(secret)
    
    with pytest.raises(HTTPException) as exc_info:
        service._validate_secret(secret, SetType.POIROT)
    
    assert exc_info.value.status_code == 400
    assert "can only reveal hidden secrets" in str(exc_info.value.detail)


# ------------------------------
# TESTS DE EJECUCIÓN - POIROT/MARPLE
# ------------------------------

def test_execute_poirot_reveal_secret(db, setup_game_with_players, setup_detective_cards):
    """Test ejecutar acción de Poirot revelando un secreto"""
    data = setup_game_with_players
    cards = setup_detective_cards
    service = DetectiveActionService(db)
    
    # Crear set de Poirot bajado
    poirot_entry = models.CardsXGame(
        id_game=data["game"].id,
        id_card=cards["poirot"].id,
        is_in=models.CardState.DETECTIVE_SET,
        position=1,
        player_id=data["player1"].id,
        hidden=False
    )
    db.add(poirot_entry)
    db.commit()
    
    # Crear acción PENDING
    action = models.ActionsPerTurn(
        id_game=data["game"].id,
        turn_id=data["turn"].id,
        player_id=data["player1"].id,
        action_name="play_Poirot_set",
        action_type=models.ActionType.DETECTIVE_SET,
        result=models.ActionResult.PENDING
    )
    db.add(action)
    db.commit()
    db.refresh(action)
    
    # Crear secreto oculto del player2
    secret = models.CardsXGame(
        id_game=data["game"].id,
        id_card=cards["murderer"].id,
        is_in=models.CardState.SECRET_SET,
        position=1,
        player_id=data["player2"].id,
        hidden=True  # Oculto
    )
    db.add(secret)
    db.commit()
    db.refresh(secret)
    
    # Ejecutar acción
    request = DetectiveActionRequest(
        actionId=action.id,
        executorId=data["player1"].id,  # Owner ejecuta
        targetPlayerId=data["player2"].id,
        secretId=secret.id
    )
    
    response = service.execute_detective_action(data["game"].id, request)
    
    # Verificar response
    assert response.success is True
    assert response.completed is True
    assert response.nextAction is None
    assert len(response.effects.revealed) == 1
    assert len(response.effects.hidden) == 0
    assert len(response.effects.transferred) == 0
    
    # Verificar revealed secret
    revealed = response.effects.revealed[0]
    assert revealed.playerId == data["player2"].id
    assert revealed.secretId == secret.id
    assert revealed.cardName == "You are the Murderer!!"
    assert revealed.imgSrc == "/assets/cards/murderer.png"
    
    # Verificar que el secreto está revelado en BD
    db.refresh(secret)
    assert secret.hidden is False
    
    # Verificar que la acción padre está SUCCESS
    db.refresh(action)
    assert action.result == models.ActionResult.SUCCESS
    
    # Verificar que se creó la sub-acción
    reveal_action = db.query(models.ActionsPerTurn).filter(
        models.ActionsPerTurn.parent_action_id == action.id,
        models.ActionsPerTurn.action_type == models.ActionType.REVEAL_SECRET
    ).first()
    assert reveal_action is not None
    assert reveal_action.result == models.ActionResult.SUCCESS
    assert reveal_action.player_source == data["player1"].id
    assert reveal_action.player_target == data["player2"].id
    assert reveal_action.secret_target == secret.id


# ------------------------------
# TESTS DE EJECUCIÓN - PARKER PYNE
# ------------------------------

def test_execute_pyne_hide_secret(db, setup_game_with_players, setup_detective_cards):
    """Test ejecutar acción de Parker Pyne ocultando un secreto"""
    data = setup_game_with_players
    cards = setup_detective_cards
    service = DetectiveActionService(db)
    
    # Crear set de Pyne bajado
    pyne_entry = models.CardsXGame(
        id_game=data["game"].id,
        id_card=cards["pyne"].id,
        is_in=models.CardState.DETECTIVE_SET,
        position=1,
        player_id=data["player1"].id,
        hidden=False
    )
    db.add(pyne_entry)
    db.commit()
    
    # Crear acción PENDING
    action = models.ActionsPerTurn(
        id_game=data["game"].id,
        turn_id=data["turn"].id,
        player_id=data["player1"].id,
        action_name="play_Pyne_set",
        action_type=models.ActionType.DETECTIVE_SET,
        result=models.ActionResult.PENDING
    )
    db.add(action)
    db.commit()
    db.refresh(action)
    
    # Crear secreto REVELADO del player2
    secret = models.CardsXGame(
        id_game=data["game"].id,
        id_card=cards["accomplice"].id,
        is_in=models.CardState.SECRET_SET,
        position=1,
        player_id=data["player2"].id,
        hidden=False  # Revelado
    )
    db.add(secret)
    db.commit()
    db.refresh(secret)
    
    # Ejecutar acción
    request = DetectiveActionRequest(
        actionId=action.id,
        executorId=data["player1"].id,  # Owner ejecuta
        targetPlayerId=data["player2"].id,
        secretId=secret.id
    )
    
    response = service.execute_detective_action(data["game"].id, request)
    
    # Verificar response
    assert response.success is True
    assert response.completed is True
    assert len(response.effects.revealed) == 0
    assert len(response.effects.hidden) == 1
    assert len(response.effects.transferred) == 0
    
    # Verificar hidden secret
    hidden = response.effects.hidden[0]
    assert hidden.playerId == data["player2"].id
    assert hidden.secretId == secret.id
    
    # Verificar que el secreto está oculto en BD
    db.refresh(secret)
    assert secret.hidden is True
    
    # Verificar que se creó la sub-acción HIDE_SECRET
    hide_action = db.query(models.ActionsPerTurn).filter(
        models.ActionsPerTurn.parent_action_id == action.id,
        models.ActionsPerTurn.action_type == models.ActionType.HIDE_SECRET
    ).first()
    assert hide_action is not None
    assert hide_action.to_be_hidden == 1  # True


# ------------------------------
# TESTS DE EJECUCIÓN - SATTERTHWAITE
# ------------------------------

def test_execute_satterthwaite_without_wildcard(db, setup_game_with_players, setup_detective_cards):
    """Test Satterthwaite sin wildcard: solo revela"""
    data = setup_game_with_players
    cards = setup_detective_cards
    service = DetectiveActionService(db)
    
    # Crear set de Satterthwaite SIN wildcard
    satterthwaite = models.Card(
        name="Mr Satterthwaite",
        description="Observer",
        type="DETECTIVE",
        img_src="/assets/cards/satterthwaite.png",
        qty=2
    )
    db.add(satterthwaite)
    db.commit()
    db.refresh(satterthwaite)
    
    satterthwaite_entry = models.CardsXGame(
        id_game=data["game"].id,
        id_card=satterthwaite.id,
        is_in=models.CardState.DETECTIVE_SET,
        position=1,
        player_id=data["player1"].id,
        hidden=False
    )
    db.add(satterthwaite_entry)
    db.commit()
    
    # Crear acción PENDING
    action = models.ActionsPerTurn(
        id_game=data["game"].id,
        turn_id=data["turn"].id,
        player_id=data["player1"].id,
        action_name="play_Satterthwaite_set",
        action_type=models.ActionType.DETECTIVE_SET,
        result=models.ActionResult.PENDING
    )
    db.add(action)
    db.commit()
    db.refresh(action)
    
    # Crear secreto oculto del player2
    secret = models.CardsXGame(
        id_game=data["game"].id,
        id_card=cards["innocent"].id,
        is_in=models.CardState.SECRET_SET,
        position=1,
        player_id=data["player2"].id,
        hidden=True
    )
    db.add(secret)
    db.commit()
    db.refresh(secret)
    
    # PASO 1: Owner selecciona target
    request_step1 = DetectiveActionRequest(
        actionId=action.id,
        executorId=data["player1"].id,  # Owner ejecuta paso 1
        targetPlayerId=data["player2"].id,
        secretId=None
    )
    
    response_step1 = service.execute_detective_action(data["game"].id, request_step1)
    
    # Verificar paso 1: no completado
    assert response_step1.success is True
    assert response_step1.completed is False
    
    # PASO 2: Target selecciona secreto
    request_step2 = DetectiveActionRequest(
        actionId=action.id,
        executorId=data["player2"].id,  # Target ejecuta paso 2
        targetPlayerId=None,
        secretId=secret.id
    )
    
    response = service.execute_detective_action(data["game"].id, request_step2)
    
    # Verificar paso 2: solo revela, NO transfiere
    assert response.success is True
    assert response.completed is True
    assert len(response.effects.revealed) == 1
    assert len(response.effects.hidden) == 0
    assert len(response.effects.transferred) == 0
    
    # Verificar que el secreto sigue perteneciendo a player2
    db.refresh(secret)
    assert secret.player_id == data["player2"].id
    assert secret.hidden is False  # Revelado


def test_execute_satterthwaite_with_wildcard(db, setup_game_with_players, setup_detective_cards):
    """Test Satterthwaite con wildcard: revela Y transfiere"""
    data = setup_game_with_players
    cards = setup_detective_cards
    service = DetectiveActionService(db)
    
    # Crear set de Satterthwaite CON wildcard
    satterthwaite = models.Card(
        name="Mr Satterthwaite",
        description="Observer",
        type="DETECTIVE",
        img_src="/assets/cards/satterthwaite.png",
        qty=2
    )
    db.add(satterthwaite)
    db.commit()
    db.refresh(satterthwaite)
    
    satterthwaite_entry = models.CardsXGame(
        id_game=data["game"].id,
        id_card=satterthwaite.id,
        is_in=models.CardState.DETECTIVE_SET,
        position=1,
        player_id=data["player1"].id,
        hidden=False
    )
    harley_entry = models.CardsXGame(
        id_game=data["game"].id,
        id_card=cards["harley_quin"].id,  # WILDCARD
        is_in=models.CardState.DETECTIVE_SET,
        position=1,
        player_id=data["player1"].id,
        hidden=False
    )
    db.add_all([satterthwaite_entry, harley_entry])
    db.commit()
    
    # Crear acción PENDING
    action = models.ActionsPerTurn(
        id_game=data["game"].id,
        turn_id=data["turn"].id,
        player_id=data["player1"].id,
        action_name="play_Satterthwaite_set",
        action_type=models.ActionType.DETECTIVE_SET,
        result=models.ActionResult.PENDING
    )
    db.add(action)
    db.commit()
    db.refresh(action)
    
    # Crear secreto oculto del player2
    secret = models.CardsXGame(
        id_game=data["game"].id,
        id_card=cards["murderer"].id,
        is_in=models.CardState.SECRET_SET,
        position=1,
        player_id=data["player2"].id,
        hidden=True
    )
    db.add(secret)
    db.commit()
    db.refresh(secret)
    
    # PASO 1: Owner selecciona target
    request_step1 = DetectiveActionRequest(
        actionId=action.id,
        executorId=data["player1"].id,  # Owner ejecuta paso 1
        targetPlayerId=data["player2"].id,
        secretId=None
    )
    
    response_step1 = service.execute_detective_action(data["game"].id, request_step1)
    
    # Verificar paso 1: no completado, hay nextAction
    assert response_step1.success is True
    assert response_step1.completed is False
    assert response_step1.nextAction is not None
    assert len(response_step1.effects.revealed) == 0
    
    # PASO 2: Target selecciona secreto
    request_step2 = DetectiveActionRequest(
        actionId=action.id,
        executorId=data["player2"].id,  # Target ejecuta paso 2
        targetPlayerId=None,
        secretId=secret.id
    )
    
    response = service.execute_detective_action(data["game"].id, request_step2)
    
    # Verificar paso 2: revela Y transfiere
    assert response.success is True
    assert response.completed is True
    assert len(response.effects.revealed) == 1
    assert len(response.effects.hidden) == 0
    assert len(response.effects.transferred) == 1
    
    # Verificar transferred
    transferred = response.effects.transferred[0]
    assert transferred.fromPlayerId == data["player2"].id
    assert transferred.toPlayerId == data["player1"].id  # Owner recibe
    assert transferred.faceDown is True
    assert transferred.cardName == "You are the Murderer!!"
    
    # Verificar que el secreto cambió de dueño en BD
    db.refresh(secret)
    assert secret.player_id == data["player1"].id  # Ahora es del owner
    assert secret.hidden is True  # Face-down
    assert secret.position == 1  # Nueva posición calculada
    
    # Verificar que se crearon ambas sub-acciones
    reveal_action = db.query(models.ActionsPerTurn).filter(
        models.ActionsPerTurn.parent_action_id == action.id,
        models.ActionsPerTurn.action_type == models.ActionType.REVEAL_SECRET
    ).first()
    assert reveal_action is not None
    
    transfer_action = db.query(models.ActionsPerTurn).filter(
        models.ActionsPerTurn.parent_action_id == action.id,
        models.ActionsPerTurn.action_type == models.ActionType.MOVE_CARD
    ).first()
    assert transfer_action is not None
    assert transfer_action.player_source == data["player2"].id
    assert transfer_action.player_target == data["player1"].id
