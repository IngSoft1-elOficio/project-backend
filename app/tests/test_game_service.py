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

@pytest.mark.asyncio
async def test_win_for_total_disgrace_victoria_malos():
    """Test victoria cuando todos los buenos están en desgracia"""
    with patch('app.services.game_service.SessionLocal') as mock_session_local, \
         patch('app.services.game_service.get_players_in_social_disgrace') as mock_get_disgrace, \
         patch('app.services.game_service._get_accomplice', new_callable=AsyncMock) as mock_get_accomplice, \
         patch('app.services.game_service._end_game_with_winners', new_callable=AsyncMock) as mock_end_game:
        
        # Setup mocks
        mock_db = Mock()
        mock_session_local.return_value = mock_db
        
        # Mock room
        mock_room = Mock()
        mock_room.id = 100
        
        # Mock murderer secret
        mock_murderer_secret = Mock()
        mock_murderer_secret.player_id = 1
        
        # Mock accomplice
        mock_get_accomplice.return_value = 2
        
        # Mock players (1=murderer, 2=accomplice, 3=detective, 4=detective)
        mock_players = [
            Mock(id=1, name="Murderer"),
            Mock(id=2, name="Accomplice"),
            Mock(id=3, name="Detective1"),
            Mock(id=4, name="Detective2")
        ]
        
        # Mock get_players_in_social_disgrace (todos los detectives en desgracia)
        mock_get_disgrace.return_value = [
            {"player_id": 3, "player_name": "Detective1"},
            {"player_id": 4, "player_name": "Detective2"}
        ]
        
        # Configurar queries separadas para cada llamada
        mock_room_query = Mock()
        mock_room_query.filter.return_value.first.return_value = mock_room
        
        mock_secret_query = Mock()
        mock_secret_join = Mock()
        mock_secret_join.filter.return_value.first.return_value = mock_murderer_secret
        mock_secret_query.join.return_value = mock_secret_join
        
        mock_player_query = Mock()
        mock_player_query.filter.return_value.all.return_value = mock_players
        
        # Configurar side_effect para retornar queries diferentes según el modelo
        def query_side_effect(model):
            if model.__name__ == 'Room':
                return mock_room_query
            elif model.__name__ == 'CardsXGame':
                return mock_secret_query
            elif model.__name__ == 'Player':
                return mock_player_query
            return Mock()
        
        mock_db.query.side_effect = query_side_effect
        
        # Ejecutar
        from app.services.game_service import win_for_total_disgrace
        result = await win_for_total_disgrace(mock_db, 123)
        
        # Verificar
        assert result is True
        mock_end_game.assert_awaited_once()
        
        # Verificar que se llamó con los winners correctos
        call_kwargs = mock_end_game.call_args[1]
        assert call_kwargs["game_id"] == 123
        assert call_kwargs["reason"] == "TOTAL_DISGRACE"
        winners = call_kwargs["winners"]
        assert len(winners) == 2
        assert any(w["player_id"] == 1 for w in winners)
        assert any(w["player_id"] == 2 for w in winners)
        
        mock_db.close.assert_called_once()


@pytest.mark.asyncio
async def test_win_for_total_disgrace_no_victoria_detective_sin_desgracia():
    """Test cuando hay al menos un detective NO en desgracia"""
    with patch('app.services.game_service.SessionLocal') as mock_session_local, \
         patch('app.services.game_service.get_players_in_social_disgrace') as mock_get_disgrace, \
         patch('app.services.game_service._get_accomplice', new_callable=AsyncMock) as mock_get_accomplice, \
         patch('app.services.game_service._end_game_with_winners', new_callable=AsyncMock) as mock_end_game:
        
        mock_db = Mock()
        mock_session_local.return_value = mock_db
        
        mock_room = Mock()
        mock_room.id = 100
        mock_db.query.return_value.filter.return_value.first.return_value = mock_room
        
        mock_murderer_secret = Mock()
        mock_murderer_secret.player_id = 1
        
        mock_get_accomplice.return_value = 2
        
        mock_players = [
            Mock(id=1, name="Murderer"),
            Mock(id=2, name="Accomplice"),
            Mock(id=3, name="Detective1"),
            Mock(id=4, name="Detective2")
        ]
        
        # Solo el detective 3 está en desgracia, el 4 NO
        mock_get_disgrace.return_value = [
            {"player_id": 3, "player_name": "Detective1"}
        ]
        
        def side_effect_query(*args):
            query_mock = Mock()
            if args[0] == models.CardsXGame:
                query_mock.join.return_value.filter.return_value.first.return_value = mock_murderer_secret
            elif args[0] == models.Player:
                query_mock.filter.return_value.all.return_value = mock_players
            return query_mock
        
        mock_db.query.side_effect = side_effect_query
        
        from app.services.game_service import win_for_total_disgrace
        result = await win_for_total_disgrace(mock_db, 123)
        
        # No debe terminar el juego
        assert result is False
        mock_end_game.assert_not_awaited()
        mock_db.close.assert_called_once()


@pytest.mark.asyncio
async def test_win_for_total_disgrace_room_not_found():
    """Test cuando no se encuentra el room"""
    with patch('app.services.game_service.SessionLocal') as mock_session_local:
        mock_db = Mock()
        mock_session_local.return_value = mock_db
        
        # Room no encontrado
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        from app.services.game_service import win_for_total_disgrace
        result = await win_for_total_disgrace(mock_db, 123)
        
        assert result is False
        mock_db.close.assert_called_once()


@pytest.mark.asyncio
async def test_win_for_total_disgrace_murderer_not_found():
    """Test cuando no se encuentra el asesino"""
    with patch('app.services.game_service.SessionLocal') as mock_session_local:
        mock_db = Mock()
        mock_session_local.return_value = mock_db
        
        mock_room = Mock()
        mock_room.id = 100
        
        def side_effect_query(*args):
            query_mock = Mock()
            if args[0] == models.Room:
                query_mock.filter.return_value.first.return_value = mock_room
            elif args[0] == models.CardsXGame:
                # Murderer secret no encontrado
                query_mock.join.return_value.filter.return_value.first.return_value = None
            return query_mock
        
        mock_db.query.side_effect = side_effect_query
        
        from app.services.game_service import win_for_total_disgrace
        result = await win_for_total_disgrace(mock_db, 123)
        
        assert result is False
        mock_db.close.assert_called_once()


@pytest.mark.asyncio
async def test_win_for_total_disgrace_murderer_without_player_id():
    """Test cuando el murderer secret no tiene player_id"""
    with patch('app.services.game_service.SessionLocal') as mock_session_local:
        mock_db = Mock()
        mock_session_local.return_value = mock_db
        
        mock_room = Mock()
        mock_room.id = 100
        
        # Murderer secret sin player_id
        mock_murderer_secret = Mock()
        mock_murderer_secret.player_id = None
        
        def side_effect_query(*args):
            query_mock = Mock()
            if args[0] == models.Room:
                query_mock.filter.return_value.first.return_value = mock_room
            elif args[0] == models.CardsXGame:
                query_mock.join.return_value.filter.return_value.first.return_value = mock_murderer_secret
            return query_mock
        
        mock_db.query.side_effect = side_effect_query
        
        from app.services.game_service import win_for_total_disgrace
        result = await win_for_total_disgrace(mock_db, 123)
        
        assert result is False
        mock_db.close.assert_called_once()


@pytest.mark.asyncio
async def test_win_for_total_disgrace_no_players():
    """Test cuando no hay jugadores en el juego"""
    with patch('app.services.game_service.SessionLocal') as mock_session_local, \
         patch('app.services.game_service._get_accomplice', new_callable=AsyncMock) as mock_get_accomplice:
        
        mock_db = Mock()
        mock_session_local.return_value = mock_db
        
        mock_room = Mock()
        mock_room.id = 100
        
        mock_murderer_secret = Mock()
        mock_murderer_secret.player_id = 1
        
        mock_get_accomplice.return_value = 2
        
        def side_effect_query(*args):
            query_mock = Mock()
            if args[0] == models.Room:
                query_mock.filter.return_value.first.return_value = mock_room
            elif args[0] == models.CardsXGame:
                query_mock.join.return_value.filter.return_value.first.return_value = mock_murderer_secret
            elif args[0] == models.Player:
                # No hay jugadores
                query_mock.filter.return_value.all.return_value = []
            return query_mock
        
        mock_db.query.side_effect = side_effect_query
        
        from app.services.game_service import win_for_total_disgrace
        result = await win_for_total_disgrace(mock_db, 123)
        
        assert result is False
        mock_db.close.assert_called_once()


@pytest.mark.asyncio
async def test_win_for_total_disgrace_sin_complice():
    """Test victoria cuando NO hay cómplice, solo asesino"""
    with patch('app.services.game_service.SessionLocal') as mock_session_local, \
         patch('app.services.game_service.get_players_in_social_disgrace') as mock_get_disgrace, \
         patch('app.services.game_service._get_accomplice', new_callable=AsyncMock) as mock_get_accomplice, \
         patch('app.services.game_service._end_game_with_winners', new_callable=AsyncMock) as mock_end_game:
        
        mock_db = Mock()
        mock_session_local.return_value = mock_db
        
        mock_room = Mock()
        mock_room.id = 100
        
        mock_murderer_secret = Mock()
        mock_murderer_secret.player_id = 1
        
        # No hay cómplice
        mock_get_accomplice.return_value = None
        
        mock_players = [
            Mock(id=1, name="Murderer"),
            Mock(id=3, name="Detective1"),
            Mock(id=4, name="Detective2")
        ]
        
        # Todos los detectives en desgracia
        mock_get_disgrace.return_value = [
            {"player_id": 3, "player_name": "Detective1"},
            {"player_id": 4, "player_name": "Detective2"}
        ]
        
        # Configurar queries
        mock_room_query = Mock()
        mock_room_query.filter.return_value.first.return_value = mock_room
        
        mock_secret_query = Mock()
        mock_secret_join = Mock()
        mock_secret_join.filter.return_value.first.return_value = mock_murderer_secret
        mock_secret_query.join.return_value = mock_secret_join
        
        mock_player_query = Mock()
        mock_player_query.filter.return_value.all.return_value = mock_players
        
        def query_side_effect(model):
            if model.__name__ == 'Room':
                return mock_room_query
            elif model.__name__ == 'CardsXGame':
                return mock_secret_query
            elif model.__name__ == 'Player':
                return mock_player_query
            return Mock()
        
        mock_db.query.side_effect = query_side_effect
        
        from app.services.game_service import win_for_total_disgrace
        result = await win_for_total_disgrace(mock_db, 123)
        
        assert result is True
        mock_end_game.assert_awaited_once()
        
        # Solo el murderer debe estar en winners
        winners = mock_end_game.call_args[1]["winners"]
        assert len(winners) == 1
        assert winners[0]["player_id"] == 1
        
        mock_db.close.assert_called_once()


@pytest.mark.asyncio
async def test_win_for_total_disgrace_exception_handling():
    """Test manejo de excepciones en win_for_total_disgrace"""
    with patch('app.services.game_service.SessionLocal') as mock_session_local:
        mock_db = Mock()
        mock_session_local.return_value = mock_db
        
        # Simular excepción en query
        mock_db.query.side_effect = Exception("Database error")
        
        from app.services.game_service import win_for_total_disgrace
        result = await win_for_total_disgrace(mock_db, 123)
        
        # Debe retornar False y cerrar la sesión
        assert result is False
        mock_db.close.assert_called_once()


@pytest.mark.asyncio
async def test_win_for_total_disgrace_solo_villanos_en_partida():
    """Test caso extremo: solo hay villanos, ningún detective"""
    with patch('app.services.game_service.SessionLocal') as mock_session_local, \
         patch('app.services.game_service.get_players_in_social_disgrace') as mock_get_disgrace, \
         patch('app.services.game_service._get_accomplice', new_callable=AsyncMock) as mock_get_accomplice, \
         patch('app.services.game_service._end_game_with_winners', new_callable=AsyncMock) as mock_end_game:
        
        mock_db = Mock()
        mock_session_local.return_value = mock_db
        
        mock_room = Mock()
        mock_room.id = 100
        
        mock_murderer_secret = Mock()
        mock_murderer_secret.player_id = 1
        
        mock_get_accomplice.return_value = 2
        
        # Solo villanos, sin detectives
        mock_players = [
            Mock(id=1, name="Murderer"),
            Mock(id=2, name="Accomplice")
        ]
        
        mock_get_disgrace.return_value = []
        
        # Configurar queries
        mock_room_query = Mock()
        mock_room_query.filter.return_value.first.return_value = mock_room
        
        mock_secret_query = Mock()
        mock_secret_join = Mock()
        mock_secret_join.filter.return_value.first.return_value = mock_murderer_secret
        mock_secret_query.join.return_value = mock_secret_join
        
        mock_player_query = Mock()
        mock_player_query.filter.return_value.all.return_value = mock_players
        
        def query_side_effect(model):
            if model.__name__ == 'Room':
                return mock_room_query
            elif model.__name__ == 'CardsXGame':
                return mock_secret_query
            elif model.__name__ == 'Player':
                return mock_player_query
            return Mock()
        
        mock_db.query.side_effect = query_side_effect
        
        from app.services.game_service import win_for_total_disgrace
        result = await win_for_total_disgrace(mock_db, 123)
        
        # Técnicamente, si no hay detectives, "todos los buenos están en desgracia" es vacuamente verdadero
        assert result is True
        mock_end_game.assert_awaited_once()
        mock_db.close.assert_called_once()