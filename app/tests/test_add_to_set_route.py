# app/tests/test_add_to_set_route.py
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
from app.routes.add_to_set import get_db
from app.routes import add_to_set
from app.services.detective_set_service import DetectiveSetService
from fastapi import HTTPException

SQLALCHEMY_DATABASE_URL = "sqlite://"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture
def client():
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
def setup_game_data():
    db = TestingSessionLocal()
    try:
        game = Game(id=1, player_turn_id=1)
        room = Room(id=1, name="Sala", status=RoomStatus.INGAME, id_game=1)
        p1 = Player(
            id=1,
            name="Jugador1",
            avatar_src="a.png",
            birthdate=date(2000, 1, 1),
            id_room=1,
            is_host=True,
        )
        turn = Turn(id=1, number=1, id_game=1, player_id=1, status=TurnStatus.IN_PROGRESS)
        card = Card(
            id=8, name="Tommy Beresford", description="Detective",
            type=CardType.DETECTIVE, img_src="t.png", qty=2
        )
        cardx = CardsXGame(
            id=10, id_game=1, id_card=8, is_in=CardState.HAND,
            position=1, player_id=1, hidden=True
        )
        set_card = CardsXGame(
            id=11, id_game=1, id_card=8, is_in=CardState.DETECTIVE_SET,
            position=1, player_id=1, hidden=False
        )
        db.add_all([game, room, p1, turn, card, cardx, set_card])
        db.commit()
    finally:
        db.close()


class TestAddToSetEndpoint:
    def test_equivalente_exitoso(self, client, setup_game_data):
        """Equivalente - flujo exitoso"""
        r = client.post(
            "/api/game/1/add-to-set",
            json={"owner": 1, "setType": "beresford", "card": 10, "setPosition": 1},
        )
        assert r.status_code == 200
        js = r.json()
        assert js["success"] is True
        assert "actionId" in js

    def test_equivalente_room_inexistente(self, client):
        """Equivalente - sala inexistente"""
        r = client.post(
            "/api/game/999/add-to-set",
            json={"owner": 1, "setType": "beresford", "card": 1, "setPosition": 1},
        )
        assert r.status_code == 404

    def test_equivalente_jugador_fuera_turno(self, client, setup_game_data):
        """Equivalente - jugador fuera de turno"""
        db = TestingSessionLocal()
        g = db.query(Game).get(1)
        g.player_turn_id = 2
        db.commit()
        db.close()
        r = client.post(
            "/api/game/1/add-to-set",
            json={"owner": 1, "setType": "beresford", "card": 10, "setPosition": 1},
        )
        assert r.status_code == 403

    def test_equivalente_carta_inexistente(self, client, setup_game_data):
        """Equivalente - carta no en mano"""
        r = client.post(
            "/api/game/1/add-to-set",
            json={"owner": 1, "setType": "beresford", "card": 999, "setPosition": 1},
        )
        assert r.status_code == 400

    def test_borde_set_inexistente(self, client, setup_game_data):
        """Borde - set inexistente"""
        r = client.post(
            "/api/game/1/add-to-set",
            json={"owner": 1, "setType": "beresford", "card": 10, "setPosition": 5},
        )
        assert r.status_code == 404

    def test_equivalente_carta_erronea_para_set(self, client, setup_game_data):
        """Equivalente - carta errónea para tipo de set"""
        db = TestingSessionLocal()
        card = db.query(CardsXGame).get(10)
        card.id_card = 6  # Marple
        db.commit()
        db.close()
        r = client.post(
            "/api/game/1/add-to-set",
            json={"owner": 1, "setType": "beresford", "card": 10, "setPosition": 1},
        )
        assert r.status_code == 400

    def test_cb_flujo_exitoso(self, client, monkeypatch, setup_game_data):
        """CajaBlanca - ruta exitosa"""
        monkeypatch.setattr(
            DetectiveSetService, "add_detective_to_set",
            lambda self, game_id, req: (99, {"type": "selectPlayer"})
        )
        resp = client.post(
            "/api/game/1/add-to-set",
            json={"owner": 1, "setType": "beresford", "card": 10, "setPosition": 1},
        )
        assert resp.status_code == 200
        assert "actionId" in resp.json()

    def test_cb_http_exception_capturada(self, client, monkeypatch, setup_game_data):
        """CajaBlanca - ruta lanza HTTPException (capturada correctamente)"""
        def fail(*args, **kw): raise HTTPException(status_code=404, detail="No encontrado")
        monkeypatch.setattr(DetectiveSetService, "add_detective_to_set", fail)
        r = client.post(
            "/api/game/1/add-to-set",
            json={"owner": 1, "setType": "marple", "card": 1, "setPosition": 1},
        )
        assert r.status_code == 404

    def test_cb_excepcion_general_manejada(self, client, monkeypatch, setup_game_data):
        """CajaBlanca - excepción no HTTP produce 500"""
        def boom(*a, **k): raise RuntimeError("Boom interno")
        monkeypatch.setattr(DetectiveSetService, "add_detective_to_set", boom)
        r = client.post(
            "/api/game/1/add-to-set",
            json={"owner": 1, "setType": "marple", "card": 1, "setPosition": 1},
        )
        assert r.status_code == 500
        assert "Internal server error" in r.json()["detail"]

    def test_cb_fallo_websocket_no_rompe(self, client, monkeypatch, setup_game_data):
        """CajaBlanca - fallo en notificación WebSocket no rompe respuesta"""
        class DummyWS:
            async def notificar_estado_partida(self, **kw): raise RuntimeError("ws fail")
            async def notificar_detective_action_started(self, **kw): return None
        monkeypatch.setattr(add_to_set, "get_websocket_service", lambda: DummyWS())
        monkeypatch.setattr(
            DetectiveSetService, "add_detective_to_set",
            lambda *a, **kw: (88, {"type": "selectPlayer"})
        )
        r = client.post(
            "/api/game/1/add-to-set",
            json={"owner": 1, "setType": "beresford", "card": 10, "setPosition": 1},
        )
        assert r.status_code == 200