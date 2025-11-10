import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from datetime import date
from unittest.mock import AsyncMock, patch
from app.db.database import Base
from app.db.models import Room, Player, RoomStatus
from app.services.leave_game_service import leave_game_logic

# Base de datos en memoria para tests
SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Crear tablas
Base.metadata.create_all(bind=engine)


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
def mock_websocket():
    """Mock del WebSocket service"""
    with patch('app.services.leave_game_service.get_websocket_service') as mock_ws:
        mock_ws_instance = AsyncMock()
        mock_ws_instance.notificar_game_cancelled = AsyncMock(return_value=None)
        mock_ws_instance.notificar_player_left = AsyncMock(return_value=None)
        mock_ws.return_value = mock_ws_instance
        yield mock_ws_instance


class TestLeaveGameService:
    """Tests para leave_game_logic service"""

    @pytest.mark.asyncio
    async def test_host_cancels_game_successfully(self, test_db, mock_websocket):
        """Test: Host cancela la partida exitosamente"""
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
            name="Host",
            avatar_src="avatar1.png",
            birthdate=date(1990, 1, 1),
            id_room=room.id,
            is_host=True,
            order=1
        )
        player2 = Player(
            name="Player2",
            avatar_src="avatar2.png",
            birthdate=date(1991, 1, 1),
            id_room=room.id,
            is_host=False,
            order=2
        )
        test_db.add_all([host, player2])
        test_db.commit()

        # Guardar IDs ANTES de ejecutar servicio
        host_id = host.id
        player2_id = player2.id

        # Ejecutar servicio
        result = await leave_game_logic(test_db, room.id, host_id)

        # Verificar resultado
        assert result["success"] is True
        assert result["is_host"] is True
        assert "cancel" in result["message"].lower()
        assert result["error"] is None

        # Verificar que la sala fue eliminada
        room_check = test_db.query(Room).filter(Room.id == room.id).first()
        assert room_check is None

        # Verificar que todos los jugadores fueron eliminados
        host_check = test_db.query(Player).filter(Player.id == host_id).first()
        player2_check = test_db.query(Player).filter(Player.id == player2_id).first()
        assert host_check is None
        assert player2_check is None

        # Verificar que se llamó al WebSocket
        mock_websocket.notificar_game_cancelled.assert_called_once()
        call_args = mock_websocket.notificar_game_cancelled.call_args
        assert call_args.kwargs['room_id'] == room.id

    @pytest.mark.asyncio
    async def test_player_leaves_game_successfully(self, test_db, mock_websocket):
        """Test: Jugador abandona la partida exitosamente"""
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
            name="Host",
            avatar_src="avatar1.png",
            birthdate=date(1990, 1, 1),
            id_room=room.id,
            is_host=True,
            order=1
        )
        player2 = Player(
            name="Player2",
            avatar_src="avatar2.png",
            birthdate=date(1991, 1, 1),
            id_room=room.id,
            is_host=False,
            order=2
        )
        test_db.add_all([host, player2])
        test_db.commit()

        # Ejecutar servicio
        result = await leave_game_logic(test_db, room.id, player2.id)

        # Guardar IDs antes de que los objetos se vuelvan inválidos
        host_id = host.id
        player2_id = player2.id

        # Verificar resultado
        assert result["success"] is True
        assert result["is_host"] is False
        assert "left" in result["message"].lower()
        assert result["error"] is None

        # Verificar que la sala NO fue eliminada
        test_db.expire_all()
        room_check = test_db.query(Room).filter(Room.id == room.id).first()
        assert room_check is not None

        # Verificar que solo player2 fue eliminado (no solo desvinculado)
        host_check = test_db.query(Player).filter(Player.id == host_id).first()
        player2_check = test_db.query(Player).filter(Player.id == player2_id).first()
        assert host_check is not None
        assert host_check.id_room == room.id
        assert player2_check is None  # Eliminado completamente

        # Verificar que se llamó al WebSocket
        mock_websocket.notificar_player_left.assert_called_once()
        call_args = mock_websocket.notificar_player_left.call_args
        assert call_args.kwargs['room_id'] == room.id
        assert call_args.kwargs['player_id'] == player2_id
        assert call_args.kwargs['players_count'] == 1
        assert len(call_args.kwargs['players']) == 1

    @pytest.mark.asyncio
    async def test_room_not_found(self, test_db):
        """Test: Error cuando la sala no existe"""
        result = await leave_game_logic(test_db, 9999, 1)

        assert result["success"] is False
        assert result["error"] == "room_not_found"

    @pytest.mark.asyncio
    async def test_game_already_started(self, test_db):
        """Test: Error cuando la partida ya inició"""
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

        result = await leave_game_logic(test_db, room.id, player.id)

        assert result["success"] is False
        assert result["error"] == "game_already_started"

    @pytest.mark.asyncio
    async def test_player_not_in_room(self, test_db):
        """Test: Error cuando el jugador no pertenece a la sala"""
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
            name="Other",
            avatar_src="avatar.png",
            birthdate=date(1990, 1, 1),
            id_room=None,
            is_host=False,
            order=None
        )
        test_db.add(other_player)
        test_db.commit()

        result = await leave_game_logic(test_db, room.id, other_player.id)

        assert result["success"] is False
        assert result["error"] == "player_not_in_room"

    @pytest.mark.asyncio
    async def test_multiple_players_all_unlinked_when_host_cancels(self, test_db, mock_websocket):
        """Test: Todos los jugadores son eliminados cuando host cancela"""
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

        # Crear 5 jugadores
        players = []
        for i in range(5):
            p = Player(
                name=f"Player{i}",
                avatar_src=f"avatar{i}.png",
                birthdate=date(1990 + i, 1, 1),
                id_room=room.id,
                is_host=(i == 0),
                order=i + 1
            )
            players.append(p)
        
        test_db.add_all(players)
        test_db.commit()

        # Guardar IDs ANTES de ejecutar servicio
        player_ids = [p.id for p in players]
        host_id = player_ids[0]

        # Host cancela
        result = await leave_game_logic(test_db, room.id, host_id)

        assert result["success"] is True
        assert result["is_host"] is True

        # Verificar que TODOS fueron eliminados completamente
        for player_id in player_ids:
            p_check = test_db.query(Player).filter(Player.id == player_id).first()
            assert p_check is None

    @pytest.mark.asyncio
    async def test_player_leaves_updates_remaining_players_list(self, test_db, mock_websocket):
        """Test: Lista de jugadores restantes es enviada correctamente"""
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

        # Crear 3 jugadores
        host = Player(name="Host", avatar_src="a1.png", birthdate=date(1990, 1, 1),
                      id_room=room.id, is_host=True, order=1)
        p2 = Player(name="P2", avatar_src="a2.png", birthdate=date(1991, 1, 1),
                    id_room=room.id, is_host=False, order=2)
        p3 = Player(name="P3", avatar_src="a3.png", birthdate=date(1992, 1, 1),
                    id_room=room.id, is_host=False, order=3)
        
        test_db.add_all([host, p2, p3])
        test_db.commit()

        # P2 abandona
        result = await leave_game_logic(test_db, room.id, p2.id)

        # Guardar IDs antes de operaciones futuras
        host_id = host.id
        p3_id = p3.id
        p2_id = p2.id

        assert result["success"] is True

        # Verificar datos enviados al WebSocket
        call_args = mock_websocket.notificar_player_left.call_args
        players_data = call_args.kwargs['players']
        
        assert len(players_data) == 2  # Solo host y p3
        assert call_args.kwargs['players_count'] == 2
        
        # Verificar estructura de jugadores
        player_ids_in_data = [p['id'] for p in players_data]
        assert host_id in player_ids_in_data
        assert p3_id in player_ids_in_data
        assert p2_id not in player_ids_in_data
        
        # Verificar que p2 fue eliminado completamente de la BD
        test_db.expire_all()
        p2_check = test_db.query(Player).filter(Player.id == p2_id).first()
        assert p2_check is None

    @pytest.mark.asyncio
    async def test_handles_exception_gracefully(self, test_db, mock_websocket):
        """Test: Maneja excepciones y retorna error"""
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

        # Hacer que el WebSocket falle
        mock_websocket.notificar_player_left.side_effect = Exception("WebSocket error")

        # Ejecutar servicio
        result = await leave_game_logic(test_db, room.id, player.id)

        # Debe retornar error
        assert result["success"] is False
        assert result["error"] == "internal_error"

    @pytest.mark.asyncio
    async def test_websocket_called_with_correct_parameters_for_host(self, test_db, mock_websocket):
        """Test: WebSocket es llamado con parámetros correctos (host)"""
        room = Room(name="Test", players_min=2, players_max=6, status=RoomStatus.WAITING)
        test_db.add(room)
        test_db.commit()
        test_db.refresh(room)

        host = Player(name="Host", avatar_src="a.png", birthdate=date(1990, 1, 1),
                      id_room=room.id, is_host=True, order=1)
        test_db.add(host)
        test_db.commit()

        await leave_game_logic(test_db, room.id, host.id)

        # Verificar llamada
        mock_websocket.notificar_game_cancelled.assert_called_once()
        call_kwargs = mock_websocket.notificar_game_cancelled.call_args.kwargs
        
        assert call_kwargs['room_id'] == room.id
        assert 'timestamp' in call_kwargs

    @pytest.mark.asyncio
    async def test_websocket_called_with_correct_parameters_for_player(self, test_db, mock_websocket):
        """Test: WebSocket es llamado con parámetros correctos (jugador)"""
        room = Room(name="Test", players_min=2, players_max=6, status=RoomStatus.WAITING)
        test_db.add(room)
        test_db.commit()
        test_db.refresh(room)

        host = Player(name="Host", avatar_src="a.png", birthdate=date(1990, 1, 1),
                      id_room=room.id, is_host=True, order=1)
        player = Player(name="Player", avatar_src="b.png", birthdate=date(1991, 1, 1),
                        id_room=room.id, is_host=False, order=2)
        test_db.add_all([host, player])
        test_db.commit()

        # Guardar IDs
        host_id = host.id
        player_id = player.id

        await leave_game_logic(test_db, room.id, player_id)

        # Verificar llamada
        mock_websocket.notificar_player_left.assert_called_once()
        call_kwargs = mock_websocket.notificar_player_left.call_args.kwargs
        
        assert call_kwargs['room_id'] == room.id
        assert call_kwargs['player_id'] == player_id
        assert call_kwargs['players_count'] == 1
        assert isinstance(call_kwargs['players'], list)
        assert 'timestamp' in call_kwargs