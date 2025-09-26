import pytest
import os
from unittest.mock import Mock, patch, AsyncMock

# Configurar variables de entorno antes de importar módulos de la app
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from app.services.game_service import (
    get_asesino,
    get_complice,
    finalizar_partida,
    procesar_ultima_carta,
    get_websocket_service_instance
)


class TestGameService:
    
    def test_get_asesino_encontrado(self):
        """Test que get_asesino retorna el ID correcto cuando existe un murderer"""
        game_state = {
            "players": [
                {"id": 1, "role": "innocent"},
                {"id": 2, "role": "murderer"},
                {"id": 3, "role": "detective"}
            ]
        }
        result = get_asesino(game_state)
        assert result == 2

    def test_get_asesino_no_encontrado(self):
        """Test que get_asesino retorna None cuando no hay murderer"""
        game_state = {
            "players": [
                {"id": 1, "role": "innocent"},
                {"id": 3, "role": "detective"}
            ]
        }
        result = get_asesino(game_state)
        assert result is None

    def test_get_complice_encontrado(self):
        """Test que get_complice retorna el ID correcto cuando existe un accomplice"""
        game_state = {
            "players": [
                {"id": 1, "role": "innocent"},
                {"id": 2, "role": "accomplice"},
                {"id": 3, "role": "detective"}
            ]
        }
        result = get_complice(game_state)
        assert result == 2

    @patch('app.services.game_service.SessionLocal')
    @patch('app.services.game_service.logger')
    @pytest.mark.asyncio
    async def test_finalizar_partida_exitoso(self, mock_logger, mock_session):
        """Test que finalizar_partida llama correctamente a la DB (sin usar DB real)"""
        # Setup mocks
        mock_db = Mock()
        mock_session.return_value = mock_db
        mock_room = Mock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_room
        
        # Execute
        winners = [{"role": "murderer", "player_id": 1}]
        await finalizar_partida(123, winners)
        
        # Verify interactions
        mock_db.query.assert_called_once()
        mock_db.add.assert_called_once_with(mock_room)
        mock_db.commit.assert_called_once()
        mock_db.close.assert_called_once()
        mock_logger.info.assert_called_once()

    @patch('app.services.game_service.SessionLocal')
    @pytest.mark.asyncio
    async def test_finalizar_partida_room_no_encontrada(self, mock_session):
        """Test que finalizar_partida lanza excepción cuando no encuentra la room"""
        # Setup mocks - room no encontrada
        mock_db = Mock()
        mock_session.return_value = mock_db
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        # Execute & verify exception
        with pytest.raises(ValueError, match="No se encontró room para game_id=123"):
            await finalizar_partida(123, [])
        
        # Verify db was closed even with exception
        mock_db.close.assert_called_once()

    @patch('app.services.game_service.get_websocket_service_instance')
    @patch('app.services.game_service.logger')
    @pytest.mark.asyncio
    async def test_procesar_ultima_carta_mazo_no_vacio(self, mock_logger, mock_ws_service):
        """Test que procesar_ultima_carta disminuye el mazo cuando no está vacío"""
        # Setup
        mock_ws = Mock()
        mock_ws_service.return_value = mock_ws
        
        game_state = {
            "deck": {"remaining": 5},
            "game": {"status": "playing"}
        }
        
        # Execute
        await procesar_ultima_carta(123, "some_card", game_state)
        
        # Verify
        assert game_state["deck"]["remaining"] == 4
        mock_ws.emit_to_room.assert_not_called()
        mock_logger.debug.assert_called_once()

    @patch('app.services.game_service.finalizar_partida')
    @patch('app.services.game_service.get_websocket_service_instance')
    @patch('app.services.game_service.logger')
    @pytest.mark.asyncio
    async def test_procesar_ultima_carta_fin_mazo_murderer_escapes(self, mock_logger, mock_ws_service, mock_finalizar):
        """Test procesar_ultima_carta con fin de mazo y murderer escape"""
        # Setup mocks
        mock_ws = Mock()
        mock_ws.emit_to_room = AsyncMock()
        mock_ws_service.return_value = mock_ws
        mock_finalizar.return_value = None
        
        game_state = {
            "deck": {"remaining": 1},
            "game": {"status": "playing"},
            "players": [
                {"id": 1, "role": "murderer"},
                {"id": 2, "role": "accomplice"},
                {"id": 3, "role": "innocent"}
            ]
        }
        
        # Execute
        await procesar_ultima_carta(123, "The murderer escapes", game_state)
        
        # Verify game state changes
        assert game_state["deck"]["remaining"] == 0
        assert game_state["game"]["status"] == "finished"
        assert len(game_state["winners"]) == 2
        
        expected_winners = [
            {"role": "murderer", "player_id": 1},
            {"role": "accomplice", "player_id": 2}
        ]
        assert game_state["winners"] == expected_winners
        
        # Verify function calls
        mock_finalizar.assert_called_once_with(123, expected_winners)
        assert mock_ws.emit_to_room.call_count == 2
        mock_logger.info.assert_called()

    @patch('app.services.game_service.finalizar_partida')
    @patch('app.services.game_service.get_websocket_service_instance')
    @pytest.mark.asyncio
    async def test_procesar_ultima_carta_fin_mazo_otra_carta(self, mock_ws_service, mock_finalizar):
        """Test procesar_ultima_carta con fin de mazo pero otra carta (no murderer escape)"""
        # Setup mocks
        mock_ws = Mock()
        mock_ws.emit_to_room = AsyncMock()
        mock_ws_service.return_value = mock_ws
        
        game_state = {
            "deck": {"remaining": 1},
            "game": {"status": "playing"},
            "players": [{"id": 1, "role": "innocent"}]
        }
        
        # Execute
        await procesar_ultima_carta(123, "other_card", game_state)
        
        # Verify
        assert game_state["winners"] == []
        assert game_state["game"]["status"] == "finished"
        mock_finalizar.assert_called_once_with(123, [])

    @patch('app.services.game_service.get_websocket_service')
    def test_get_websocket_service_instance_singleton(self, mock_get_ws):
        """Test que get_websocket_service_instance funciona como singleton"""
        # Reset global variable
        import app.services.game_service as game_service_module
        game_service_module.websocket_service = None
        
        mock_service = Mock()
        mock_get_ws.return_value = mock_service
        
        # Call twice
        result1 = get_websocket_service_instance()
        result2 = get_websocket_service_instance()
        
        # Verify singleton behavior
        assert result1 is result2
        assert result1 is mock_service
        mock_get_ws.assert_called_once()