# app/tests/test_game_service.py
import pytest
import os
from unittest.mock import Mock, patch, AsyncMock
from app.services.game_service import procesar_ultima_carta

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

@pytest.mark.asyncio
async def test_procesar_ultima_carta_mazo_no_vacio():
    """Si el mazo tiene más de 1 carta, no debe notificar fin de partida"""
    with patch('app.sockets.socket_service.get_websocket_service') as mock_ws_service, \
         patch('app.services.game_service.finalizar_partida', new_callable=AsyncMock) as mock_finalizar:
        mock_ws = Mock()
        mock_ws_service.return_value = mock_ws

        game_state = {
            "mazos": {"deck": {"count": 5, "draft": [{"id": 1}, {"id": 2}]}},  # mazo > 1, draft no vacío
            "jugadores": [],
            "estados_privados": {}
        }

        await procesar_ultima_carta(123, 1, game_state)
        mock_ws.notificar_fin_partida.assert_not_called()
        mock_finalizar.assert_not_called()


@pytest.mark.asyncio
async def test_procesar_ultima_carta_mazo_vacio_murderer_wins():
    """Si el mazo queda en 1 carta, debe notificar fin y winners correctos"""
    with patch('app.sockets.socket_service.get_websocket_service') as mock_ws_service, \
         patch('app.services.game_service.finalizar_partida', new_callable=AsyncMock) as mock_finalizar:

        mock_ws = Mock()
        mock_ws.notificar_fin_partida = AsyncMock()
        mock_ws_service.return_value = mock_ws

        game_state = {
            "mazos": {"deck": {"count": 1}},  # última carta
            "jugadores": [
                {"player_id": 1, "name": "Alice", "avatar_src": "avatar1.png"},
                {"player_id": 2, "name": "Bob", "avatar_src": "avatar2.png"}
            ],
            "estados_privados": {
                1: {"secretos": [{"name": "You are the Murderer!!"}]},
                2: {"secretos": [{"name": "You are the Accomplice!"}]}
            }
        }

        await procesar_ultima_carta(123, 42, game_state)

        winners = mock_finalizar.call_args[0][1]
        assert len(winners) == 2
        assert any(w["role"] == "murderer" and w["player_id"] == 1 for w in winners)
        assert any(w["role"] == "accomplice" and w["player_id"] == 2 for w in winners)

        mock_ws.notificar_fin_partida.assert_awaited_once_with(
            room_id=42,
            winners=winners,
            reason="deck_empty"
        )
        mock_finalizar.assert_awaited_once()


@pytest.mark.asyncio
async def test_procesar_ultima_carta_mazo_vacio_sin_winners():
    """Si el mazo queda en 1 carta pero no hay winners, debe notificar fin con lista vacía"""
    with patch('app.sockets.socket_service.get_websocket_service') as mock_ws_service, \
         patch('app.services.game_service.finalizar_partida', new_callable=AsyncMock) as mock_finalizar:

        mock_ws = Mock()
        mock_ws.notificar_fin_partida = AsyncMock()
        mock_ws_service.return_value = mock_ws

        game_state = {
            "mazos": {"deck": {"count": 1}},
            "jugadores": [
                {"player_id": 1, "name": "Alice", "avatar_src": "avatar1.png"}
            ],
            "estados_privados": {
                1: {"secretos": [{"name": "Other Secret"}]}
            }
        }

        await procesar_ultima_carta(123, 42, game_state)

        winners = mock_finalizar.call_args[0][1]
        assert winners == []

        mock_ws.notificar_fin_partida.assert_awaited_once_with(
            room_id=42,
            winners=[],
            reason="deck_empty"
        )
        mock_finalizar.assert_awaited_once()