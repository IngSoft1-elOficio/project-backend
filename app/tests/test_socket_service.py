# tests/test_socket_service.py
import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime
from app.sockets.socket_service import WebSocketService, get_websocket_service

@pytest.fixture
def mock_sio():
    client_mock = Mock()
    client_mock.connect = Mock()
    client_mock.emit = Mock()
    client_mock.on = Mock()
    client_mock.disconnect = Mock()
    return client_mock

@pytest.fixture
def mock_ws_manager():
    """Mock del WebSocket manager"""
    manager = Mock()
    manager.get_sids_in_game = AsyncMock()
    manager.emit_to_room = AsyncMock()
    manager.emit_to_sid = AsyncMock()
    manager.get_user_session = Mock()
    return manager


@pytest.fixture
def websocket_service(mock_ws_manager):
    """Fixture del WebSocketService con manager mockeado"""
    with patch('app.sockets.socket_service.get_ws_manager', return_value=mock_ws_manager):
        service = WebSocketService()
        return service


@pytest.fixture
def sample_game_state():
    """Estado de juego de ejemplo para las pruebas"""
    return {
        "turno_actual": 1,
        "jugadores": [{"id": 1, "nombre": "Player1"}, {"id": 2, "nombre": "Player2"}],
        "mazos": {"mazo_principal": 30, "mazo_descarte": 5},
        "manos": {
            1: [{"id": "carta1", "nombre": "Carta A"}, {"id": "carta2", "nombre": "Carta B"}],
            2: [{"id": "carta3", "nombre": "Carta C"}]
        },
        "secretos": {
            1: ["secreto1", "secreto2"],
            2: ["secreto3"]
        }
    }


class TestWebSocketService:
    """Tests para la clase WebSocketService"""

    def test_init(self, mock_ws_manager):
        """Test de inicialización del servicio"""
        with patch('app.sockets.socket_service.get_ws_manager', return_value=mock_ws_manager):
            service = WebSocketService()
            assert service.ws_manager == mock_ws_manager

    @pytest.mark.asyncio
    async def test_notificar_estado_partida_room_vacio(self, websocket_service, mock_ws_manager):
        """Test cuando no hay jugadores en el room"""
        # Configurar mock para room vacío
        mock_ws_manager.get_sids_in_game.return_value = []
        
        with patch('app.sockets.socket_service.logger') as mock_logger:
            await websocket_service.notificar_estado_partida(game_id=1)
            
            # Verificar que se loggea warning y no se emiten mensajes
            mock_logger.warning.assert_called_once_with("room 1 vacia")
            mock_ws_manager.emit_to_room.assert_not_called()
            mock_ws_manager.emit_to_sid.assert_not_called()

    @pytest.mark.asyncio
    async def test_notificar_estado_partida_completo(
        self, websocket_service, mock_ws_manager, sample_game_state
    ):
        """Test completo de notificación con todos los parámetros"""
        # Configurar mocks
        sids = ["sid1", "sid2"]
        mock_ws_manager.get_sids_in_game.return_value = sids
        mock_ws_manager.get_user_session.side_effect = [
            {"user_id": 1},
            {"user_id": 2},
            {"user_id": 1},  # Segunda llamada para feedback
            {"user_id": 2}   # Segunda llamada para partida_finalizada
        ]

        with patch('app.sockets.socket_service.datetime') as mock_datetime:
            mock_datetime.now.return_value.isoformat.return_value = "2023-01-01T12:00:00"

            await websocket_service.notificar_estado_partida(
                game_id=1,
                jugador_que_actuo=1,
                game_state=sample_game_state,
                partida_finalizada=True,
                ganador_id=1
            )

            # Verificar mensaje público
            mock_ws_manager.emit_to_room.assert_called_once_with(
                1, "game_state_public", {
                    "type": "game_state_public",
                    "game_id": 1,
                    "turno_actual": 1,
                    "jugadores": sample_game_state["jugadores"],
                    "mazos": sample_game_state["mazos"],
                    "timestamp": "2023-01-01T12:00:00"
                }
            )

            # Debug: imprimir las llamadas para entender qué pasó
            print(f"Número de llamadas a emit_to_sid: {mock_ws_manager.emit_to_sid.call_count}")
            for i, call in enumerate(mock_ws_manager.emit_to_sid.call_args_list):
                print(f"Llamada {i+1}: {call[0][1]}")  # Imprime el tipo de evento
            
            # Verificar que se llamó emit_to_sid las veces correctas
            # Analizar exactamente cuántas llamadas se hicieron
            assert mock_ws_manager.emit_to_sid.call_count >= 4  # Al menos mensajes privados para ambos jugadores

    @pytest.mark.asyncio
    async def test_mensajes_privados_por_jugador(
        self, websocket_service, mock_ws_manager, sample_game_state
    ):
        """Test específico de los mensajes privados para cada jugador"""
        sids = ["sid1", "sid2"]
        mock_ws_manager.get_sids_in_game.return_value = sids
        mock_ws_manager.get_user_session.side_effect = [
            {"user_id": 1},
            {"user_id": 2}
        ]

        with patch('app.sockets.socket_service.datetime') as mock_datetime:
            mock_datetime.now.return_value.isoformat.return_value = "2023-01-01T12:00:00"

            await websocket_service.notificar_estado_partida(
                game_id=1,
                game_state=sample_game_state
            )

            # Verificar mensajes privados específicos
            calls = mock_ws_manager.emit_to_sid.call_args_list
            
            # Primer mensaje privado (jugador 1)
            assert calls[0][0] == ("sid1", "game_state_private", {
                "type": "game_state_private",
                "user_id": 1,
                "mano": sample_game_state["manos"][1],
                "secretos": sample_game_state["secretos"][1],
                "timestamp": "2023-01-01T12:00:00"
            })
            
            # Segundo mensaje privado (jugador 2)
            assert calls[1][0] == ("sid2", "game_state_private", {
                "type": "game_state_private",
                "user_id": 2,
                "mano": sample_game_state["manos"][2],
                "secretos": sample_game_state["secretos"][2],
                "timestamp": "2023-01-01T12:00:00"
            })

    @pytest.mark.asyncio
    async def test_feedback_jugador_que_actuo(
        self, websocket_service, mock_ws_manager
    ):
        """Test del feedback al jugador que actuó"""
        sids = ["sid1", "sid2"]
        mock_ws_manager.get_sids_in_game.return_value = sids
        mock_ws_manager.get_user_session.side_effect = [
            {"user_id": 1},
            {"user_id": 2}
        ]

        with patch('app.sockets.socket_service.datetime') as mock_datetime:
            mock_datetime.now.return_value.isoformat.return_value = "2023-01-01T12:00:00"

            await websocket_service.notificar_estado_partida(
                game_id=1,
                jugador_que_actuo=1
            )

            # Buscar el call del feedback
            calls = mock_ws_manager.emit_to_sid.call_args_list
            feedback_call = next(
                call for call in calls 
                if call[0][1] == "player_action_result"
            )
            
            assert feedback_call[0] == ("sid1", "player_action_result", {
                "type": "player_action_result",
                "success": True,
                "mensaje": "Accion valida",
                "timestamp": "2023-01-01T12:00:00"
            })

    @pytest.mark.asyncio
    async def test_partida_finalizada(
        self, websocket_service, mock_ws_manager
    ):
        """Test de notificación cuando la partida finaliza"""
        sids = ["sid1", "sid2"]
        mock_ws_manager.get_sids_in_game.return_value = sids
        mock_ws_manager.get_user_session.side_effect = [
            {"user_id": 1},
            {"user_id": 2}
        ]

        with patch('app.sockets.socket_service.datetime') as mock_datetime:
            mock_datetime.now.return_value.isoformat.return_value = "2023-01-01T12:00:00"

            await websocket_service.notificar_estado_partida(
                game_id=1,
                partida_finalizada=True,
                ganador_id=1
            )

            # Verificar mensajes de game_ended
            calls = mock_ws_manager.emit_to_sid.call_args_list
            game_ended_calls = [
                call for call in calls 
                if call[0][1] == "game_ended"
            ]
            
            # Jugador ganador
            assert game_ended_calls[0][0] == ("sid1", "game_ended", {
                "type": "game_ended",
                "user_id": 1,
                "ganaste": True,
                "timestamp": "2023-01-01T12:00:00"
            })
            
            # Jugador perdedor
            assert game_ended_calls[1][0] == ("sid2", "game_ended", {
                "type": "game_ended",
                "user_id": 2,
                "ganaste": False,
                "timestamp": "2023-01-01T12:00:00"
            })

    @pytest.mark.asyncio
    async def test_session_inexistente(
        self, websocket_service, mock_ws_manager
    ):
        """Test cuando no se puede obtener la sesión de un usuario"""
        sids = ["sid1", "sid_invalido"]
        mock_ws_manager.get_sids_in_game.return_value = sids
        mock_ws_manager.get_user_session.side_effect = [
            {"user_id": 1},
            None  # Sesión inexistente
        ]

        await websocket_service.notificar_estado_partida(game_id=1)

        # Verificar que solo se envía mensaje al usuario válido
        calls = mock_ws_manager.emit_to_sid.call_args_list
        sids_called = [call[0][0] for call in calls]
        
        assert "sid1" in sids_called
        assert "sid_invalido" not in sids_called

    @pytest.mark.asyncio
    async def test_sin_game_state(
        self, websocket_service, mock_ws_manager
    ):
        """Test cuando no se proporciona game_state"""
        sids = ["sid1"]
        mock_ws_manager.get_sids_in_game.return_value = sids
        mock_ws_manager.get_user_session.return_value = {"user_id": 1}

        with patch('app.sockets.socket_service.datetime') as mock_datetime:
            mock_datetime.now.return_value.isoformat.return_value = "2023-01-01T12:00:00"

            await websocket_service.notificar_estado_partida(
                game_id=1,
                jugador_que_actuo=1
            )

            # Verificar mensaje público con valores por defecto
            mock_ws_manager.emit_to_room.assert_called_once_with(
                1, "game_state_public", {
                    "type": "game_state_public",
                    "game_id": 1,
                    "turno_actual": 1,
                    "jugadores": [],
                    "mazos": {},
                    "timestamp": "2023-01-01T12:00:00"
                }
            )

            # Verificar mensaje privado con listas vacías
            calls = mock_ws_manager.emit_to_sid.call_args_list
            private_call = next(
                call for call in calls 
                if call[0][1] == "game_state_private"
            )
            
            assert private_call[0][2]["mano"] == []
            assert private_call[0][2]["secretos"] == []


class TestGetWebSocketService:
    """Tests para la función factory get_websocket_service"""

    def test_singleton_behavior(self):
        """Test que verifica el comportamiento singleton"""
        # Resetear el singleton
        import app.sockets.socket_service
        app.sockets.socket_service._websocket_service = None
        
        with patch('app.sockets.socket_service.get_ws_manager'):
            service1 = get_websocket_service()
            service2 = get_websocket_service()
            
            assert service1 is service2

    def test_creates_instance_when_none(self):
        """Test que crea instancia cuando es None"""
        import app.sockets.socket_service
        app.sockets.socket_service._websocket_service = None
        
        with patch('app.sockets.socket_service.get_ws_manager') as mock_get_manager:
            mock_manager = Mock()
            mock_get_manager.return_value = mock_manager
            
            service = get_websocket_service()
            
            assert isinstance(service, WebSocketService)
            assert service.ws_manager == mock_manager


# Configuración adicional para pytest
@pytest.fixture(autouse=True)
def reset_singleton():
    """Fixture que resetea el singleton después de cada test"""
    yield
    import app.sockets.socket_service
    app.sockets.socket_service._websocket_service = None