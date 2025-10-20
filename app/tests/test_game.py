import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
from app.main import app
from app.db import models
from app.routes.game import get_db
from datetime import date

client = TestClient(app)

@pytest.fixture
def mock_db():
    return MagicMock()

@pytest.fixture
def mock_get_db(mock_db):
    def _mock_get_db():
        yield mock_db
    return _mock_get_db

@pytest.fixture
def sample_request():
    return {
        "room": {
            "nombre_partida": "PartidaTest",
            "jugadoresMin": 2,
            "jugadoresMax": 4
        },
        "player": {
            "nombre": "Jugador1",
            "avatar": "avatar.png",
            "fechaNacimiento": "1990-01-01"
        }
    }

def test_create_game_success(sample_request, mock_db, mock_get_db):
    app.dependency_overrides[get_db] = mock_get_db

    with patch("app.db.crud.create_game") as mock_create_game, \
         patch("app.db.crud.create_room") as mock_create_room, \
         patch("app.db.crud.create_player") as mock_create_player:

        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        mock_game = MagicMock()
        mock_game.id = 1
        mock_create_game.return_value = mock_game
        
        mock_room = MagicMock()
        mock_room.id = 10
        mock_room.name = "PartidaTest"
        mock_room.players_min = 2
        mock_room.players_max = 4
        mock_room.status = models.RoomStatus.WAITING
        mock_create_room.return_value = mock_room
        
        mock_player = MagicMock()
        mock_player.id = 100
        mock_player.name = "Jugador1"
        mock_player.avatar_src = "avatar.png"
        mock_player.birthdate = date(1990, 1, 1)
        mock_player.is_host = True
        mock_create_player.return_value = mock_player

        response = client.post("/game", json=sample_request)
        
        assert response.status_code == 201
        data = response.json()
        assert data["room"]["name"] == "PartidaTest"
        assert data["players"][0]["name"] == "Jugador1"

    app.dependency_overrides.clear()

def test_create_game_conflict(sample_request, mock_db, mock_get_db):
    app.dependency_overrides[get_db] = mock_get_db

    mock_db.query.return_value.filter.return_value.first.return_value = MagicMock(name="PartidaTest")

    response = client.post("/game", json=sample_request)
    assert response.status_code == 409
    assert response.json()["detail"] == "Ya existe una partida con ese nombre"

    app.dependency_overrides.clear()

def test_create_game_with_alternate_date_format(sample_request, mock_db, mock_get_db):
    app.dependency_overrides[get_db] = mock_get_db
    sample_request["player"]["fechaNacimiento"] = "01-01-1990"

    with patch("app.db.crud.create_game") as mock_create_game, \
         patch("app.db.crud.create_room") as mock_create_room, \
         patch("app.db.crud.create_player") as mock_create_player:

        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        mock_game = MagicMock()
        mock_game.id = 1
        mock_create_game.return_value = mock_game
        
        mock_room = MagicMock()
        mock_room.id = 10
        mock_room.name = "PartidaTest"
        mock_room.players_min = 2
        mock_room.players_max = 4
        mock_room.status = models.RoomStatus.WAITING
        mock_create_room.return_value = mock_room
        
        mock_player = MagicMock()
        mock_player.id = 100
        mock_player.name = "Jugador1"
        mock_player.avatar_src = "avatar.png"
        mock_player.birthdate = date(1990, 1, 1)
        mock_player.is_host = True
        mock_create_player.return_value = mock_player

        response = client.post("/game", json=sample_request)
        
        assert response.status_code == 201
        assert response.json()["players"][0]["name"] == "Jugador1"

    app.dependency_overrides.clear()

def test_create_game_internal_error(sample_request, mock_db, mock_get_db):
    app.dependency_overrides[get_db] = mock_get_db

    with patch("app.db.crud.create_game", side_effect=Exception("DB error")):
        mock_db.query.return_value.filter.return_value.first.return_value = None

        response = client.post("/game", json=sample_request)
        assert response.status_code == 500
        assert response.json()["detail"] == "Error interno al crear la partida"

    app.dependency_overrides.clear()

def test_get_db_real_session():
    from app.routes.game import get_db
    gen = get_db()
    db = next(gen)
    assert db is not None
    # Forzar finally
    try:
        pass
    finally:
        gen.close()

