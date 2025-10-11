import httpx
import json
import sys
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import date, datetime
from app.routes.join import join_game, JoinGameRequest
from app.services.game_service import join_game_logic
from app.db.models import Room, Player, RoomStatus
from sqlalchemy.orm import Session

@pytest.fixture
def mock_db():
    """Mock database session"""
    return Mock(spec=Session)

@pytest.fixture
def sample_room():
    """Sample room for testing"""
    room = Mock(spec=Room)
    room.id = 1
    room.name = "Test Room"
    room.players_min = 2
    room.players_max = 6
    room.status = RoomStatus.WAITING
    room.id_game = 10
    return room

@pytest.fixture
def sample_players():
    """Sample players for testing"""
    host = Mock(spec=Player)
    host.id = 1
    host.name = "Host"
    host.avatar_src = "/host.png"
    host.birthdate = date(1995, 1, 1)
    host.is_host = True
    host.order = 1
    
    player2 = Mock(spec=Player)
    player2.id = 2
    player2.name = "Player2"
    player2.avatar_src = "/player2.png"
    player2.birthdate = date(1996, 2, 2)
    player2.is_host = False
    player2.order = 2
    
    return [host, player2]

class TestJoinGameLogic:
    """Tests for join_game_logic function"""
    
    @patch('app.services.game_service.crud')
    def test_join_game_success(self, mock_crud, mock_db, sample_room, sample_players):
        """Test successful join"""
        # Setup mocks
        mock_crud.get_room_by_id.return_value = sample_room
        mock_crud.list_players_by_room.side_effect = [
            [sample_players[0]],  # First call: only host
            sample_players         # Second call: host + new player
        ]
        mock_crud.create_player.return_value = sample_players[1]
        
        player_data = {
            "name": "Player2",
            "avatar": "/player2.png",
            "birthdate": "1996-02-02"
        }
        
        result = join_game_logic(mock_db, 1, player_data)
        
        assert result["success"] is True
        assert result["room"] == sample_room
        assert len(result["players"]) == 2
        assert result["error"] is None
        
        # Verify crud calls
        mock_crud.get_room_by_id.assert_called_once_with(mock_db, 1)
        mock_crud.create_player.assert_called_once()
    
    @patch('app.services.game_service.crud')
    def test_join_game_room_not_found(self, mock_crud, mock_db):
        """Test join when room doesn't exist"""
        mock_crud.get_room_by_id.return_value = None
        
        result = join_game_logic(mock_db, 999, {})
        
        assert result["success"] is False
        assert result["error"] == "room_not_found"
    
    @patch('app.services.game_service.crud')
    def test_join_game_room_not_waiting(self, mock_crud, mock_db, sample_room):
        """Test join when room is not in WAITING status"""
        sample_room.status = RoomStatus.INGAME
        mock_crud.get_room_by_id.return_value = sample_room
        
        result = join_game_logic(mock_db, 1, {})
        
        assert result["success"] is False
        assert result["error"] == "room_not_waiting"
    
    @patch('app.services.game_service.crud')
    def test_join_game_room_full(self, mock_crud, mock_db, sample_room):
        """Test join when room is full"""
        # Create 6 players (max capacity)
        full_players = []
        for i in range(6):
            p = Mock(spec=Player)
            p.id = i + 1
            p.name = f"Player{i+1}"
            full_players.append(p)
        
        mock_crud.get_room_by_id.return_value = sample_room
        mock_crud.list_players_by_room.return_value = full_players
        
        player_data = {
            "name": "Player7",
            "avatar": "/player7.png",
            "birthdate": "1997-01-01"
        }
        
        result = join_game_logic(mock_db, 1, player_data)
        
        assert result["success"] is False
        assert result["error"] == "room_full"
    
    @patch('app.services.game_service.crud')
    def test_join_game_invalid_birthdate(self, mock_crud, mock_db, sample_room, sample_players):
        """Test join with invalid birthdate format"""
        mock_crud.get_room_by_id.return_value = sample_room
        mock_crud.list_players_by_room.return_value = [sample_players[0]]
        
        player_data = {
            "name": "Player2",
            "avatar": "/player2.png",
            "birthdate": "invalid-date"
        }
        
        result = join_game_logic(mock_db, 1, player_data)
        
        assert result["success"] is False
        assert result["error"] == "invalid_birthdate_format"
    
    @patch('app.services.game_service.crud')
    def test_join_game_exception_handling(self, mock_crud, mock_db):
        """Test exception handling"""
        mock_crud.get_room_by_id.side_effect = Exception("Database error")
        
        result = join_game_logic(mock_db, 1, {})
        
        assert result["success"] is False
        assert result["error"] == "internal_error"


class TestJoinGameEndpoint:
    """Tests for the join_game FastAPI endpoint"""
    
    @pytest.mark.asyncio
    @patch('app.routes.join.join_game_logic')
    async def test_endpoint_success(self, mock_logic, mock_db, sample_room, sample_players):
        """Test successful endpoint call"""
        mock_logic.return_value = {
            "success": True,
            "room": sample_room,
            "players": sample_players,
            "error": None
        }
        
        request = JoinGameRequest(
            name="TestPlayer",
            avatar="/test.png",
            birthdate="1995-01-01"
        )
        
        response = await join_game(1, request, mock_db)
        
        assert response.room.id == 1
        assert response.room.name == "Test Room"
        assert response.room.players_min == 2
        assert response.room.players_max == 6
        assert len(response.players) == 2
        assert response.players[0].name == "Host"
        assert response.players[0].is_host is True
    
    @pytest.mark.asyncio
    @patch('app.routes.join.join_game_logic')
    async def test_endpoint_room_not_found(self, mock_logic, mock_db):
        """Test endpoint when room not found"""
        from fastapi import HTTPException
        
        mock_logic.return_value = {
            "success": False,
            "error": "room_not_found"
        }
        
        request = JoinGameRequest(
            name="TestPlayer",
            avatar="/test.png",
            birthdate="1995-01-01"
        )
        
        with pytest.raises(HTTPException) as exc_info:
            await join_game(999, request, mock_db)
        
        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Room not found"
    
    @pytest.mark.asyncio
    @patch('app.routes.join.join_game_logic')
    async def test_endpoint_room_full(self, mock_logic, mock_db):
        """Test endpoint when room is full"""
        from fastapi import HTTPException
        
        mock_logic.return_value = {
            "success": False,
            "error": "room_full"
        }
        
        request = JoinGameRequest(
            name="TestPlayer",
            avatar="/test.png",
            birthdate="1995-01-01"
        )
        
        with pytest.raises(HTTPException) as exc_info:
            await join_game(1, request, mock_db)
        
        assert exc_info.value.status_code == 400
        assert exc_info.value.detail == "Room is full"
    
    @pytest.mark.asyncio
    @patch('app.routes.join.join_game_logic')
    async def test_endpoint_room_not_waiting(self, mock_logic, mock_db):
        """Test endpoint when room not accepting players"""
        from fastapi import HTTPException
        
        mock_logic.return_value = {
            "success": False,
            "error": "room_not_waiting"
        }
        
        request = JoinGameRequest(
            name="TestPlayer",
            avatar="/test.png",
            birthdate="1995-01-01"
        )
        
        with pytest.raises(HTTPException) as exc_info:
            await join_game(1, request, mock_db)
        
        assert exc_info.value.status_code == 400
        assert exc_info.value.detail == "Room is not accepting players"
    
    @pytest.mark.asyncio
    @patch('app.routes.join.join_game_logic')
    async def test_endpoint_generic_error(self, mock_logic, mock_db):
        """Test endpoint with generic error"""
        from fastapi import HTTPException
        
        mock_logic.return_value = {
            "success": False,
            "error": "some_other_error"
        }
        
        request = JoinGameRequest(
            name="TestPlayer",
            avatar="/test.png",
            birthdate="1995-01-01"
        )
        
        with pytest.raises(HTTPException) as exc_info:
            await join_game(1, request, mock_db)
        
        assert exc_info.value.status_code == 400
        assert exc_info.value.detail == "some_other_error"
    
    @pytest.mark.asyncio
    @patch('app.routes.join.join_game_logic')
    async def test_endpoint_exception_handling(self, mock_logic, mock_db):
        """Test endpoint exception handling"""
        from fastapi import HTTPException
        
        mock_logic.side_effect = Exception("Unexpected error")
        
        request = JoinGameRequest(
            name="TestPlayer",
            avatar="/test.png",
            birthdate="1995-01-01"
        )
        
        with pytest.raises(HTTPException) as exc_info:
            await join_game(1, request, mock_db)
        
        assert exc_info.value.status_code == 500
        assert exc_info.value.detail == "server_error"