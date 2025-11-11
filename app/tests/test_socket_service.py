import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from app.sockets.socket_service import WebSocketService

@pytest.fixture
def mock_ws_manager():
    """Mocked websocket manager"""
    ws_manager = MagicMock()
    ws_manager.emit_to_room = AsyncMock()
    ws_manager.emit_to_sid = AsyncMock()
    ws_manager.get_sids_in_game = MagicMock(return_value=["sid1", "sid2"])
    ws_manager.get_user_session = MagicMock(side_effect=lambda sid: {"user_id": 1} if sid == "sid1" else {"user_id": 2})
    return ws_manager

@pytest.fixture
def service(mock_ws_manager, monkeypatch):
    """Create a WebSocketService with mocked ws_manager"""
    with patch("app.sockets.socket_service.get_ws_manager", return_value=mock_ws_manager):
        svc = WebSocketService()
    return svc

# ---------------
# Basic notifications
# ---------------

@pytest.mark.asyncio
async def test_notificar_estado_publico(service, mock_ws_manager):
    game_state = {
        "game_id": 1,
        "status": "INGAME",
        "turno_actual": 1,
        "jugadores": [{"player_id": 1}],
        "mazos": {"deck": {"count": 25}}
    }

    await service.notificar_estado_publico(10, game_state)

    mock_ws_manager.emit_to_room.assert_awaited_once()
    args, kwargs = mock_ws_manager.emit_to_room.await_args
    event, payload = args[1], args[2]

    assert event == "game_state_public"
    assert payload["type"] == "game_state_public"
    assert payload["room_id"] == 10
    assert payload["game_id"] == 1
    assert "timestamp" in payload


@pytest.mark.asyncio
async def test_notificar_estados_privados(service, mock_ws_manager):
    estados_privados = {
        1: {"mano": [{"id": 1}], "secretos": [{"id": 99}]},
        2: {"mano": [], "secretos": []},
    }

    await service.notificar_estados_privados(10, estados_privados)

    assert mock_ws_manager.emit_to_sid.await_count == 2
    for call in mock_ws_manager.emit_to_sid.await_args_list:
        _, event, payload = call.args
        assert event == "game_state_private"
        assert payload["type"] == "game_state_private"
        assert "timestamp" in payload


@pytest.mark.asyncio
async def test_notificar_fin_partida(service, mock_ws_manager):
    winners = [{"player_id": 1, "name": "Ana"}]
    await service.notificar_fin_partida(10, winners, "Victory")

    assert mock_ws_manager.emit_to_sid.await_count == 2
    args, _, payload = mock_ws_manager.emit_to_sid.await_args_list[0].args
    assert payload["type"] == "game_ended"
    assert "reason" in payload


# ---------------
# Combined / Convenience methods
# ---------------

@pytest.mark.asyncio
async def test_notificar_estado_partida_legacy(service, mock_ws_manager):
    game_state = {
        "game_id": 2,
        "status": "INGAME",
        "jugadores": [],
        "mazos": {},
        "estados_privados": {1: {"mano": [], "secretos": []}},
        "winners": [],
        "finish_reason": "Done"
    }

    await service.notificar_estado_partida(50, game_state=game_state, partida_finalizada=False)
    assert mock_ws_manager.emit_to_room.await_count >= 1


# ---------------
# Detective actions
# ---------------

@pytest.mark.asyncio
async def test_detective_action_methods(service, mock_ws_manager):
    await service.notificar_detective_action_started(1, 5, "SET_A")
    await service.notificar_detective_target_selected(1, 5, 8, "SET_A")
    await service.notificar_detective_action_request(1, 2, "action123", 5, "SET_A")
    await service.notificar_detective_action_complete(1, "SET_A", 5, 8, secret_id=99, action="hidden")

    assert mock_ws_manager.emit_to_room.await_count >= 3
    mock_ws_manager.emit_to_sid.assert_awaited()


# ---------------
# Event actions
# ---------------

@pytest.mark.asyncio
async def test_event_methods(service, mock_ws_manager):
    await service.notificar_event_action_started(1, 5, "EVENT_A", "Card X")
    await service.notificar_event_step_update(1, 5, "EVENT_A", "step1", "doing something")
    await service.notificar_event_action_complete(1, 5, "EVENT_A")

    for call in mock_ws_manager.emit_to_room.await_args_list:
        _, event, payload = call.args
        assert payload["type"].startswith("event_")


# ---------------
# Draw / Turn actions
# ---------------

@pytest.mark.asyncio
async def test_draw_and_turn_methods(service, mock_ws_manager):
    await service.notificar_player_must_draw(1, 10, 3)
    await service.notificar_card_drawn_simple(1, 10, "deck", 2)
    await service.notificar_turn_finished(1, 10)

    for call in mock_ws_manager.emit_to_room.await_args_list:
        _, event, payload = call.args
        assert "player_id" in payload
        assert "timestamp" in payload


# ---------------
# Social Disgrace
# ---------------

@pytest.mark.asyncio
async def test_notificar_social_disgrace_update(service, mock_ws_manager):
    """Test notificación de cambio en desgracia social"""
    players_in_disgrace = [
        {
            "player_id": 5,
            "player_name": "Ana",
            "avatar_src": "avatar1.png",
            "entered_at": "2025-11-06T10:30:00"
        },
        {
            "player_id": 8,
            "player_name": "Luis",
            "avatar_src": "avatar2.png",
            "entered_at": "2025-11-06T10:35:00"
        }
    ]
    
    change_info = {
        "action": "entered",
        "player_id": 5,
        "player_name": "Ana",
        "game_id": 1
    }

    await service.notificar_social_disgrace_update(
        room_id=10,
        game_id=1,
        players_in_disgrace=players_in_disgrace,
        change_info=change_info
    )

    mock_ws_manager.emit_to_room.assert_awaited_once()
    args, kwargs = mock_ws_manager.emit_to_room.await_args
    room_id, event, payload = args

    assert room_id == 10
    assert event == "social_disgrace_update"
    assert payload["type"] == "social_disgrace_update"
    assert payload["game_id"] == 1
    assert len(payload["players_in_disgrace"]) == 2
    assert payload["players_in_disgrace"][0]["player_id"] == 5
    assert payload["players_in_disgrace"][1]["player_name"] == "Luis"
    assert payload["change"]["action"] == "entered"
    assert payload["change"]["player_name"] == "Ana"
    assert payload["message"] == "Ana ha entrado en desgracia social"
    assert "timestamp" in payload


@pytest.mark.asyncio
async def test_notificar_social_disgrace_update_sin_change_info(service, mock_ws_manager):
    """Test notificación de desgracia social sin change_info (lista inicial)"""
    players_in_disgrace = [
        {
            "player_id": 3,
            "player_name": "Carlos",
            "avatar_src": "avatar3.png",
            "entered_at": "2025-11-06T09:00:00"
        }
    ]

    await service.notificar_social_disgrace_update(
        room_id=20,
        game_id=2,
        players_in_disgrace=players_in_disgrace,
        change_info=None
    )

    mock_ws_manager.emit_to_room.assert_awaited_once()
    _, event, payload = mock_ws_manager.emit_to_room.await_args.args

    assert event == "social_disgrace_update"
    assert payload["game_id"] == 2
    assert len(payload["players_in_disgrace"]) == 1
    assert payload["change"] is None
    assert payload["message"] is None


@pytest.mark.asyncio
async def test_notificar_social_disgrace_update_lista_vacia(service, mock_ws_manager):
    """Test notificación cuando nadie está en desgracia social"""
    change_info = {
        "action": "exited",
        "player_id": 7,
        "player_name": "María",
        "game_id": 3
    }

    await service.notificar_social_disgrace_update(
        room_id=30,
        game_id=3,
        players_in_disgrace=[],
        change_info=change_info
    )

    mock_ws_manager.emit_to_room.assert_awaited_once()
    _, event, payload = mock_ws_manager.emit_to_room.await_args.args

    assert event == "social_disgrace_update"
    assert payload["game_id"] == 3
    assert payload["players_in_disgrace"] == []
    assert payload["change"]["action"] == "exited"
    assert payload["message"] == "María ha salido de desgracia social"



# ---------------
# Not So Fast (NSF) notifications
# ---------------

@pytest.mark.asyncio
async def test_notificar_valid_action(service, mock_ws_manager):
    """Test notificar acción válida (VALID_ACTION)"""
    await service.notificar_valid_action(
        room_id=15,
        action_id=100,
        player_id=5,
        action_type="EVENT",
        action_name="Point your suspicions",
        cancellable=True
    )

    mock_ws_manager.emit_to_room.assert_awaited_once()
    room_id, event, payload = mock_ws_manager.emit_to_room.await_args.args

    assert room_id == 15
    assert event == "valid_action"
    assert payload["type"] == "valid_action"
    assert payload["action_id"] == 100
    assert payload["player_id"] == 5
    assert payload["action_type"] == "EVENT"
    assert payload["action_name"] == "Point your suspicions"
    assert payload["cancellable"] is True
    assert "timestamp" in payload


@pytest.mark.asyncio
async def test_notificar_valid_action_no_cancelable(service, mock_ws_manager):
    """Test notificar acción válida pero no cancelable"""
    await service.notificar_valid_action(
        room_id=20,
        action_id=101,
        player_id=6,
        action_type="EVENT",
        action_name="Cards off the table",
        cancellable=False
    )

    _, event, payload = mock_ws_manager.emit_to_room.await_args.args

    assert payload["cancellable"] is False
    assert payload["action_name"] == "Cards off the table"


@pytest.mark.asyncio
async def test_notificar_nsf_counter_start(service, mock_ws_manager):
    """Test notificar inicio de ventana NSF (NSF_COUNTER_START)"""
    await service.notificar_nsf_counter_start(
        room_id=25,
        action_id=102,
        nsf_action_id=103,
        player_id=7,
        action_type="CREATE_SET",
        action_name="Create Marple Set",
        time_remaining=5
    )

    mock_ws_manager.emit_to_room.assert_awaited_once()
    room_id, event, payload = mock_ws_manager.emit_to_room.await_args.args

    assert room_id == 25
    assert event == "nsf_counter_start"
    assert payload["type"] == "nsf_counter_start"
    assert payload["action_id"] == 102
    assert payload["nsf_action_id"] == 103
    assert payload["player_id"] == 7
    assert payload["action_type"] == "CREATE_SET"
    assert payload["action_name"] == "Create Marple Set"
    assert payload["time_remaining"] == 5
    assert "timestamp" in payload


@pytest.mark.asyncio
async def test_notificar_nsf_counter_tick(service, mock_ws_manager):
    """Test notificar tick del contador NSF (NSF_COUNTER_TICK)"""
    await service.notificar_nsf_counter_tick(
        room_id=30,
        action_id=104,
        remaining_time=3,
        elapsed_time=2
    )

    mock_ws_manager.emit_to_room.assert_awaited_once()
    room_id, event, payload = mock_ws_manager.emit_to_room.await_args.args

    assert room_id == 30
    assert event == "nsf_counter_tick"
    assert payload["type"] == "nsf_counter_tick"
    assert payload["action_id"] == 104
    assert payload["remaining_time"] == 3
    assert payload["elapsed_time"] == 2
    assert "timestamp" in payload


@pytest.mark.asyncio
async def test_notificar_nsf_played(service, mock_ws_manager):
    """Test notificar que un jugador jugó NSF (NSF_PLAYED)"""
    await service.notificar_nsf_played(
        room_id=35,
        action_id=105,
        nsf_action_id=106,
        player_id=8,
        card_id=33,
        player_name="TestPlayer"
    )

    mock_ws_manager.emit_to_room.assert_awaited_once()
    room_id, event, payload = mock_ws_manager.emit_to_room.await_args.args

    assert room_id == 35
    assert event == "nsf_played"
    assert payload["type"] == "nsf_played"
    assert payload["action_id"] == 105
    assert payload["nsf_action_id"] == 106
    assert payload["player_id"] == 8
    assert payload["card_id"] == 33
    assert payload["message"] == "Player TestPlayer jugó Not So Fast"
    assert "timestamp" in payload


@pytest.mark.asyncio
async def test_notificar_nsf_counter_complete_cancelled(service, mock_ws_manager):
    """Test notificar finalización de ventana NSF con resultado CANCELLED"""
    await service.notificar_nsf_counter_complete(
        room_id=40,
        action_id=107,
        final_result="cancelled",
        message="NSF counter finished - 1 NSF played, action cancelled"
    )

    mock_ws_manager.emit_to_room.assert_awaited_once()
    room_id, event, payload = mock_ws_manager.emit_to_room.await_args.args

    assert room_id == 40
    assert event == "nsf_counter_complete"
    assert payload["type"] == "nsf_counter_complete"
    assert payload["action_id"] == 107
    assert payload["final_result"] == "cancelled"
    assert payload["message"] == "NSF counter finished - 1 NSF played, action cancelled"
    assert "timestamp" in payload


@pytest.mark.asyncio
async def test_notificar_nsf_counter_complete_continue(service, mock_ws_manager):
    """Test notificar finalización de ventana NSF con resultado CONTINUE"""
    await service.notificar_nsf_counter_complete(
        room_id=45,
        action_id=108,
        final_result="continue",
        message="NSF counter finished - 2 NSF played, action continues"
    )

    _, event, payload = mock_ws_manager.emit_to_room.await_args.args

    assert payload["action_id"] == 108
    assert payload["final_result"] == "continue"
    assert payload["message"] == "NSF counter finished - 2 NSF played, action continues"


@pytest.mark.asyncio
async def test_notificar_accion_cancelada_ejecutada_create_set(service, mock_ws_manager):
    """Test notificar ejecución de acción cancelada tipo CREATE_SET"""
    await service.notificar_accion_cancelada_ejecutada(
        room_id=50,
        action_id=109,
        player_id=9,
        message="Jugador CancelPlayer intentó bajar set de detective Parker Pyne creado pero efecto no realizado"
    )

    mock_ws_manager.emit_to_room.assert_awaited_once()
    room_id, event, payload = mock_ws_manager.emit_to_room.await_args.args

    assert room_id == 50
    assert event == "cancelled_action_executed"
    assert payload["type"] == "cancelled_action_executed"
    assert payload["action_id"] == 109
    assert payload["player_id"] == 9
    assert "Parker Pyne" in payload["message"]
    assert "timestamp" in payload


@pytest.mark.asyncio
async def test_notificar_accion_cancelada_ejecutada_event(service, mock_ws_manager):
    """Test notificar ejecución de acción cancelada tipo EVENT"""
    await service.notificar_accion_cancelada_ejecutada(
        room_id=55,
        action_id=110,
        player_id=10,
        message="Jugador EventPlayer jugó carta evento Point your suspicions que va al mazo de descarte"
    )

    _, event, payload = mock_ws_manager.emit_to_room.await_args.args

    assert event == "cancelled_action_executed"
    assert payload["action_id"] == 110
    assert payload["player_id"] == 10
    assert "Point your suspicions" in payload["message"]
    assert "mazo de descarte" in payload["message"]


@pytest.mark.asyncio
async def test_notificar_accion_cancelada_ejecutada_add_to_set(service, mock_ws_manager):
    """Test notificar ejecución de acción cancelada tipo ADD_TO_SET"""
    await service.notificar_accion_cancelada_ejecutada(
        room_id=60,
        action_id=111,
        player_id=11,
        message="Jugador AddPlayer intentó agregar carta a set Miss Marple ampliado pero efecto no realizado"
    )

    _, event, payload = mock_ws_manager.emit_to_room.await_args.args

    assert event == "cancelled_action_executed"
    assert payload["action_id"] == 111
    assert payload["player_id"] == 11
    assert "Miss Marple" in payload["message"]
    assert "ampliado pero efecto no realizado" in payload["message"]
