"""
Tests para el endpoint POST /api/game/{room_id}/instant/not-so-fast/cancel

Casos testeados:
- CREATE_SET normal
- CREATE_SET con Eileen Brent
- EVENT
- ADD_TO_SET con Eileen Brent
- Validación: Room not found
- Validación: Action not cancelled
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from datetime import datetime, date

from app.main import app
from app.db import models
from app.db.models import CardState, ActionType, ActionName, ActionResult
from app.db.database import Base
from app.routes.not_so_fast import get_db


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


def _load_cards(db: Session):
    """Carga las cartas necesarias para los tests"""
    cards = [
        # ID 4 - Harley Quinn
        models.Card(id=4, name="Harley Quin Wildcard", description="Wildcard", type="DETECTIVE", img_src="/cards/detective_quin.png", qty=4),
        # ID 5 - Ariadne Oliver
        models.Card(id=5, name="Adriane Oliver", description="Add to any existing set", type="DETECTIVE", img_src="/cards/detective_oliver.png", qty=3),
        # ID 6 - Miss Marple  
        models.Card(id=6, name="Miss Marple", description="Choose a player", type="DETECTIVE", img_src="/cards/detective_marple.png", qty=3),
        # ID 7 - Parker Pyne
        models.Card(id=7, name="Parker Pyne", description="Flip face-up card down", type="DETECTIVE", img_src="/cards/detective_pyne.png", qty=3),
        # ID 8 - Tommy Beresford
        models.Card(id=8, name="Tommy Beresford", description="Choose a player", type="DETECTIVE", img_src="/cards/detective_tommyberesford.png", qty=2),
        # ID 9 - Eileen Brent
        models.Card(id=9, name='Lady Eileen "Bundle" Brent', description="Return to hand if cancelled", type="DETECTIVE", img_src="/cards/detective_brent.png", qty=3),
        # ID 10 - Tuppence Beresford
        models.Card(id=10, name="Tuppence Beresford", description="Choose a player", type="DETECTIVE", img_src="/cards/detective_tuppenceberesford.png", qty=2),
        # ID 11 - Hercule Poirot
        models.Card(id=11, name="Hercule Poirot", description="Choose a player", type="DETECTIVE", img_src="/cards/detective_poirot.png", qty=3),
        # ID 13 - Not So Fast
        models.Card(id=13, name="Not so fast", description="Cancel an action", type="INSTANT", img_src="/cards/instant_notsofast.png", qty=10),
        # ID 17 - Point your suspicions (un evento cualquiera)
        models.Card(id=17, name="Point your suspicions", description="All players point", type="EVENT", img_src="/cards/event_pointsuspicions.png", qty=3),
        # Cartas genericas para discard/deck
        models.Card(id=1, name="Generic Card 1", description="Test card", type="SECRET", img_src="/cards/generic1.png", qty=1),
        models.Card(id=2, name="Generic Card 2", description="Test card", type="SECRET", img_src="/cards/generic2.png", qty=1),
    ]
    db.add_all(cards)
    db.commit()


@pytest.fixture
def setup_game_data(client: TestClient):
    """
    Fixture completa para testear el endpoint /cancel
    """
    db = TestingSessionLocal()
    
    # Cargar cartas primero
    _load_cards(db)
    
    # Crear juego
    game = models.Game(player_turn_id=None)
    db.add(game)
    db.flush()
    
    # Crear room
    room = models.Room(
        name="NSF Route Test",
        players_min=2,
        players_max=6,
        status=models.RoomStatus.INGAME,
        id_game=game.id
    )
    db.add(room)
    db.flush()
    
    # Crear jugadores
    player1 = models.Player(
        name="RoutePlayer1",
        avatar_src="/avatars/rp1.jpg",
        birthdate=date(1990, 1, 1),
        id_room=room.id,
        is_host=True,
        order=1
    )
    player2 = models.Player(
        name="RoutePlayer2",
        avatar_src="/avatars/rp2.jpg",
        birthdate=date(1990, 2, 2),
        id_room=room.id,
        is_host=False,
        order=2
    )
    db.add_all([player1, player2])
    db.flush()
    
    game.player_turn_id = player1.id
    db.flush()
    
    # Crear turn
    turn = models.Turn(
        number=1,
        id_game=game.id,
        player_id=player1.id,
        status=models.TurnStatus.IN_PROGRESS,
        start_time=datetime.now()
    )
    db.add(turn)
    db.flush()
    
    # Cartas para diferentes tests
    card_pyne1 = models.CardsXGame(id_game=game.id, id_card=7, is_in=CardState.HAND, position=1, player_id=player1.id, hidden=True)
    card_pyne2 = models.CardsXGame(id_game=game.id, id_card=7, is_in=CardState.HAND, position=2, player_id=player1.id, hidden=True)
    card_eileen1 = models.CardsXGame(id_game=game.id, id_card=9, is_in=CardState.HAND, position=3, player_id=player1.id, hidden=True)
    card_event = models.CardsXGame(id_game=game.id, id_card=17, is_in=CardState.HAND, position=4, player_id=player1.id, hidden=True)
    card_oliver = models.CardsXGame(id_game=game.id, id_card=5, is_in=CardState.HAND, position=5, player_id=player1.id, hidden=True)
    card_marple = models.CardsXGame(id_game=game.id, id_card=6, is_in=CardState.HAND, position=6, player_id=player1.id, hidden=True)
    
    # Set de Poirot de player2
    card_poirot1 = models.CardsXGame(id_game=game.id, id_card=11, is_in=CardState.DETECTIVE_SET, position=1, player_id=player2.id, hidden=False)
    card_poirot2 = models.CardsXGame(id_game=game.id, id_card=11, is_in=CardState.DETECTIVE_SET, position=2, player_id=player2.id, hidden=False)
    
    # Discard inicial
    discard1 = models.CardsXGame(id_game=game.id, id_card=1, is_in=CardState.DISCARD, position=1, player_id=None, hidden=False)
    discard2 = models.CardsXGame(id_game=game.id, id_card=2, is_in=CardState.DISCARD, position=2, player_id=None, hidden=False)
    
    db.add_all([card_pyne1, card_pyne2, card_eileen1, card_event, card_oliver, card_marple,
                card_poirot1, card_poirot2, discard1, discard2])
    db.commit()
    
    # Devolver IDs en lugar de objetos para evitar DetachedInstanceError
    result = {
        "game_id": game.id,
        "room_id": room.id,
        "player1_id": player1.id,
        "player2_id": player2.id,
        "card_pyne1_id": card_pyne1.id,
        "card_pyne2_id": card_pyne2.id,
        "card_eileen1_id": card_eileen1.id,
        "card_event_id": card_event.id,
        "card_oliver_id": card_oliver.id,
        "card_marple_id": card_marple.id,
    }
    
    db.close()
    return result


def create_cancelled_action(db: Session, game_id: int, player_id: int):
    """Helper para crear una acción CANCELLED"""
    action_xxx = models.ActionsPerTurn(
        id_game=game_id,
        player_id=player_id,
        action_type=ActionType.INIT,
        action_name=ActionName.DRAFT_PHASE,
        result=ActionResult.CANCELLED,
        action_time=datetime.now(),
        action_time_end=None,
        parent_action_id=None,
        triggered_by_action_id=None
    )
    db.add(action_xxx)
    db.flush()
    
    action_yyy = models.ActionsPerTurn(
        id_game=game_id,
        player_id=player_id,  # Mismo jugador que la acción original
        action_type=ActionType.INSTANT,
        action_name=ActionName.INSTANT_START,  # Debe ser INSTANT_START
        result=ActionResult.PENDING,
        action_time=datetime.now(),
        action_time_end=None,
        parent_action_id=None,
        triggered_by_action_id=action_xxx.id
    )
    db.add(action_yyy)
    db.flush()
    
    action_zzz = models.ActionsPerTurn(
        id_game=game_id,
        player_id=player_id,
        action_type=ActionType.INSTANT,
        action_name=ActionName.DRAFT_PHASE,
        result=ActionResult.PENDING,
        action_time=datetime.now(),
        action_time_end=None,
        parent_action_id=action_yyy.id,
        triggered_by_action_id=action_xxx.id
    )
    db.add(action_zzz)
    
    nsf_card = models.CardsXGame(
        id_game=game_id,
        id_card=13,
        is_in=CardState.DISCARD,
        position=1,
        player_id=None,
        hidden=False
    )
    db.add(nsf_card)
    
    db.commit()
    
    return action_xxx.id


class TestCancelNSFRoute:
    """Tests para POST /api/game/{room_id}/instant/not-so-fast/cancel"""
    
    def test_cancel_create_set_normal(self, client: TestClient, setup_game_data):
        """Debe crear set de Parker Pyne sin efecto"""
        data = setup_game_data
        db = TestingSessionLocal()
        
        # Crear acción cancelada
        action_id = create_cancelled_action(db, data["game_id"], data["player1_id"])
        
        response = client.post(
            f"/api/game/{data['room_id']}/instant/not-so-fast/cancel",
            json={
                "actionId": action_id,
                "playerId": data["player1_id"],
                "cardIds": [data["card_pyne1_id"], data["card_pyne2_id"]],
                "additionalData": {
                    "actionType": "CREATE_SET"
                }
            }
        )
        
        assert response.status_code == 200
        result = response.json()
        
        assert result["success"] is True
        assert "bajar set de detective" in result["message"]
        assert "Parker Pyne" in result["message"]
    
    def test_cancel_create_set_with_eileen(self, client: TestClient, setup_game_data):
        """Debe dejar cartas en HAND cuando set contiene Eileen"""
        data = setup_game_data
        db = TestingSessionLocal()
        
        # Crear otra Eileen para hacer un set
        card_eileen2 = models.CardsXGame(
            id_game=data["game_id"],
            id_card=9,
            is_in=CardState.HAND,
            position=10,
            player_id=data["player1_id"],
            hidden=True
        )
        db.add(card_eileen2)
        db.commit()
        
        action_id = create_cancelled_action(db, data["game_id"], data["player1_id"])
        
        response = client.post(
            f"/api/game/{data['room_id']}/instant/not-so-fast/cancel",
            json={
                "actionId": action_id,
                "playerId": data["player1_id"],
                "cardIds": [data["card_eileen1_id"], card_eileen2.id],
                "additionalData": {
                    "actionType": "CREATE_SET"
                }
            }
        )
        
        assert response.status_code == 200
        result = response.json()
        
        assert result["success"] is True
        assert "Eileen vuelve a la mano" in result["message"]
    
    def test_cancel_event_card(self, client: TestClient, setup_game_data):
        """Debe mover carta evento al discard debajo de NSF"""
        data = setup_game_data
        db = TestingSessionLocal()
        
        action_id = create_cancelled_action(db, data["game_id"], data["player1_id"])
        
        response = client.post(
            f"/api/game/{data['room_id']}/instant/not-so-fast/cancel",
            json={
                "actionId": action_id,
                "playerId": data["player1_id"],
                "cardIds": [data["card_event_id"]],
                "additionalData": {
                    "actionType": "EVENT"
                }
            }
        )
        
        assert response.status_code == 200
        result = response.json()
        
        assert result["success"] is True
        assert "carta evento" in result["message"]
        assert "mazo de descarte" in result["message"]
    
    def test_cancel_add_to_set_with_eileen(self, client: TestClient, setup_game_data):
        """Debe dejar Eileen en HAND al agregar a set"""
        data = setup_game_data
        db = TestingSessionLocal()
        
        action_id = create_cancelled_action(db, data["game_id"], data["player1_id"])
        
        response = client.post(
            f"/api/game/{data['room_id']}/instant/not-so-fast/cancel",
            json={
                "actionId": action_id,
                "playerId": data["player1_id"],
                "cardIds": [data["card_eileen1_id"]],
                "additionalData": {
                    "actionType": "ADD_TO_SET",
                    "targetPlayerId": data["player2_id"],
                    "targetSetId": 11,  # Poirot set
                    "setPosition": 3
                }
            }
        )
        
        assert response.status_code == 200
        result = response.json()
        
        assert result["success"] is True
        assert "Eileen vuelve a la mano" in result["message"]
    
    def test_cancel_validates_room_not_found(self, client: TestClient, setup_game_data):
        """Debe retornar 404 si la room no existe"""
        data = setup_game_data
        db = TestingSessionLocal()
        
        action_id = create_cancelled_action(db, data["game_id"], data["player1_id"])
        
        response = client.post(
            f"/api/game/99999/instant/not-so-fast/cancel",
            json={
                "actionId": action_id,
                "playerId": data["player1_id"],
                "cardIds": [data["card_pyne1_id"]],
                "additionalData": {
                    "actionType": "CREATE_SET"
                }
            }
        )
        
        assert response.status_code == 404
        assert "detail" in response.json()
    
    def test_cancel_validates_action_not_cancelled(self, client: TestClient, setup_game_data):
        """Debe retornar 400 si la acción no está en estado CANCELLED"""
        data = setup_game_data
        db = TestingSessionLocal()
        
        # Crear acción NO cancelada (PENDING)
        action = models.ActionsPerTurn(
            id_game=data["game_id"],
            player_id=data["player1_id"],
            action_type=ActionType.INIT,
            action_name=ActionName.DRAFT_PHASE,
            result=ActionResult.PENDING,  # NO CANCELLED
            action_time=datetime.now(),
            action_time_end=None,
            parent_action_id=None,
            triggered_by_action_id=None
        )
        db.add(action)
        db.commit()
        
        response = client.post(
            f"/api/game/{data['room_id']}/instant/not-so-fast/cancel",
            json={
                "actionId": action.id,
                "playerId": data["player1_id"],
                "cardIds": [data["card_pyne1_id"]],
                "additionalData": {
                    "actionType": "CREATE_SET"
                }
            }
        )
        
        assert response.status_code == 400
        assert "detail" in response.json()
