import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, AsyncMock, patch
from app.routes.finish_turn import router, get_db
from app.db import models
from app.main import app
from datetime import datetime

# --- Setup FastAPI test client ---
app.include_router(router)
client = TestClient(app)

@pytest.fixture
def mock_db():
    return MagicMock()

@pytest.fixture
def mock_get_db(mock_db):
    def _mock_get_db():
        yield mock_db
    return _mock_get_db


def make_mock_room_game_players(turn_user_id=1):
    """Helper to prepare mocked Room, Game and Players."""
    room = models.Room(id=1, id_game=10, status="INGAME")
    game = models.Game(id=10, player_turn_id=turn_user_id)
    p1 = models.Player(id=1, id_room=1, order=1)
    p2 = models.Player(id=2, id_room=1, order=2)
    return room, game, [p1, p2]


# ================================================================
# SUCCESS CASE
# ================================================================

def test_finish_turn_success(mock_db, mock_get_db):
    app.dependency_overrides[get_db] = mock_get_db

    room, game, players = make_mock_room_game_players()

    # mock query chain behavior
    def query_side_effect(model):
        if model == models.Room:
            q = MagicMock()
            q.filter.return_value.first.return_value = room
            return q
        if model == models.Game:
            q = MagicMock()
            q.filter.return_value.first.return_value = game
            return q
        if model == models.Player:
            q = MagicMock()
            q.filter.return_value.order_by.return_value.all.return_value = players
            return q
        if model == models.CardsXGame:
            q = MagicMock()
            q.filter.return_value.count.return_value = 25
            return q
        return MagicMock()

    mock_db.query.side_effect = query_side_effect
    mock_db.commit = MagicMock()
    mock_db.refresh = MagicMock()

    with patch("app.routes.finish_turn.build_complete_game_state") as mock_build_state, \
         patch("app.routes.finish_turn.get_websocket_service") as mock_ws:
        mock_build_state.return_value = {"game_id": 10, "status": "INGAME"}

        ws = MagicMock()
        ws.notificar_estado_partida = AsyncMock()
        ws.notificar_turn_finished = AsyncMock()
        mock_ws.return_value = ws

        response = client.post("/game/1/finish-turn", json={"user_id": 1})

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["next_turn"] == 2

        ws.notificar_estado_partida.assert_awaited_once()
        ws.notificar_turn_finished.assert_awaited_once()

    app.dependency_overrides.clear()


# ================================================================
# ROOM NOT FOUND
# ================================================================

def test_finish_turn_room_not_found(mock_db, mock_get_db):
    app.dependency_overrides[get_db] = mock_get_db

    mock_db.query.return_value.filter.return_value.first.return_value = None

    response = client.post("/game/999/finish-turn", json={"user_id": 1})
    assert response.status_code == 404
    assert response.json()["detail"] == "room_not_found"

    app.dependency_overrides.clear()


# ================================================================
# GAME NOT FOUND
# ================================================================

def test_finish_turn_game_not_found(mock_db, mock_get_db):
    app.dependency_overrides[get_db] = mock_get_db

    room = models.Room(id=1, id_game=10)
    def query_side_effect(model):
        if model == models.Room:
            q = MagicMock()
            q.filter.return_value.first.return_value = room
            return q
        if model == models.Game:
            q = MagicMock()
            q.filter.return_value.first.return_value = None
            return q
        return MagicMock()
    mock_db.query.side_effect = query_side_effect

    resp = client.post("/game/1/finish-turn", json={"user_id": 1})
    assert resp.status_code == 404
    assert resp.json()["detail"] == "game_not_found"

    app.dependency_overrides.clear()


# ================================================================
# NOT YOUR TURN
# ================================================================

def test_finish_turn_not_your_turn(mock_db, mock_get_db):
    app.dependency_overrides[get_db] = mock_get_db

    room, game, players = make_mock_room_game_players(turn_user_id=2)

    def query_side_effect(model):
        if model == models.Room:
            q = MagicMock()
            q.filter.return_value.first.return_value = room
            return q
        if model == models.Game:
            q = MagicMock()
            q.filter.return_value.first.return_value = game
            return q
        if model == models.Player:
            q = MagicMock()
            q.filter.return_value.order_by.return_value.all.return_value = players
            return q
        return MagicMock()

    mock_db.query.side_effect = query_side_effect

    resp = client.post("/game/1/finish-turn", json={"user_id": 1})
    assert resp.status_code == 403
    assert resp.json()["detail"] == "not_your_turn"

    app.dependency_overrides.clear()


# ================================================================
# TEST TURN TRANSITIONS
# ================================================================

def test_finish_turn_handles_turn_transitions(mock_db, mock_get_db):
    """Test that finishing a turn properly handles Turn table transitions."""
    app.dependency_overrides[get_db] = mock_get_db

    room, game, players = make_mock_room_game_players()
    
    # Mock current turn - create a real object so its status can be modified
    current_turn = MagicMock()
    current_turn.id = 1
    current_turn.number = 1
    current_turn.id_game = 10
    current_turn.player_id = 1
    current_turn.status = models.TurnStatus.IN_PROGRESS
    current_turn.start_time = datetime.now()

    # Track objects added to db
    added_objects = []
    mock_db.add = MagicMock(side_effect=lambda obj: added_objects.append(obj))

    def query_side_effect(model):
        if model == models.Room:
            q = MagicMock()
            q.filter.return_value.first.return_value = room
            return q
        if model == models.Game:
            q = MagicMock()
            q.filter.return_value.first.return_value = game
            return q
        if model == models.Player:
            q = MagicMock()
            q.filter.return_value.order_by.return_value.all.return_value = players
            return q
        if model == models.Turn:
            q = MagicMock()
            q.filter.return_value.filter.return_value.filter.return_value.first.return_value = current_turn
            return q
        if model == models.CardsXGame:
            q = MagicMock()
            q.filter.return_value.count.return_value = 25
            return q
        return MagicMock()

    mock_db.query.side_effect = query_side_effect
    mock_db.commit = MagicMock()
    mock_db.refresh = MagicMock()

    with patch("app.routes.finish_turn.build_complete_game_state") as mock_build_state, \
         patch("app.routes.finish_turn.get_websocket_service") as mock_ws:
        mock_build_state.return_value = {"game_id": 10, "status": "INGAME"}

        ws = MagicMock()
        ws.notificar_estado_partida = AsyncMock()
        ws.notificar_turn_finished = AsyncMock()
        mock_ws.return_value = ws

        response = client.post("/game/1/finish-turn", json={"user_id": 1})

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["next_turn"] == 2

        # Verify that current turn was finished and new turn was created
        # We should have 2 db.add calls: one for finishing current turn, one for new turn
        assert mock_db.add.call_count == 2
        
        # Verify the second call created a new Turn object
        new_turn_call = mock_db.add.call_args_list[1]
        new_turn = new_turn_call[0][0]  # First argument of the second call
        assert hasattr(new_turn, 'number')
        assert hasattr(new_turn, 'id_game')
        assert hasattr(new_turn, 'player_id')
        assert hasattr(new_turn, 'status')
        assert hasattr(new_turn, 'start_time')

    app.dependency_overrides.clear()
