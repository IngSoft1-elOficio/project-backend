"""
Tests para servicios de timer de Not So Fast (NSF)

Cubre:
- timer_manager.py: Gestión de timers asíncronos
- counter_timeout_handler.py: Lógica de finalización y cálculo de resultado
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import date, datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import models, crud
from app.db.database import Base
from app.services.timer_manager import TimerManager, NSFTimer, get_timer_manager
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


@pytest.fixture
def game_setup(db):
    """Fixture que crea un juego básico para tests"""
    game = crud.create_game(db, {})
    room = crud.create_room(db, {
        "name": "Test Room",
        "status": "INGAME",
        "id_game": game.id
    })
    
    player = crud.create_player(db, {
        "name": "Player 1",
        "avatar_src": "avatar1.png",
        "birthdate": date(2000, 1, 1),
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
    
    return {
        "game": game,
        "room": room,
        "player": player,
        "turn": turn,
        "db": db
    }


# =============================
# TESTS TIMER_MANAGER
# =============================

def test_nsf_timer_creation():
    """Test creación de NSFTimer"""
    timer = NSFTimer(room_id=10, nsf_action_id=100, initial_time=5)
    
    assert timer.room_id == 10
    assert timer.nsf_action_id == 100
    assert timer.initial_time == 5
    assert timer.time_remaining == 5
    assert timer.cancelled is False
    assert timer.task is None


def test_nsf_timer_cancel():
    """Test cancelación manual de timer"""
    timer = NSFTimer(room_id=10, nsf_action_id=100, initial_time=5)
    timer.task = MagicMock()
    timer.task.done = MagicMock(return_value=False)
    timer.task.cancel = MagicMock()
    
    timer.cancel()
    
    assert timer.cancelled is True
    timer.task.cancel.assert_called_once()


def test_timer_manager_singleton():
    """Test que get_timer_manager retorna singleton"""
    manager1 = get_timer_manager()
    manager2 = get_timer_manager()
    
    assert manager1 is manager2


@pytest.mark.asyncio
async def test_timer_manager_start_timer():
    """Test iniciar timer básico"""
    manager = TimerManager()
    tick_callback = AsyncMock()
    complete_callback = AsyncMock()
    
    await manager.start_timer(
        room_id=10,
        nsf_action_id=100,
        time_remaining=2,  # 2 segundos para test rápido
        on_tick_callback=tick_callback,
        on_complete_callback=complete_callback
    )
    
    # Verificar que el timer se creó
    assert manager.is_timer_active(100)
    timer = manager.get_timer(100)
    assert timer is not None
    assert timer.room_id == 10
    assert timer.initial_time == 2
    
    # Esperar a que termine el countdown
    await asyncio.sleep(2.5)
    
    # Verificar que se llamó a los callbacks
    assert tick_callback.await_count >= 2  # Al menos 2 ticks
    complete_callback.assert_awaited_once_with(10, 100, was_cancelled=False)
    
    # El timer debe haberse limpiado
    assert not manager.is_timer_active(100)


@pytest.mark.asyncio
async def test_timer_manager_restart_timer():
    """Test reiniciar timer existente"""
    manager = TimerManager()
    tick_callback1 = AsyncMock()
    complete_callback1 = AsyncMock()
    
    # Iniciar primer timer
    await manager.start_timer(
        room_id=10,
        nsf_action_id=100,
        time_remaining=5,
        on_tick_callback=tick_callback1,
        on_complete_callback=complete_callback1
    )
    
    await asyncio.sleep(0.5)
    
    # Reiniciar el timer con nuevos callbacks
    tick_callback2 = AsyncMock()
    complete_callback2 = AsyncMock()
    
    await manager.start_timer(
        room_id=10,
        nsf_action_id=100,  # Mismo action_id
        time_remaining=3,
        on_tick_callback=tick_callback2,
        on_complete_callback=complete_callback2
    )
    
    # Verificar que sigue activo
    assert manager.is_timer_active(100)
    
    # Esperar a que termine
    await asyncio.sleep(3.5)
    
    # Solo el segundo callback debería haberse llamado al completar
    complete_callback2.assert_awaited_once()
    assert not manager.is_timer_active(100)


@pytest.mark.asyncio
async def test_timer_manager_cancel_timer():
    """Test cancelar timer manualmente"""
    manager = TimerManager()
    tick_callback = AsyncMock()
    complete_callback = AsyncMock()
    
    await manager.start_timer(
        room_id=10,
        nsf_action_id=100,
        time_remaining=5,
        on_tick_callback=tick_callback,
        on_complete_callback=complete_callback
    )
    
    await asyncio.sleep(0.5)
    
    # Cancelar manualmente
    await manager.cancel_timer(100)
    
    await asyncio.sleep(0.5)
    
    # El callback de completado debería haberse llamado con was_cancelled=True
    complete_callback.assert_awaited_once_with(10, 100, was_cancelled=True)
    
    # Timer no debería estar activo
    assert not manager.is_timer_active(100)


@pytest.mark.asyncio
async def test_timer_manager_multiple_timers():
    """Test manejar múltiples timers simultáneos"""
    manager = TimerManager()
    
    callbacks_100 = (AsyncMock(), AsyncMock())
    callbacks_200 = (AsyncMock(), AsyncMock())
    
    # Iniciar 2 timers diferentes
    await manager.start_timer(10, 100, 2, *callbacks_100)
    await manager.start_timer(10, 200, 2, *callbacks_200)
    
    # Ambos deberían estar activos
    assert manager.is_timer_active(100)
    assert manager.is_timer_active(200)
    
    await asyncio.sleep(2.5)
    
    # Ambos deberían haberse completado
    callbacks_100[1].assert_awaited_once()
    callbacks_200[1].assert_awaited_once()
    
    assert not manager.is_timer_active(100)
    assert not manager.is_timer_active(200)


@pytest.mark.asyncio
async def test_timer_tick_countdown():
    """Test que los ticks se emiten correctamente con tiempo decreciente"""
    manager = TimerManager()
    tick_times = []
    
    async def on_tick(room_id, nsf_action_id, time_remaining):
        tick_times.append(time_remaining)
    
    complete_callback = AsyncMock()
    
    await manager.start_timer(
        room_id=10,
        nsf_action_id=100,
        time_remaining=3,
        on_tick_callback=on_tick,
        on_complete_callback=complete_callback
    )
    
    await asyncio.sleep(3.5)
    
    # Debería haber ticks con 3, 2, 1
    assert 3 in tick_times
    assert 2 in tick_times
    assert 1 in tick_times
    # Los ticks deberían estar en orden decreciente
    assert tick_times == sorted(tick_times, reverse=True)


# =============================
# TESTS COUNTER_TIMEOUT_HANDLER
# =============================

@pytest.mark.asyncio
async def test_handle_nsf_timeout_no_nsf_played(game_setup):
    """Test timeout sin NSF jugadas (0 = par = CONTINUE)"""
    db = game_setup["db"]
    game = game_setup["game"]
    room = game_setup["room"]
    player = game_setup["player"]
    turn = game_setup["turn"]
    
    # Crear acción de intención (XXX)
    intention = crud.create_action(db, {
        "id_game": game.id,
        "turn_id": turn.id,
        "player_id": player.id,
        "action_name": "Point your suspicions",
        "action_type": models.ActionType.INIT,
        "result": models.ActionResult.PENDING
    })
    db.commit()
    db.refresh(intention)
    
    # Crear acción NSF start (YYY)
    nsf_start = crud.create_action(db, {
        "id_game": game.id,
        "turn_id": turn.id,
        "player_id": player.id,
        "action_name": models.ActionName.INSTANT_START,
        "action_type": models.ActionType.INSTANT,
        "result": models.ActionResult.PENDING,
        "triggered_by_action_id": intention.id
    })
    db.commit()
    db.refresh(nsf_start)
    
    # Mock WebSocket service
    with patch("app.services.counter_timeout_handler.get_websocket_service") as mock_ws:
        mock_ws_instance = AsyncMock()
        mock_ws.return_value = mock_ws_instance
        
        # Ejecutar handler
        await handle_nsf_timeout(
            db=db,
            room_id=room.id,
            intention_action_id=intention.id,
            nsf_action_id=nsf_start.id
        )
    
    # Verificar actualizaciones en DB
    db.refresh(intention)
    db.refresh(nsf_start)
    
    assert nsf_start.result == models.ActionResult.SUCCESS
    assert intention.result == models.ActionResult.CONTINUE  # Continúa (par)
    
    # Verificar que se emitió el evento con result="continue"
    mock_ws_instance.notificar_nsf_counter_complete.assert_awaited_once_with(
        room_id=room.id,
        action_id=intention.id,
        final_result="continue",
        message="NSF counter finished - No NSF played, action continues"
    )


@pytest.mark.asyncio
async def test_handle_nsf_timeout_one_nsf_played(game_setup):
    """Test timeout con 1 NSF jugada (1 = impar = CANCELLED)"""
    db = game_setup["db"]
    game = game_setup["game"]
    room = game_setup["room"]
    player = game_setup["player"]
    turn = game_setup["turn"]
    
    # Crear XXX y YYY
    intention = crud.create_action(db, {
        "id_game": game.id,
        "turn_id": turn.id,
        "player_id": player.id,
        "action_name": "Point your suspicions",
        "action_type": models.ActionType.INIT,
        "result": models.ActionResult.PENDING
    })
    db.commit()
    db.refresh(intention)
    
    nsf_start = crud.create_action(db, {
        "id_game": game.id,
        "turn_id": turn.id,
        "player_id": player.id,
        "action_name": models.ActionName.INSTANT_START,
        "action_type": models.ActionType.INSTANT,
        "result": models.ActionResult.PENDING,
        "triggered_by_action_id": intention.id
    })
    db.commit()
    db.refresh(nsf_start)
    
    # Crear 1 NSF jugada (ZZZ)
    nsf_played = crud.create_action(db, {
        "id_game": game.id,
        "turn_id": turn.id,
        "player_id": player.id,
        "action_name": "NOT_SO_FAST",
        "action_type": models.ActionType.INSTANT,
        "result": models.ActionResult.PENDING,
        "parent_action_id": nsf_start.id,
        "triggered_by_action_id": intention.id
    })
    db.commit()
    
    with patch("app.services.counter_timeout_handler.get_websocket_service") as mock_ws:
        mock_ws_instance = AsyncMock()
        mock_ws.return_value = mock_ws_instance
        
        await handle_nsf_timeout(
            db=db,
            room_id=room.id,
            intention_action_id=intention.id,
            nsf_action_id=nsf_start.id
        )
    
    # Verificar actualizaciones
    db.refresh(intention)
    db.refresh(nsf_start)
    
    assert nsf_start.result == models.ActionResult.CANCELLED
    assert intention.result == models.ActionResult.CANCELLED  # Cancelada
    
    # Verificar evento
    mock_ws_instance.notificar_nsf_counter_complete.assert_awaited_once_with(
        room_id=room.id,
        action_id=intention.id,
        final_result="cancelled",
        message="NSF counter finished - 1 NSF played, action cancelled"
    )


@pytest.mark.asyncio
async def test_handle_nsf_timeout_two_nsf_played(game_setup):
    """Test timeout con 2 NSF jugadas (2 = par = CONTINUE)"""
    db = game_setup["db"]
    game = game_setup["game"]
    room = game_setup["room"]
    player = game_setup["player"]
    turn = game_setup["turn"]
    
    # Crear XXX y YYY
    intention = crud.create_action(db, {
        "id_game": game.id,
        "turn_id": turn.id,
        "player_id": player.id,
        "action_name": "Create Set",
        "action_type": models.ActionType.INIT,
        "result": models.ActionResult.PENDING
    })
    db.commit()
    db.refresh(intention)
    
    nsf_start = crud.create_action(db, {
        "id_game": game.id,
        "turn_id": turn.id,
        "player_id": player.id,
        "action_name": models.ActionName.INSTANT_START,
        "action_type": models.ActionType.INSTANT,
        "result": models.ActionResult.PENDING,
        "triggered_by_action_id": intention.id
    })
    db.commit()
    db.refresh(nsf_start)
    
    # Crear 2 NSF jugadas
    for _ in range(2):
        crud.create_action(db, {
            "id_game": game.id,
            "turn_id": turn.id,
            "player_id": player.id,
            "action_name": "NOT_SO_FAST",
            "action_type": models.ActionType.INSTANT,
            "result": models.ActionResult.PENDING,
            "parent_action_id": nsf_start.id,
            "triggered_by_action_id": intention.id
        })
    db.commit()
    
    with patch("app.services.counter_timeout_handler.get_websocket_service") as mock_ws:
        mock_ws_instance = AsyncMock()
        mock_ws.return_value = mock_ws_instance
        
        await handle_nsf_timeout(
            db=db,
            room_id=room.id,
            intention_action_id=intention.id,
            nsf_action_id=nsf_start.id
        )
    
    db.refresh(intention)
    db.refresh(nsf_start)
    
    # Par = continúa
    assert nsf_start.result == models.ActionResult.SUCCESS
    assert intention.result == models.ActionResult.CONTINUE  # Continúa (par)
    
    mock_ws_instance.notificar_nsf_counter_complete.assert_awaited_once_with(
        room_id=room.id,
        action_id=intention.id,
        final_result="continue",
        message="NSF counter finished - 2 NSF played, action continues"
    )


@pytest.mark.asyncio
async def test_handle_nsf_timeout_three_nsf_played(game_setup):
    """Test timeout con 3 NSF jugadas (3 = impar = CANCELLED)"""
    db = game_setup["db"]
    game = game_setup["game"]
    room = game_setup["room"]
    player = game_setup["player"]
    turn = game_setup["turn"]
    
    # Crear XXX y YYY
    intention = crud.create_action(db, {
        "id_game": game.id,
        "turn_id": turn.id,
        "player_id": player.id,
        "action_name": "Add to Set",
        "action_type": models.ActionType.INIT,
        "result": models.ActionResult.PENDING
    })
    db.commit()
    db.refresh(intention)
    
    nsf_start = crud.create_action(db, {
        "id_game": game.id,
        "turn_id": turn.id,
        "player_id": player.id,
        "action_name": models.ActionName.INSTANT_START,
        "action_type": models.ActionType.INSTANT,
        "result": models.ActionResult.PENDING,
        "triggered_by_action_id": intention.id
    })
    db.commit()
    db.refresh(nsf_start)
    
    # Crear 3 NSF jugadas
    for _ in range(3):
        crud.create_action(db, {
            "id_game": game.id,
            "turn_id": turn.id,
            "player_id": player.id,
            "action_name": "NOT_SO_FAST",
            "action_type": models.ActionType.INSTANT,
            "result": models.ActionResult.PENDING,
            "parent_action_id": nsf_start.id,
            "triggered_by_action_id": intention.id
        })
    db.commit()
    
    with patch("app.services.counter_timeout_handler.get_websocket_service") as mock_ws:
        mock_ws_instance = AsyncMock()
        mock_ws.return_value = mock_ws_instance
        
        await handle_nsf_timeout(
            db=db,
            room_id=room.id,
            intention_action_id=intention.id,
            nsf_action_id=nsf_start.id
        )
    
    db.refresh(intention)
    db.refresh(nsf_start)
    
    # Impar = cancelada
    assert nsf_start.result == models.ActionResult.CANCELLED
    assert intention.result == models.ActionResult.CANCELLED
    
    mock_ws_instance.notificar_nsf_counter_complete.assert_awaited_once_with(
        room_id=room.id,
        action_id=intention.id,
        final_result="cancelled",
        message="NSF counter finished - 3 NSF played, action cancelled"
    )


@pytest.mark.asyncio
async def test_handle_nsf_timeout_counts_only_nsf_chain(game_setup):
    """Test que solo cuenta NSF de la cadena específica"""
    db = game_setup["db"]
    game = game_setup["game"]
    room = game_setup["room"]
    player = game_setup["player"]
    turn = game_setup["turn"]
    
    # Crear primera cadena XXX1 + YYY1
    intention1 = crud.create_action(db, {
        "id_game": game.id,
        "turn_id": turn.id,
        "player_id": player.id,
        "action_name": "Action 1",
        "action_type": models.ActionType.INIT,
        "result": models.ActionResult.PENDING
    })
    db.commit()
    db.refresh(intention1)
    
    nsf_start1 = crud.create_action(db, {
        "id_game": game.id,
        "turn_id": turn.id,
        "player_id": player.id,
        "action_name": models.ActionName.INSTANT_START,
        "action_type": models.ActionType.INSTANT,
        "result": models.ActionResult.PENDING,
        "triggered_by_action_id": intention1.id
    })
    db.commit()
    db.refresh(nsf_start1)
    
    # NSF de la primera cadena
    crud.create_action(db, {
        "id_game": game.id,
        "turn_id": turn.id,
        "player_id": player.id,
        "action_name": "NOT_SO_FAST",
        "action_type": models.ActionType.INSTANT,
        "result": models.ActionResult.PENDING,
        "parent_action_id": nsf_start1.id,
        "triggered_by_action_id": intention1.id
    })
    db.commit()
    
    # Crear segunda cadena XXX2 + YYY2
    intention2 = crud.create_action(db, {
        "id_game": game.id,
        "turn_id": turn.id,
        "player_id": player.id,
        "action_name": "Action 2",
        "action_type": models.ActionType.INIT,
        "result": models.ActionResult.PENDING
    })
    db.commit()
    db.refresh(intention2)
    
    nsf_start2 = crud.create_action(db, {
        "id_game": game.id,
        "turn_id": turn.id,
        "player_id": player.id,
        "action_name": models.ActionName.INSTANT_START,
        "action_type": models.ActionType.INSTANT,
        "result": models.ActionResult.PENDING,
        "triggered_by_action_id": intention2.id
    })
    db.commit()
    db.refresh(nsf_start2)
    
    # NO crear NSF en la segunda cadena
    
    # Ejecutar timeout en la segunda cadena
    with patch("app.services.counter_timeout_handler.get_websocket_service") as mock_ws:
        mock_ws_instance = AsyncMock()
        mock_ws.return_value = mock_ws_instance
        
        await handle_nsf_timeout(
            db=db,
            room_id=room.id,
            intention_action_id=intention2.id,
            nsf_action_id=nsf_start2.id
        )
    
    db.refresh(intention2)
    db.refresh(nsf_start2)
    
    # Segunda cadena tiene 0 NSF (no debe contar la NSF de la primera cadena)
    assert nsf_start2.result == models.ActionResult.SUCCESS
    assert intention2.result == models.ActionResult.CONTINUE  # Continue (par)
    
    mock_ws_instance.notificar_nsf_counter_complete.assert_awaited_once_with(
        room_id=room.id,
        action_id=intention2.id,
        final_result="continue",
        message="NSF counter finished - No NSF played, action continues"
    )


# =============================
# TESTS INTEGRACIÓN TIMER + HANDLER
# =============================

@pytest.mark.asyncio
async def test_full_nsf_flow_with_timer(game_setup):
    """Test flujo completo: timer + timeout handler"""
    db = game_setup["db"]
    game = game_setup["game"]
    room = game_setup["room"]
    player = game_setup["player"]
    turn = game_setup["turn"]
    
    # Crear acciones
    intention = crud.create_action(db, {
        "id_game": game.id,
        "turn_id": turn.id,
        "player_id": player.id,
        "action_name": "Test Action",
        "action_type": models.ActionType.INIT,
        "result": models.ActionResult.PENDING
    })
    db.commit()
    db.refresh(intention)
    
    nsf_start = crud.create_action(db, {
        "id_game": game.id,
        "turn_id": turn.id,
        "player_id": player.id,
        "action_name": models.ActionName.INSTANT_START,
        "action_type": models.ActionType.INSTANT,
        "result": models.ActionResult.PENDING,
        "triggered_by_action_id": intention.id
    })
    db.commit()
    db.refresh(nsf_start)
    
    # Mock WS
    with patch("app.services.counter_timeout_handler.get_websocket_service") as mock_ws:
        mock_ws_instance = AsyncMock()
        mock_ws.return_value = mock_ws_instance
        
        # Crear timer con handler como callback
        manager = TimerManager()
        tick_callback = AsyncMock()
        
        async def on_complete(room_id, nsf_action_id, was_cancelled):
            if not was_cancelled:
                await handle_nsf_timeout(
                    db=db,
                    room_id=room_id,
                    intention_action_id=intention.id,
                    nsf_action_id=nsf_action_id
                )
        
        await manager.start_timer(
            room_id=room.id,
            nsf_action_id=nsf_start.id,
            time_remaining=2,
            on_tick_callback=tick_callback,
            on_complete_callback=on_complete
        )
        
        # Esperar a que termine
        await asyncio.sleep(2.5)
        
        # Verificar que el handler se ejecutó
        db.refresh(intention)
        db.refresh(nsf_start)

        assert nsf_start.result == models.ActionResult.SUCCESS
        assert intention.result == models.ActionResult.CONTINUE  # Continúa (par)
        mock_ws_instance.notificar_nsf_counter_complete.assert_awaited_once()
