# app/tests/test_game_service.py
import pytest
import os
from unittest.mock import Mock, patch, AsyncMock

# Config vars before imports
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from app.services.game_service import (
    get_asesino,
    get_complice,
    finalizar_partida,
    procesar_ultima_carta
)


class TestGameService:
    def test_get_asesino_encontrado(self):
        game_state = {
            "players": [
                {"id": 1, "role": "innocent"},
                {"id": 2, "role": "murderer"},
                {"id": 3, "role": "detective"}
            ]
        }
        assert get_asesino(game_state) == 2

    def test_get_asesino_no_encontrado(self):
        game_state = {"players": [{"id": 1, "role": "innocent"}]}
        assert get_asesino(game_state) is None
    
    def test_get_asesino_game_state_vacio(self):
        """Test con game_state sin players"""
        game_state = {}
        assert get_asesino(game_state) is None

    def test_get_complice_encontrado(self):
        game_state = {
            "players": [
                {"id": 1, "role": "innocent"},
                {"id": 2, "role": "accomplice"},
            ]
        }
        assert get_complice(game_state) == 2

    def test_get_complice_no_encontrado(self):
        game_state = {"players": [{"id": 1, "role": "innocent"}]}
        assert get_complice(game_state) is None
    
    def test_get_complice_game_state_vacio(self):
        """Test con game_state sin players"""
        game_state = {}
        assert get_complice(game_state) is None

    @patch('app.services.game_service.SessionLocal')
    @patch('app.services.game_service.logger')
    @pytest.mark.asyncio
    async def test_finalizar_partida_exitoso(self, mock_logger, mock_session):
        mock_db = Mock()
        mock_session.return_value = mock_db
        mock_room = Mock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_room
        
        winners = [{"role": "murderer", "player_id": 1}]
        
        await finalizar_partida(123, winners)
        
        mock_db.add.assert_called_once_with(mock_room)
        mock_db.commit.assert_called_once()
        mock_db.close.assert_called_once()
        mock_logger.info.assert_called_once()

    @patch('app.services.game_service.SessionLocal')
    @pytest.mark.asyncio
    async def test_finalizar_partida_room_no_encontrada(self, mock_session):
        mock_db = Mock()
        mock_session.return_value = mock_db
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        with pytest.raises(ValueError, match="No se encontró room para game_id=123"):
            await finalizar_partida(123, [])
        
        mock_db.close.assert_called_once()

    @patch('app.sockets.socket_service.get_websocket_service')
    @pytest.mark.asyncio
    async def test_procesar_ultima_carta_mazo_no_vacio(self, mock_ws_service):
        mock_ws = Mock()
        mock_ws_service.return_value = mock_ws
        
        game_state = {
            "mazos": {"deck": 5},
            "status": "INGAME"
        }
        
        # Since deck != 0, should do nothing
        await procesar_ultima_carta(123, 1, "some_card", game_state, 42)
        
        assert game_state["status"] == "INGAME"
        mock_ws.notificar_estado_partida.assert_not_called()

    @patch('app.services.game_service.finalizar_partida', new_callable=AsyncMock)
    @patch('app.sockets.socket_service.get_websocket_service')
    @pytest.mark.asyncio
    async def test_procesar_ultima_carta_mazo_vacio_murderer_wins(self, mock_ws_service, mock_finalizar):
        """Test when deck is empty and Murder Escapes card is played"""
        mock_ws = Mock()
        mock_ws.notificar_estado_partida = AsyncMock()
        mock_ws_service.return_value = mock_ws
        
        game_state = {
            "mazos": {"deck": 0},
            "status": "INGAME",
            "secretos": {
                "1": [{"name": "Secret Murderer"}],
                "2": [{"name": "Secret Accomplice"}]
            }
        }
        
        await procesar_ultima_carta(123, 1, "Murder Escapes", game_state, 42)
        
        assert game_state["status"] == "FINISH"
        assert game_state["game_finished"] is True
        assert game_state["finish_reason"] == "deck_exhausted_murderer_wins"
        assert len(game_state["winners"]) == 2
        mock_ws.notificar_estado_partida.assert_called_once()
        mock_finalizar.assert_called_once()

    @patch('app.services.game_service.finalizar_partida', new_callable=AsyncMock)
    @patch('app.sockets.socket_service.get_websocket_service')
    @pytest.mark.asyncio
    async def test_procesar_ultima_carta_mazo_vacio_sin_murderer_wins(self, mock_ws_service, mock_finalizar):
        """Test when deck is empty but carta is not Murder Escapes"""
        mock_ws = Mock()
        mock_ws.notificar_estado_partida = AsyncMock()
        mock_ws_service.return_value = mock_ws
        
        game_state = {
            "mazos": {"deck": 0},
            "status": "INGAME",
            "secretos": {}
        }
        
        await procesar_ultima_carta(123, 1, "Other Card", game_state, 42)
        
        assert game_state["status"] == "FINISH"
        assert game_state["game_finished"] is True
        assert game_state["winners"] == []
        mock_ws.notificar_estado_partida.assert_called_once()
        mock_finalizar.assert_called_once()