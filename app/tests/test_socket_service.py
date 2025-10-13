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
