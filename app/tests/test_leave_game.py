import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from datetime import date
from unittest.mock import AsyncMock, patch
from app.main import app
from app.db.database import Base
from app.db.models import Room, Player, RoomStatus
from app.routes.leave_game import get_db

# Base de datos en memoria COMPARTIDA para todos los tests
SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,  # Importante: mantiene la misma conexión
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Crear tablas UNA VEZ
Base.metadata.create_all(bind=engine)

client = TestClient(app)


@pytest.fixture(scope="function")
def test_db():
    """Crea una sesión de DB limpia para cada test"""
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    
    yield session
    
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(autouse=True)
def override_get_db(test_db):
    """Override del dependency de base de datos"""
    def _get_test_db():
        try:
            yield test_db
        finally:
            pass
    
    app.dependency_overrides[get_db] = _get_test_db
    yield
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def mock_websocket():
    """Mock del WebSocket service para evitar errores"""
    with patch('app.services.leave_game_service.get_websocket_service') as mock_ws:
        mock_ws_instance = AsyncMock()
        mock_ws_instance.notificar_game_cancelled = AsyncMock(return_value=None)
        mock_ws_instance.notificar_player_left = AsyncMock(return_value=None)
        mock_ws.return_value = mock_ws_instance
        yield mock_ws_instance


class TestLeaveGameEndpoint:
    """Tests de integración para DELETE /game_join/{room_id}/leave"""

    def test_host_cancels_game_successfully(self, test_db):
        """Test: Host cancela la partida y elimina la sala"""
        # Crear sala
        room = Room(
            name="Test Room",
            players_min=2,
            players_max=6,
            status=RoomStatus.WAITING,
            id_game=None
        )
        test_db.add(room)
        test_db.commit()
        test_db.refresh(room)

        # Crear jugadores
        host = Player(
            name="Host Player",
            avatar_src="avatar1.png",
            birthdate=date(1990, 1, 1),
            id_room=room.id,
            is_host=True,
            order=1
        )
        player2 = Player(
            name="Player 2",
            avatar_src="avatar2.png",
            birthdate=date(1991, 1, 1),
            id_room=room.id,
            is_host=False,
            order=2
        )
        test_db.add_all([host, player2])
        test_db.commit()

        # Host cancela
        response = client.delete(
            f"/game_join/{room.id}/leave",
            headers={"HTTP_USER_ID": str(host.id)}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["is_host"] is True

        # Verificar que la sala fue eliminada
        test_db.expire_all()
        room_check = test_db.query(Room).filter(Room.id == room.id).first()
        assert room_check is None

        # Verificar que todos los jugadores fueron desvinculados
        host_check = test_db.query(Player).filter(Player.id == host.id).first()
        player2_check = test_db.query(Player).filter(Player.id == player2.id).first()
        assert host_check.id_room is None
        assert player2_check.id_room is None

    def test_player_leaves_game_successfully(self, test_db):
        """Test: Jugador abandona la partida"""
        # Crear sala
        room = Room(
            name="Test Room",
            players_min=2,
            players_max=6,
            status=RoomStatus.WAITING,
            id_game=None
        )
        test_db.add(room)
        test_db.commit()
        test_db.refresh(room)

        # Crear jugadores
        host = Player(
            name="Host Player",
            avatar_src="avatar1.png",
            birthdate=date(1990, 1, 1),
            id_room=room.id,
            is_host=True,
            order=1
        )
        player2 = Player(
            name="Player 2",
            avatar_src="avatar2.png",
            birthdate=date(1991, 1, 1),
            id_room=room.id,
            is_host=False,
            order=2
        )
        test_db.add_all([host, player2])
        test_db.commit()

        # Player2 abandona
        response = client.delete(
            f"/game_join/{room.id}/leave",
            headers={"HTTP_USER_ID": str(player2.id)}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["is_host"] is False

        # Verificar que la sala NO fue eliminada
        test_db.expire_all()
        room_check = test_db.query(Room).filter(Room.id == room.id).first()
        assert room_check is not None

        # Verificar que solo player2 fue desvinculado
        host_check = test_db.query(Player).filter(Player.id == host.id).first()
        player2_check = test_db.query(Player).filter(Player.id == player2.id).first()
        assert host_check.id_room == room.id
        assert player2_check.id_room is None

    def test_room_not_found(self, test_db):
        """Test: Error 404 cuando la sala no existe"""
        response = client.delete(
            "/game_join/9999/leave",
            headers={"HTTP_USER_ID": "1"}
        )

        assert response.status_code == 404
        assert "sala" in response.json()["detail"].lower() or "room" in response.json()["detail"].lower()

    def test_player_not_in_room(self, test_db):
        """Test: Error 403 cuando el jugador no pertenece a la sala"""
        # Crear sala
        room = Room(
            name="Test Room",
            players_min=2,
            players_max=6,
            status=RoomStatus.WAITING,
            id_game=None
        )
        test_db.add(room)
        test_db.commit()

        # Crear jugador que NO está en la sala
        other_player = Player(
            name="Other Player",
            avatar_src="avatar.png",
            birthdate=date(1990, 1, 1),
            id_room=None,
            is_host=False,
            order=None
        )
        test_db.add(other_player)
        test_db.commit()

        # Intentar abandonar
        response = client.delete(
            f"/game_join/{room.id}/leave",
            headers={"HTTP_USER_ID": str(other_player.id)}
        )

        assert response.status_code == 403

    def test_game_already_started(self, test_db):
        """Test: Error 409 cuando la partida ya inició"""
        # Crear sala en estado INGAME
        room = Room(
            name="Test Room",
            players_min=2,
            players_max=6,
            status=RoomStatus.INGAME,
            id_game=1
        )
        test_db.add(room)
        test_db.commit()

        # Crear jugador
        player = Player(
            name="Player",
            avatar_src="avatar.png",
            birthdate=date(1990, 1, 1),
            id_room=room.id,
            is_host=False,
            order=1
        )
        test_db.add(player)
        test_db.commit()

        # Intentar abandonar
        response = client.delete(
            f"/game_join/{room.id}/leave",
            headers={"HTTP_USER_ID": str(player.id)}
        )

        assert response.status_code == 409

    def test_missing_user_id_header(self, test_db):
        """Test: Error 422 cuando falta el header HTTP_USER_ID"""
        response = client.delete("/game_join/123/leave")

        assert response.status_code == 422

    def test_invalid_room_id_type(self, test_db):
        """Test: Error 422 cuando room_id no es un número"""
        response = client.delete(
            "/game_join/abc/leave",
            headers={"HTTP_USER_ID": "123"}
        )

        assert response.status_code == 422

    def test_multiple_players_all_unlinked_when_host_cancels(self, test_db):
        """Test: Todos los jugadores son desvinculados cuando el host cancela"""
        # Crear sala
        room = Room(
            name="Test Room",
            players_min=2,
            players_max=6,
            status=RoomStatus.WAITING,
            id_game=None
        )
        test_db.add(room)
        test_db.commit()
        test_db.refresh(room)

        # Crear 4 jugadores
        players = [
            Player(name="Host", avatar_src="a1.png", birthdate=date(1990, 1, 1),
                   id_room=room.id, is_host=True, order=1),
            Player(name="P2", avatar_src="a2.png", birthdate=date(1991, 1, 1),
                   id_room=room.id, is_host=False, order=2),
            Player(name="P3", avatar_src="a3.png", birthdate=date(1992, 1, 1),
                   id_room=room.id, is_host=False, order=3),
            Player(name="P4", avatar_src="a4.png", birthdate=date(1993, 1, 1),
                   id_room=room.id, is_host=False, order=4),
        ]
        test_db.add_all(players)
        test_db.commit()

        # Host cancela
        response = client.delete(
            f"/game_join/{room.id}/leave",
            headers={"HTTP_USER_ID": str(players[0].id)}
        )

        assert response.status_code == 200

        # Verificar que TODOS fueron desvinculados
        test_db.expire_all()
        for player in players:
            player_check = test_db.query(Player).filter(Player.id == player.id).first()
            assert player_check.id_room is None