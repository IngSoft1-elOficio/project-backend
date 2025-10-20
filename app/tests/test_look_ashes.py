import pytest
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from fastapi.testclient import TestClient
from app.db import models
from app.main import app

client = TestClient(app)

def test_play_room_not_found():
    """Test que retorna 404 cuando la sala no existe"""
    with patch('app.routes.look_ashes.crud.get_room_by_id', return_value=None):
        payload = {"card_id": 1}
        resp = client.post(f"/api/game/99999/look-into-ashes/play", json=payload, headers={"http-user-id": "1"})
        assert resp.status_code == 404
        assert resp.json()['detail'] == 'Room not found'


def test_play_room_has_no_active_game():
    """Test que retorna 400 cuando la sala no tiene juego activo"""
    mock_room = Mock()
    mock_room.id_game = None
    
    with patch('app.routes.look_ashes.crud.get_room_by_id', return_value=mock_room):
        payload = {"card_id": 1}
        resp = client.post(f"/api/game/1/look-into-ashes/play", json=payload, headers={"http-user-id": "1"})
        assert resp.status_code == 400
        assert resp.json()['detail'] == 'Room has no active game'


def test_play_game_not_found():
    """Test que retorna 404 cuando el juego no existe"""
    mock_room = Mock()
    mock_room.id_game = 10
    
    with patch('app.routes.look_ashes.crud.get_room_by_id', return_value=mock_room), \
         patch('app.routes.look_ashes.crud.get_game_by_id', return_value=None):
        payload = {"card_id": 1}
        resp = client.post(f"/api/game/1/look-into-ashes/play", json=payload, headers={"http-user-id": "1"})
        assert resp.status_code == 404
        assert resp.json()['detail'] == 'Game not found'


def test_play_not_your_turn():
    """Test que retorna 403 cuando no es el turno del jugador"""
    mock_room = Mock()
    mock_room.id_game = 10
    
    mock_game = Mock()
    mock_game.player_turn_id = 2  # Different player
    
    with patch('app.routes.look_ashes.crud.get_room_by_id', return_value=mock_room), \
         patch('app.routes.look_ashes.crud.get_game_by_id', return_value=mock_game):
        payload = {"card_id": 1}
        resp = client.post(f"/api/game/1/look-into-ashes/play", json=payload, headers={"http-user-id": "1"})
        assert resp.status_code == 403
        assert resp.json()['detail'] == 'Not your turn'


def test_play_event_card_not_in_hand():
    """Test que retorna 404 cuando la carta de evento no está en la mano"""
    mock_room = Mock()
    mock_room.id = 1
    mock_room.id_game = 10
    
    mock_game = Mock()
    mock_game.id = 10
    mock_game.player_turn_id = 1
    
    # Mock query to return None (card not found)
    mock_query = MagicMock()
    mock_query.first.return_value = None
    
    with patch('app.routes.look_ashes.crud.get_room_by_id', return_value=mock_room), \
         patch('app.routes.look_ashes.crud.get_game_by_id', return_value=mock_game), \
         patch('app.routes.look_ashes.SessionLocal') as mock_db_class:
        
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value = mock_query
        mock_db_class.return_value = mock_db
        
        payload = {"card_id": 999}
        resp = client.post(f"/api/game/1/look-into-ashes/play", json=payload, headers={"http-user-id": "1"})
        assert resp.status_code == 404
        assert resp.json()['detail'] == 'Event card not found in your hand'


def test_play_card_not_event_type():
    """Test que retorna 400 cuando la carta no es de tipo evento"""
    mock_room = Mock()
    mock_room.id = 1
    mock_room.id_game = 10
    
    mock_game = Mock()
    mock_game.id = 10
    mock_game.player_turn_id = 1
    
    # Mock card entry que no es de tipo EVENT
    mock_card_obj = Mock()
    mock_card_obj.type = models.CardType.INSTANT
    
    mock_card_entry = Mock()
    mock_card_entry.card = mock_card_obj
    
    mock_query = MagicMock()
    mock_query.first.return_value = mock_card_entry
    
    with patch('app.routes.look_ashes.crud.get_room_by_id', return_value=mock_room), \
         patch('app.routes.look_ashes.crud.get_game_by_id', return_value=mock_game), \
         patch('app.routes.look_ashes.SessionLocal') as mock_db_class:
        
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value = mock_query
        mock_db_class.return_value = mock_db
        
        payload = {"card_id": 100}
        resp = client.post(f"/api/game/1/look-into-ashes/play", json=payload, headers={"http-user-id": "1"})
        assert resp.status_code == 400
        assert resp.json()['detail'] == 'Card is not an event card'


def test_play_no_current_turn():
    """Test que retorna 400 cuando no hay turno activo"""
    mock_room = Mock()
    mock_room.id = 1
    mock_room.id_game = 10
    
    mock_game = Mock()
    mock_game.id = 10
    mock_game.player_turn_id = 1
    
    # Mock event card entry
    mock_card_obj = Mock()
    mock_card_obj.type = models.CardType.EVENT
    
    mock_card_entry = Mock()
    mock_card_entry.card = mock_card_obj
    
    # Mock discard cards (not empty)
    mock_discard_card = Mock()
    
    mock_query1 = MagicMock()
    mock_query1.first.return_value = mock_card_entry
    
    mock_query2 = MagicMock()
    mock_query2.limit.return_value.all.return_value = [mock_discard_card]
    
    with patch('app.routes.look_ashes.crud.get_room_by_id', return_value=mock_room), \
         patch('app.routes.look_ashes.crud.get_game_by_id', return_value=mock_game), \
         patch('app.routes.look_ashes.crud.get_current_turn', return_value=None), \
         patch('app.routes.look_ashes.SessionLocal') as mock_db_class:
        
        mock_db = MagicMock()
        mock_db.query.side_effect = [MagicMock(filter=MagicMock(return_value=mock_query1)), 
                                       MagicMock(join=MagicMock(return_value=MagicMock(filter=MagicMock(return_value=mock_query2))))]
        mock_db_class.return_value = mock_db
        
        payload = {"card_id": 100}
        resp = client.post(f"/api/game/1/look-into-ashes/play", json=payload, headers={"http-user-id": "1"})
        assert resp.status_code == 400
        assert resp.json()['detail'] == 'No active turn found'


def test_select_room_not_found():
    """Test que retorna 404 cuando la sala no existe en select"""
    with patch('app.routes.look_ashes.crud.get_room_by_id', return_value=None):
        payload = {"action_id": 1, "selected_card_id": 1}
        resp = client.post(f"/api/game/999999/look-into-ashes/select", json=payload, headers={"http-user-id": "1"})
        assert resp.status_code == 404


def test_select_game_not_found():
    """Test que retorna 404 cuando el juego no existe en select"""
    mock_room = Mock()
    mock_room.id_game = 10
    
    with patch('app.routes.look_ashes.crud.get_room_by_id', return_value=mock_room), \
         patch('app.routes.look_ashes.crud.get_game_by_id', return_value=None):
        payload = {"action_id": 1, "selected_card_id": 1}
        resp = client.post(f"/api/game/1/look-into-ashes/select", json=payload, headers={"http-user-id": "1"})
        assert resp.status_code == 404


def test_select_parent_action_not_found():
    """Test que retorna 404 cuando la acción padre no existe"""
    mock_room = Mock()
    mock_room.id_game = 10
    
    mock_game = Mock()
    
    with patch('app.routes.look_ashes.crud.get_room_by_id', return_value=mock_room), \
         patch('app.routes.look_ashes.crud.get_game_by_id', return_value=mock_game), \
         patch('app.routes.look_ashes.crud.get_action_by_id', return_value=None):
        payload = {"action_id": 999, "selected_card_id": 1}
        resp = client.post(f"/api/game/1/look-into-ashes/select", json=payload, headers={"http-user-id": "1"})
        assert resp.status_code == 404


def test_select_parent_action_invalid():
    """Test que retorna 400 cuando la acción padre es inválida"""
    mock_room = Mock()
    mock_room.id_game = 10
    
    mock_game = Mock()
    
    mock_action = Mock()
    mock_action.id_game = 11  # Different game
    mock_action.player_id = 1
    mock_action.action_name = models.ActionName.LOOK_INTO_THE_ASHES.value
    mock_action.result = models.ActionResult.SUCCESS
    
    with patch('app.routes.look_ashes.crud.get_room_by_id', return_value=mock_room), \
         patch('app.routes.look_ashes.crud.get_game_by_id', return_value=mock_game), \
         patch('app.routes.look_ashes.crud.get_action_by_id', return_value=mock_action):
        payload = {"action_id": 1, "selected_card_id": 1}
        resp = client.post(f"/api/game/1/look-into-ashes/select", json=payload, headers={"http-user-id": "1"})
        assert resp.status_code == 400


def test_select_action_expired():
    """Test que retorna 400 cuando la acción está expirada"""
    from datetime import datetime, timedelta
    
    mock_room = Mock()
    mock_room.id_game = 10
    
    mock_game = Mock()
    
    mock_action = Mock()
    mock_action.id_game = 10
    mock_action.player_id = 1
    mock_action.action_name = models.ActionName.LOOK_INTO_THE_ASHES.value
    mock_action.result = models.ActionResult.SUCCESS
    mock_action.action_time = datetime.now() - timedelta(minutes=11)  # Expired
    
    with patch('app.routes.look_ashes.crud.get_room_by_id', return_value=mock_room), \
         patch('app.routes.look_ashes.crud.get_game_by_id', return_value=mock_game), \
         patch('app.routes.look_ashes.crud.get_action_by_id', return_value=mock_action):
        payload = {"action_id": 1, "selected_card_id": 1}
        resp = client.post(f"/api/game/1/look-into-ashes/select", json=payload, headers={"http-user-id": "1"})
        assert resp.status_code == 400
        assert resp.json()['detail'] == 'Action expired'


def test_select_card_not_found():
    """Test que retorna 400 cuando la carta seleccionada no está en discard"""
    from datetime import datetime
    
    mock_room = Mock()
    mock_room.id_game = 10
    
    mock_game = Mock()
    
    mock_action = Mock()
    mock_action.id_game = 10
    mock_action.player_id = 1
    mock_action.action_name = models.ActionName.LOOK_INTO_THE_ASHES.value
    mock_action.result = models.ActionResult.SUCCESS
    mock_action.action_time = datetime.now()  # Valid
    
    # Mock query for card (returns None)
    mock_query = MagicMock()
    mock_query.first.return_value = None
    
    with patch('app.routes.look_ashes.crud.get_room_by_id', return_value=mock_room), \
         patch('app.routes.look_ashes.crud.get_game_by_id', return_value=mock_game), \
         patch('app.routes.look_ashes.crud.get_action_by_id', return_value=mock_action), \
         patch('app.routes.look_ashes.SessionLocal') as mock_db_class:
        
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value = mock_query
        mock_db_class.return_value = mock_db
        
        payload = {"action_id": 1, "selected_card_id": 999}
        resp = client.post(f"/api/game/1/look-into-ashes/select", json=payload, headers={"http-user-id": "1"})
        assert resp.status_code == 400
        assert 'not found' in resp.json()['detail'].lower() or 'no longer' in resp.json()['detail'].lower()
