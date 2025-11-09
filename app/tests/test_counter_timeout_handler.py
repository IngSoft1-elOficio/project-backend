"""
Tests para counter_timeout_handler.py

Verifica la lógica de paridad y actualización de estados cuando el timer NSF termina.
"""

import pytest
import asyncio
from datetime import datetime, date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import AsyncMock, patch

from app.db import models, crud
from app.db.database import Base
from app.db.models import ActionResult, ActionName
from app.services.counter_timeout_handler import handle_nsf_timeout


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


def _create_test_game_setup(db):
    """Crea una configuración básica de juego para tests."""
    # Game
    game = models.Game(id=1)
    db.add(game)
    
    # Room
    room = models.Room(id=1, name="Test Room", status=models.RoomStatus.INGAME, id_game=1)
    db.add(room)
    
    # Players
    player1 = models.Player(
        id=1,
        id_room=1,
        name="Alice",
        order=1,
        is_host=True,
        avatar_src="avatar1.png",
        birthdate=date(1990, 1, 1)
    )
    player2 = models.Player(
        id=2,
        id_room=1,
        name="Bob",
        order=2,
        is_host=False,
        avatar_src="avatar2.png",
        birthdate=date(1991, 1, 1)
    )
    player3 = models.Player(
        id=3,
        id_room=1,
        name="Charlie",
        order=3,
        is_host=False,
        avatar_src="avatar3.png",
        birthdate=date(1992, 1, 1)
    )
    db.add_all([player1, player2, player3])
    db.flush()
    
    # Turn
    turn = models.Turn(id=1, id_game=1, number=1, player_id=1, status=models.TurnStatus.IN_PROGRESS)
    db.add(turn)
    
    db.commit()
    
    return room, game, turn, player1, player2, player3


@pytest.mark.asyncio
async def test_nsf_timeout_zero_nsf_par(db):
    """
    Test: timeout con 0 NSF jugadas (par) → CONTINUE
    Precondiciones: XXX, YYY creados, ningún ZZZ
    Postcondiciones: XXX=CONTINUE, YYY=SUCCESS
    """
    # Setup
    room, game, turn, *_ = _create_test_game_setup(db)
    
    # Acción XXX (INIT - acción original que puede ser cancelada)
    intention_action = models.ActionsPerTurn(
        id=100,
        turn_id=1,
        player_id=1,
        id_game=1,
        action_name=ActionName.CARD_TRADE,
        action_time=datetime.now(),
        result=ActionResult.PENDING
    )
    db.add(intention_action)
    
    # Acción YYY (INSTANT_START - inicio ventana NSF)
    nsf_start_action = models.ActionsPerTurn(
        id=200,
        turn_id=1,
        player_id=1,
        id_game=1,
        action_name=ActionName.INSTANT_START,
        action_time=datetime.now(),
        result=ActionResult.PENDING,
        parent_action_id=100
    )
    db.add(nsf_start_action)


@pytest.mark.asyncio
async def test_nsf_timeout_one_nsf_impar(db):
    """
    Test: timeout con 1 NSF jugada (impar) → CANCELLED
    Precondiciones: XXX, YYY creados, 1 ZZZ creado
    Postcondiciones: XXX=CANCELLED, YYY=CANCELLED, ZZZ=SUCCESS
    """
    # Setup
    room, game, turn, *players = _create_test_game_setup(db)
    
    # Acción XXX (INIT)
    intention_action = models.ActionsPerTurn(
        id=100,
        turn_id=1,
        player_id=1,
        id_game=1,
        action_name=ActionName.CARD_TRADE,
        action_time=datetime.now(),
        result=ActionResult.PENDING
    )
    db.add(intention_action)
    
    # Acción YYY (INSTANT_START)
    nsf_start_action = models.ActionsPerTurn(
        id=200,
        turn_id=1,
        player_id=1,
        id_game=1,
        action_name=ActionName.INSTANT_START,
        action_time=datetime.now(),
        result=ActionResult.PENDING,
        parent_action_id=100
    )
    db.add(nsf_start_action)
    
    # Acción ZZZ1 (INSTANT_PLAY)
    nsf_play1 = models.ActionsPerTurn(
        id=300,
        turn_id=1,
        player_id=1,
        id_game=1,
        action_name=ActionName.INSTANT_PLAY,
        action_time=datetime.now(),
        result=ActionResult.PENDING,
        parent_action_id=200,          # parent = YYY
        triggered_by_action_id=100     # triggered_by = XXX
    )
    db.add(nsf_play1)
    
    db.commit()
    
    # Mock WebSocket service
    with patch('app.services.counter_timeout_handler.get_websocket_service') as mock_ws:
        mock_ws_instance = AsyncMock()
        mock_ws.return_value = mock_ws_instance
        
        # Execute
        await handle_nsf_timeout(
            db=db,
            room_id=room.id,
            intention_action_id=100,
            nsf_action_id=200
        )
        
        # Assert
        db.refresh(intention_action)
        db.refresh(nsf_start_action)
        db.refresh(nsf_play1)
        
        assert intention_action.result == ActionResult.CANCELLED  # XXX cancelado (impar)
        assert nsf_start_action.result == ActionResult.CANCELLED  # YYY cancelado
        assert nsf_play1.result == ActionResult.SUCCESS           # ZZZ exitoso
        
        # Verificar evento WS
        mock_ws_instance.notificar_nsf_counter_complete.assert_called_once()
        call_args = mock_ws_instance.notificar_nsf_counter_complete.call_args
        assert call_args.kwargs["final_result"] == "cancelled"


@pytest.mark.asyncio
async def test_nsf_timeout_two_nsf_par(db):
    """
    Test: timeout con 2 NSF jugadas (par) → CONTINUE
    Precondiciones: XXX, YYY creados, 2 ZZZ creados
    Postcondiciones: XXX=CONTINUE, YYY=SUCCESS, ZZZ1=SUCCESS, ZZZ2=SUCCESS
    """
    # Setup
    room, game, turn, *players = _create_test_game_setup(db)
    
    # XXX (INIT)
    intention_action = models.ActionsPerTurn(
        id=100,
        turn_id=1,
        player_id=1,
        id_game=1,
        action_name=ActionName.CARD_TRADE,
        action_time=datetime.now(),
        result=ActionResult.PENDING
    )
    db.add(intention_action)
    
    # YYY (INSTANT_START)
    nsf_start_action = models.ActionsPerTurn(
        id=200,
        turn_id=1,
        player_id=1,
        id_game=1,
        action_name=ActionName.INSTANT_START,
        action_time=datetime.now(),
        result=ActionResult.PENDING,
        parent_action_id=100
    )
    db.add(nsf_start_action)
    
    # ZZZ1
    nsf_play1 = models.ActionsPerTurn(
        id=300,
        turn_id=1,
        player_id=1,
        id_game=1,
        action_name=ActionName.INSTANT_PLAY,
        action_time=datetime.now(),
        result=ActionResult.PENDING,
        parent_action_id=200,
        triggered_by_action_id=100
    )
    db.add(nsf_play1)
    
    # ZZZ2
    nsf_play2 = models.ActionsPerTurn(
        id=301,
        turn_id=1,
        player_id=1,
        id_game=1,
        action_name=ActionName.INSTANT_PLAY,
        action_time=datetime.now(),
        result=ActionResult.PENDING,
        parent_action_id=200,
        triggered_by_action_id=100
    )
    db.add(nsf_play2)
    
    db.commit()
    
    # Mock WebSocket service
    with patch('app.services.counter_timeout_handler.get_websocket_service') as mock_ws:
        mock_ws_instance = AsyncMock()
        mock_ws.return_value = mock_ws_instance
        
        # Execute
        await handle_nsf_timeout(
            db=db,
            room_id=room.id,
            intention_action_id=100,
            nsf_action_id=200
        )
        
        # Assert
        db.refresh(intention_action)
        db.refresh(nsf_start_action)
        db.refresh(nsf_play1)
        db.refresh(nsf_play2)
        
        assert intention_action.result == ActionResult.CONTINUE  # XXX continúa (par)
        assert nsf_start_action.result == ActionResult.SUCCESS   # YYY exitoso
        assert nsf_play1.result == ActionResult.SUCCESS          # ZZZ1 exitoso
        assert nsf_play2.result == ActionResult.SUCCESS          # ZZZ2 exitoso
        
        # Verificar evento WS
        mock_ws_instance.notificar_nsf_counter_complete.assert_called_once()
        call_args = mock_ws_instance.notificar_nsf_counter_complete.call_args
        assert call_args.kwargs["final_result"] == "continue"


@pytest.mark.asyncio
async def test_nsf_timeout_three_nsf_impar(db):
    """
    Test: timeout con 3 NSF jugadas (impar) → CANCELLED
    Precondiciones: XXX, YYY creados, 3 ZZZ creados
    Postcondiciones: XXX=CANCELLED, YYY=CANCELLED, todas las ZZZ=SUCCESS
    """
    # Setup
    room, game, turn, *players = _create_test_game_setup(db)
    
    # XXX (INIT)
    intention_action = models.ActionsPerTurn(
        id=100,
        turn_id=1,
        player_id=1,
        id_game=1,
        action_name=ActionName.CARD_TRADE,
        action_time=datetime.now(),
        result=ActionResult.PENDING
    )
    db.add(intention_action)
    
    # YYY (INSTANT_START)
    nsf_start_action = models.ActionsPerTurn(
        id=200,
        turn_id=1,
        player_id=1,
        id_game=1,
        action_name=ActionName.INSTANT_START,
        action_time=datetime.now(),
        result=ActionResult.PENDING,
        parent_action_id=100
    )
    db.add(nsf_start_action)
    
    # ZZZ1, ZZZ2, ZZZ3
    nsf_plays = []
    for i in range(3):
        nsf_play = models.ActionsPerTurn(
            id=300 + i,
            turn_id=1,
        player_id=1,
            id_game=1,
            action_name=ActionName.INSTANT_PLAY,
            action_time=datetime.now(),
            result=ActionResult.PENDING,
            parent_action_id=200,
            triggered_by_action_id=100
        )
        db.add(nsf_play)
        nsf_plays.append(nsf_play)
    
    db.commit()
    
    # Mock WebSocket service
    with patch('app.services.counter_timeout_handler.get_websocket_service') as mock_ws:
        mock_ws_instance = AsyncMock()
        mock_ws.return_value = mock_ws_instance
        
        # Execute
        await handle_nsf_timeout(
            db=db,
            room_id=room.id,
            intention_action_id=100,
            nsf_action_id=200
        )
        
        # Assert
        db.refresh(intention_action)
        db.refresh(nsf_start_action)
        for nsf_play in nsf_plays:
            db.refresh(nsf_play)
        
        assert intention_action.result == ActionResult.CANCELLED  # XXX cancelado (impar)
        assert nsf_start_action.result == ActionResult.CANCELLED  # YYY cancelado
        
        # Todas las ZZZ son SUCCESS (se jugaron correctamente)
        for nsf_play in nsf_plays:
            assert nsf_play.result == ActionResult.SUCCESS
        
        # Verificar evento WS
        mock_ws_instance.notificar_nsf_counter_complete.assert_called_once()
        call_args = mock_ws_instance.notificar_nsf_counter_complete.call_args
        assert call_args.kwargs["final_result"] == "cancelled"
