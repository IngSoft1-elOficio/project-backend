"""
Tests for the play_detective_set route endpoint.
Tests the HTTP API layer including validation and error handling.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from datetime import date

from app.main import app
from app.db.database import Base
from app.db.models import Room, Game, Player, Card, CardsXGame, Turn
from app.db.models import RoomStatus, CardState, TurnStatus, CardType
from app.routes.play_detective_set import get_db


# Create shared in-memory SQLite database for testing
# StaticPool ensures the same connection is reused across sessions so tables persist
SQLALCHEMY_DATABASE_URL = "sqlite://"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture
def client():
    """Create a test client for the FastAPI app"""
    Base.metadata.create_all(bind=engine)
    
    def override_get_db():
        try:
            db = TestingSessionLocal()
            yield db
        finally:
            db.close()
    
    app.dependency_overrides[get_db] = override_get_db
    
    yield TestClient(app)
    
    Base.metadata.drop_all(bind=engine)
    app.dependency_overrides.clear()


@pytest.fixture
def setup_game_data(client):
    """Setup a complete game with players and cards for testing"""
    db = TestingSessionLocal()
    
    try:
        # Create game
        game = Game(id=1, player_turn_id=None)
        db.add(game)
        db.flush()
        
        # Create room
        room = Room(
            id=1,
            name="Test Room",
            status=RoomStatus.INGAME,
            id_game=game.id,
            players_min=2,
            players_max=6
        )
        db.add(room)
        db.flush()
        
        # Create players
        player1 = Player(
            id=1,
            name="Player1",
            id_room=room.id,
            order=1,
            is_host=True,
            avatar_src="avatar1.png",
            birthdate=date(2000, 1, 1),
        )
        player2 = Player(
            id=2,
            name="Player2",
            id_room=room.id,
            order=2,
            is_host=False,
            avatar_src="avatar2.png",
            birthdate=date(2000, 1, 2),
        )
        db.add_all([player1, player2])
        db.flush()
        
        # Update game with player turn
        game.player_turn_id = player1.id
        
        # Create turn
        turn = Turn(id=1, number=1, id_game=game.id, player_id=player1.id, status=TurnStatus.IN_PROGRESS)
        db.add(turn)
        db.flush()
        
        # Create cards
        marple = Card(id=6, name="Miss Marple", description="Detective", 
                     type=CardType.DETECTIVE, img_src="marple.png", qty=3)
        wildcard = Card(id=4, name="Harley Quin Wildcard", description="Wildcard",
                       type=CardType.DETECTIVE, img_src="wildcard.png", qty=1)
        db.add_all([marple, wildcard])
        db.flush()
        
        # Assign cards to player1's hand
        card1 = CardsXGame(id=10, id_game=game.id, id_card=6, is_in=CardState.HAND, 
                          position=1, player_id=player1.id, hidden=True)
        card2 = CardsXGame(id=11, id_game=game.id, id_card=6, is_in=CardState.HAND,
                          position=2, player_id=player1.id, hidden=True)
        card3 = CardsXGame(id=12, id_game=game.id, id_card=4, is_in=CardState.HAND,
                          position=3, player_id=player1.id, hidden=True)
        db.add_all([card1, card2, card3])
        
        db.commit()
        
        return {
            "game_id": game.id,
            "room_id": room.id,
            "player1_id": player1.id,
            "player2_id": player2.id,
            "card_ids": [10, 11, 12]
        }
        
    finally:
        db.close()


class TestPlayDetectiveSetRoute:
    """Test suite for POST /api/game/{room_id}/play-detective-set endpoint"""
    
    def test_successful_play_detective_set(self, client, setup_game_data):
        """Test successful detective set play"""
        data = setup_game_data
        
        response = client.post(
            f"/api/game/{data['room_id']}/play-detective-set",
            json={
                "owner": data['player1_id'],
                "setType": "marple",
                "cards": data['card_ids'],
                "hasWildcard": True
            }
        )
        
        assert response.status_code == 200
        json_data = response.json()
        assert json_data["success"] is True
        assert "actionId" in json_data
        assert "nextAction" in json_data
        assert json_data["nextAction"]["type"] in ["selectPlayerAndSecret", "selectPlayer"]
    
    def test_invalid_request_body(self, client):
        """Test validation error with invalid request body"""
        response = client.post(
            "/api/game/1/play-detective-set",
            json={
                "owner": "not_a_number",  # Should be int
                "setType": "invalid_type",  # Should be valid SetType
                "cards": "not_a_list",  # Should be list
                "hasWildcard": "not_a_bool"  # Should be bool
            }
        )
        
        assert response.status_code == 422  # Pydantic validation error
    
    def test_missing_required_fields(self, client):
        """Test validation error with missing required fields"""
        response = client.post(
            "/api/game/1/play-detective-set",
            json={
                "owner": 1,
                # Missing setType, cards, hasWildcard
            }
        )
        
        assert response.status_code == 422
    
    def test_invalid_set_type(self, client):
        """Test validation error with invalid set type"""
        response = client.post(
            "/api/game/1/play-detective-set",
            json={
                "owner": 1,
                "setType": "invalid_detective",
                "cards": [1, 2, 3],
                "hasWildcard": False
            }
        )
        
        assert response.status_code == 422
    
    def test_empty_cards_list(self, client):
        """Test validation error with empty cards list"""
        response = client.post(
            "/api/game/1/play-detective-set",
            json={
                "owner": 1,
                "setType": "marple",
                "cards": [],
                "hasWildcard": False
            }
        )
        
        assert response.status_code == 422
    
    def test_duplicate_cards(self, client):
        """Test validation error with duplicate card IDs"""
        response = client.post(
            "/api/game/1/play-detective-set",
            json={
                "owner": 1,
                "setType": "marple",
                "cards": [1, 1, 2],  # Duplicate card ID
                "hasWildcard": False
            }
        )
        
        assert response.status_code == 422
    
    def test_valid_set_types_accepted(self, client):
        """Test that all valid set types are accepted by schema validation"""
        valid_set_types = ["poirot", "marple", "satterthwaite", "pyne", "eileenbrent", "beresford"]
        
        for set_type in valid_set_types:
            response = client.post(
                "/api/game/999/play-detective-set",  # Non-existent room
                json={
                    "owner": 1,
                    "setType": set_type,
                    "cards": [1, 2, 3],
                    "hasWildcard": False
                }
            )
            
            # Should fail with 404 (room not found), not 422 (validation error)
            assert response.status_code == 404, f"Set type {set_type} should be valid"
    
    def test_negative_owner_id(self, client):
        """Test validation with negative owner ID"""
        response = client.post(
            "/api/game/1/play-detective-set",
            json={
                "owner": -1,
                "setType": "marple",
                "cards": [1, 2, 3],
                "hasWildcard": False
            }
        )
        
        # Schema validation should accept negative numbers (business logic validates)
        # So it should fail with 404/400, not 422
        assert response.status_code in [400, 404, 409]
    
    def test_room_not_found_error(self, client):
        """Test error when room doesn't exist"""
        response = client.post(
            "/api/game/999/play-detective-set",
            json={
                "owner": 1,
                "setType": "marple",
                "cards": [1, 2, 3],
                "hasWildcard": False
            }
        )
        
        assert response.status_code == 404
        assert "Room not found" in response.json()["detail"]
    
    def test_game_not_started_error(self, client):
        """Test error when game hasn't started"""
        db = TestingSessionLocal()
        
        # Create room without game
        room = Room(
            id=2,
            name="Waiting Room",
            status=RoomStatus.WAITING,
            id_game=None,
            players_min=2,
            players_max=6
        )
        db.add(room)
        db.commit()
        db.close()
        
        response = client.post(
            "/api/game/2/play-detective-set",
            json={
                "owner": 1,
                "setType": "marple",
                "cards": [1, 2, 3],
                "hasWildcard": False
            }
        )
        
        assert response.status_code == 409
        assert "Game not started" in response.json()["detail"]
    
    def test_response_structure_on_validation_error(self, client):
        """Test that validation errors return proper structure"""
        response = client.post(
            "/api/game/1/play-detective-set",
            json={
                "owner": "invalid",
                "setType": "marple",
                "cards": [1, 2],
                "hasWildcard": False
            }
        )
        
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
        assert isinstance(data["detail"], list)  # FastAPI validation errors

    def test_get_db_generator_yields_session(self, monkeypatch):
        """Cover get_db() dependency generator lines by patching SessionLocal"""
        # Patch SessionLocal used in route to reuse our testing engine
        from app.routes import play_detective_set as route_mod
        original_sessionlocal = route_mod.SessionLocal
        route_mod.SessionLocal = TestingSessionLocal
        try:
            gen = route_mod.get_db()
            db = next(gen)
            # Sanity: db can execute a simple statement
            assert db.bind is engine
            # Close generator (triggers finally: db.close())
            gen.close()
        finally:
            # Restore original to avoid side-effects in other tests
            route_mod.SessionLocal = original_sessionlocal

    def test_build_game_state_exception_is_handled(self, client, setup_game_data, monkeypatch):
        """Force build_complete_game_state to raise and ensure route still returns 200"""
        from app.routes import play_detective_set as route_mod

        def boom(*args, **kwargs):
            raise RuntimeError("boom")

        monkeypatch.setattr(route_mod, "build_complete_game_state", boom)

        data = setup_game_data
        resp = client.post(
            f"/api/game/{data['room_id']}/play-detective-set",
            json={
                "owner": data['player1_id'],
                "setType": "marple",
                "cards": data['card_ids'],
                "hasWildcard": True,
            },
        )
        assert resp.status_code == 200

    def test_websocket_emission_success(self, client, setup_game_data, monkeypatch):
        """Mock WS service to succeed and cover the success branch (info logs)"""
        from app.routes import play_detective_set as route_mod

        class DummyWS:
            async def notificar_detective_action_started(self, **kwargs):
                return None

            async def notificar_estado_partida(self, **kwargs):
                return None

        monkeypatch.setattr(route_mod, "get_websocket_service", lambda: DummyWS())

        data = setup_game_data
        resp = client.post(
            f"/api/game/{data['room_id']}/play-detective-set",
            json={
                "owner": data['player1_id'],
                "setType": "marple",
                "cards": data['card_ids'],
                "hasWildcard": True,
            },
        )
        assert resp.status_code == 200

    def test_websocket_emission_failure_does_not_break(self, client, setup_game_data, monkeypatch):
        """If WS emission raises, route should log and still return 200"""
        from app.routes import play_detective_set as route_mod

        class FailingWS:
            async def notificar_detective_action_started(self, **kwargs):
                raise RuntimeError("ws down")

            async def notificar_estado_partida(self, **kwargs):
                # Not reached, but keep it defined
                return None

        monkeypatch.setattr(route_mod, "get_websocket_service", lambda: FailingWS())

        data = setup_game_data
        resp = client.post(
            f"/api/game/{data['room_id']}/play-detective-set",
            json={
                "owner": data['player1_id'],
                "setType": "marple",
                "cards": data['card_ids'],
                "hasWildcard": True,
            },
        )
        assert resp.status_code == 200

    def test_service_raises_non_http_exception(self, client, setup_game_data, monkeypatch):
        """Test when service raises a non-HTTPException error (lines 63-69)"""
        from app.routes import play_detective_set as route_mod

        def boom(*args, **kwargs):
            raise ValueError("Service logic error")

        monkeypatch.setattr(route_mod.DetectiveSetService, "play_detective_set", boom)

        data = setup_game_data
        resp = client.post(
            f"/api/game/{data['room_id']}/play-detective-set",
            json={
                "owner": data['player1_id'],
                "setType": "marple",
                "cards": data['card_ids'],
                "hasWildcard": True,
            },
        )
        
        # Should return 500 when service raises non-HTTPException
        assert resp.status_code == 500
        assert "Internal server error" in resp.json()["detail"]
