import pytest
from fastapi.testclient import TestClient
from app.routes.another_victim import router, get_db
from app.db.models import (
    Game, Room, Player, CardsXGame, CardState, Turn,
    TurnStatus, Card
)
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.database import Base
from fastapi import FastAPI
from app.sockets.socket_service import get_websocket_service


# =======================================
#  SETUP TEST DATABASE (IN-MEMORY SQLITE)
# =======================================
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


# =======================================
#  FAKE WEBSOCKET MANAGER
# =======================================
class FakeWsManager:
    """Simula un manejador WS que guarda los mensajes emitidos."""
    def __init__(self):
        self.room_messages = []
        self.sid_messages = []

    async def emit_to_room(self, room_id, event_type, data):
        self.room_messages.append((room_id, event_type, data))

    async def emit_to_sid(self, sid, event_type, data):
        self.sid_messages.append((sid, event_type, data))

    def get_sids_in_game(self, room_id):
        # Devuelve una lista simulada de conexiones
        return ["fake_sid_1", "fake_sid_2"]

    def get_user_session(self, sid):
        # Simula sesiones con user_id
        return {"user_id": 10 if sid == "fake_sid_1" else 20}


# =======================================
#  TEST APP
# =======================================
app = FastAPI()
app.include_router(router)
app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)


@pytest.fixture(scope="function", autouse=True)
def setup_ws_manager():
    """Inyecta un FakeWsManager antes de cada test."""
    ws_service = get_websocket_service()
    ws_service.ws_manager = FakeWsManager()
    return ws_service.ws_manager


@pytest.fixture
def setup_data():
    """Carga datos mínimos de juego y jugadores en la DB."""
    db = TestingSessionLocal()

    # Crear juego y sala
    game = Game(id=1, player_turn_id=10)
    room = Room(id=100, id_game=1)
    db.add_all([game, room])

    # Crear jugadores
    actor = Player(id=10, id_room=100, name="Lucas")
    victim = Player(id=20, id_room=100, name="Marcos")
    db.add_all([actor, victim])

    # Turno activo
    turn = Turn(id=1, id_game=1, player_id=10, status=TurnStatus.IN_PROGRESS)
    db.add(turn)

    # Crear cartas
    card_a = Card(id=1, name="Knife", type="WEAPON")
    card_b = Card(id=2, name="Gun", type="WEAPON")
    card_event = Card(id=13, name="Another Victim", type="EVENT")
    db.add_all([card_a, card_b, card_event])

    # Set de la víctima
    victim_set = [
        CardsXGame(id=1, id_game=1, player_id=20, is_in=CardState.DETECTIVE_SET, position=1, card_id=1),
        CardsXGame(id=2, id_game=1, player_id=20, is_in=CardState.DETECTIVE_SET, position=1, card_id=2)
    ]

    # Carta "Another Victim" en la mano del actor
    actor_card = CardsXGame(id=3, id_game=1, player_id=10, is_in=CardState.HAND, position=1, card_id=13)
    db.add_all(victim_set + [actor_card])
    db.commit()
    db.close()


# =======================================
#  TEST PRINCIPAL
# =======================================
def test_another_victim_success(setup_data, setup_ws_manager):
    """Verifica que el endpoint transfiera correctamente un set."""
    # Request
    response = client.post(
        "/game/100/event/another-victim",
        json={"originalOwnerId": 20, "setPosition": 1},
        headers={"HTTP_USER_ID": "10"},
    )

    assert response.status_code == 200, response.text
    body = response.json()

    # --- Validación del resultado ---
    assert body["success"] is True
    transferred = body["transferredSet"]
    assert transferred["originalOwnerId"] == 20
    assert transferred["newOwnerId"] == 10
    assert len(transferred["cards"]) == 2

    # --- Validación de notificaciones WS ---
    room_msgs = [msg[1] for msg in setup_ws_manager.room_messages]
    expected = {
        "event_step_update",
        "event_action_complete",
        "game_state_public",
    }
    assert expected.issubset(set(room_msgs)), f"Mensajes WS faltantes: {expected - set(room_msgs)}"
