import pytest
from unittest.mock import AsyncMock, patch
from app.services import game_service


@pytest.mark.asyncio
async def test_procesar_ultima_carta_fin_de_partida():
    """Test básico que verifica el fin de partida cuando se agota el mazo"""
    
    # Mock del WebSocketService
    mock_ws_service = AsyncMock()
    
    with patch("app.services.game_service.get_websocket_service", return_value=mock_ws_service):
        # Reasignar websocket_service
        game_service.websocket_service = mock_ws_service
        
        # Datos de prueba - partida con 1 carta restante
        game_id = 123
        carta = "The murderer escapes"
        game_state = {
            "game": {
                "id": game_id,
                "status": "in_game"
            },
            "players": [
                {"id": 1, "name": "Ana", "role": "murderer"},
                {"id": 2, "name": "Luis", "role": "accomplice"},
                {"id": 3, "name": "Carlos", "role": "detective"}
            ],
            "deck": {"remaining": 1}
        }
        
        # Ejecutar función
        await game_service.procesar_ultima_carta(game_id, carta, game_state)
        
        # Verificar que el mazo quedó en 0
        assert game_state["deck"]["remaining"] == 0
        
        # Verificar que el estado cambió a finished
        assert game_state["game"]["status"] == "finished"
        
        # Verificar que se llamó al WebSocket 2 veces (game_finished y game_state)
        assert mock_ws_service.emit_to_room.call_count == 2
        
        # Verificar primera llamada (game_finished)
        first_call = mock_ws_service.emit_to_room.call_args_list[0]
        assert first_call[0][0] == game_id  # game_id
        assert first_call[0][1] == "game_finished"  # event
        
        # Verificar que hay winners en la primera llamada
        winners = first_call[0][2]["winners"]
        assert len(winners) == 2  # murderer y accomplice
        
        # Verificar estructura y contenido de los winners
        winner_roles = [w["role"] for w in winners]
        winner_ids = [w["player_id"] for w in winners]
        
        assert "murderer" in winner_roles
        assert "accomplice" in winner_roles
        assert 1 in winner_ids  # ID del murderer
        assert 2 in winner_ids  # ID del accomplice


@pytest.mark.asyncio 
async def test_procesar_ultima_carta_continua_partida():
    """Test que verifica que la partida continúa cuando quedan cartas"""
    
    mock_ws_service = AsyncMock()
    
    with patch("app.services.game_service.get_websocket_service", return_value=mock_ws_service):
        game_service.websocket_service = mock_ws_service
        
        # Partida con más de 1 carta
        game_id = 456
        carta = "Some other card"
        game_state = {
            "game": {
                "id": game_id,
                "status": "in_game"
            },
            "players": [
                {"id": 1, "role": "murderer"},
                {"id": 2, "role": "accomplice"}
            ],
            "deck": {"remaining": 5}
        }
        
        # Ejecutar función
        await game_service.procesar_ultima_carta(game_id, carta, game_state)
        
        # Verificar que el mazo se decrementó en 1
        assert game_state["deck"]["remaining"] == 4
        
        # Verificar que el estado NO cambió
        assert game_state["game"]["status"] == "in_game"
        
        # Verificar que NO se llamó al WebSocket
        mock_ws_service.emit_to_room.assert_not_called()


def test_get_asesino():
    """Test para la función get_asesino"""
    
    # Caso con asesino presente
    game_state = {
        "players": [
            {"id": 1, "role": "detective"},
            {"id": 2, "role": "murderer"},
            {"id": 3, "role": "accomplice"}
        ]
    }
    
    asesino_id = game_service.get_asesino(game_state)
    assert asesino_id == 2
    
    # Caso sin asesino
    game_state_sin_asesino = {
        "players": [
            {"id": 1, "role": "detective"},
            {"id": 3, "role": "accomplice"}
        ]
    }
    
    asesino_id = game_service.get_asesino(game_state_sin_asesino)
    assert asesino_id is None


def test_get_complice():
    """Test para la función get_complice"""
    
    # Caso con cómplice presente
    game_state = {
        "players": [
            {"id": 1, "role": "detective"},
            {"id": 2, "role": "murderer"},
            {"id": 3, "role": "accomplice"}
        ]
    }
    
    complice_id = game_service.get_complice(game_state)
    assert complice_id == 3
    
    # Caso sin cómplice
    game_state_sin_complice = {
        "players": [
            {"id": 1, "role": "detective"},
            {"id": 2, "role": "murderer"}
        ]
    }
    
    complice_id = game_service.get_complice(game_state_sin_complice)
    assert complice_id is None


@pytest.mark.asyncio
async def test_procesar_ultima_carta_sin_murderer_escapes():
    """Test cuando la última carta NO es 'The murderer escapes'"""
    
    mock_ws_service = AsyncMock()
    
    with patch("app.services.game_service.get_websocket_service", return_value=mock_ws_service):
        game_service.websocket_service = mock_ws_service
        
        game_id = 789
        carta = "Some other final card"
        game_state = {
            "game": {"id": game_id, "status": "in_game"},
            "players": [
                {"id": 1, "role": "murderer"},
                {"id": 2, "role": "accomplice"}
            ],
            "deck": {"remaining": 1}
        }
        
        await game_service.procesar_ultima_carta(game_id, carta, game_state)
        
        # La partida debe terminar pero sin winners
        assert game_state["game"]["status"] == "finished"
        assert game_state["deck"]["remaining"] == 0
        
        # Verificar que se emitió game_finished con winners vacío
        first_call = mock_ws_service.emit_to_room.call_args_list[0]
        winners = first_call[0][2]["winners"]
        assert len(winners) == 0