import pytest
import pytest_asyncio
import types
import random
from datetime import date
import app.routes.start as route_mod
from app.db import models as db_models
start_game = route_mod.start_game
RoomStatus = db_models.RoomStatus
CardType = db_models.CardType
CardState = db_models.CardState

class ConditionMock:
    def __init__(self, left, op, right):
        self.left = left
        self.op = op
        self.right = types.SimpleNamespace(value=right)
    def __invert__(self): return ConditionMock(self.left, f"~{self.op}", self.right.value)

class ColumnMock:
    def __init__(self, key): self.key = key
    def __eq__(self, other): return ConditionMock(self, "==", other)
    def in_(self, items): return ConditionMock(self, "in", items)
    def __invert__(self): return ConditionMock(self, "~", None)
    def asc(self): return f"{self.key}_asc"

class Room:
    id = None
    def __init__(self, id, name="room", players_min=2, players_max=6, status=RoomStatus.WAITING):
        self.id, self.name, self.players_min, self.players_max, self.status = id, name, players_min, players_max, status
        self.id_game = None

class Player:
    id, id_room, is_host = ColumnMock("id"), ColumnMock("id_room"), ColumnMock("is_host")
    def __init__(self, id, name, id_room, birthdate, is_host=False):
        self.id, self.name, self.id_room, self.birthdate, self.is_host = id, name, id_room, birthdate, is_host
        self.order = None

class Card:
    id, name, type = ColumnMock("id"), ColumnMock("name"), ColumnMock("type")
    def __init__(self, id, name, type, qty=1): self.id, self.name, self.type, self.qty = id, name, type, qty
    
class CardsXGame:
    id_game, is_in, player_id, position, id_card = [ColumnMock(x) for x in
        ("id_game", "is_in", "player_id", "position", "id_card")]
    _id_counter = 0
    def __init__(self, **kwargs): 
        CardsXGame._id_counter += 1
        self.id = CardsXGame._id_counter
        self.__dict__.update(kwargs)

class GameObj:  # creado por create_game
    def __init__(self, id): self.id, self.player_turn_id = id, None

class QueryFake:
    def __init__(self, db, model): self.db, self.model, self._filters = db, model, []
    def filter(self, *conds): self._filters.extend(conds); return self
    def order_by(self, *_, **__): return self
    def _matches(self, obj):
        for cond in self._filters:
            if getattr(obj, cond.left.key) != cond.right.value: return False
        return True
    def first(self):
        if self.model is Room: return self.db.rooms[0] if self.db.rooms else None
        if self.model is Player:
            for p in self.db.players:
                if self._matches(p): return p
        if self.model is Card: return self.db.cards[0] if self.db.cards else None
    def all(self):
        if self.model is Player: return [p for p in self.db.players if p.id_room == self.db.rooms[0].id]
        if self.model is Card: return list(self.db.cards)
        return []

class FakeDB:
    def __init__(self): self.rooms, self.players, self.cards, self.added = [], [], [], []
    def query(self, model): return QueryFake(self, model)
    def add(self, obj): self.added.append(obj)
    def commit(self): self.committed = True
    def refresh(self, obj): pass
    def rollback(self): self._rolledback = True
    def close(self): pass
    def flush(self): pass

@pytest.fixture(autouse=True)
def no_shuffle(monkeypatch): monkeypatch.setattr(random, "shuffle", lambda x: x)

class FakeWSService:
    def __init__(self, fail=False): self.fail, self.notified = fail, False
    async def notificar_estado_partida(self, room_id, game_state):
        self.notified = True
        if self.fail: raise Exception("ws fail")

@pytest.fixture
def fake_ws(monkeypatch):
    svc = FakeWSService(); monkeypatch.setattr("app.routes.start.get_websocket_service", lambda: svc); return svc

@pytest.fixture
def fake_create(monkeypatch):
    monkeypatch.setattr("app.routes.start.create_game", lambda db, *args, **kwargs: GameObj(100))

@pytest_asyncio.fixture
async def setup_db():
    db = FakeDB()
    db.rooms.append(Room(1, "Sala Test"))
    db.players += [
        Player(10, "A", 1, date(1990,1,1), True),
        Player(11, "B", 1, date(1991,1,1)),
        Player(12, "C", 1, date(1992,1,1)),
    ]
    db.cards += [Card(i, f"C{i}", CardType.SECRET if i>4 else CardType.EVENT, 3) for i in range(1,10)]
    return db

def patch_models(monkeypatch):
    for name in ("RoomStatus","CardType","CardState","Player","Room","Card","CardsXGame"):
        monkeypatch.setattr(route_mod, name, globals()[name])

# tests
@pytest.mark.asyncio
async def test_start_ok(setup_db, fake_ws, fake_create, monkeypatch):
    patch_models(monkeypatch)
    res = await start_game(1, types.SimpleNamespace(user_id=10), setup_db)
    assert res["game"]["id"] == 100
    assert any(isinstance(a, CardsXGame) for a in setup_db.added)
    assert fake_ws.notified

@pytest.mark.asyncio
async def test_room_not_found():
    with pytest.raises(Exception, match="Sala no encontrada"):
        await start_game(1, types.SimpleNamespace(user_id=1), FakeDB())

@pytest.mark.asyncio
async def test_room_not_waiting(monkeypatch):
    db = FakeDB(); db.rooms.append(Room(2, status="OTHER"))
    patch_models(monkeypatch)
    with pytest.raises(Exception, match="La sala no está en estado WAITING"):
        await start_game(2, types.SimpleNamespace(user_id=1), db)

@pytest.mark.asyncio
async def test_not_enough_players(monkeypatch):
    db = FakeDB(); db.rooms.append(Room(3, players_min=4))
    db.players += [Player(1,"A",3,date(1990,1,1),True), Player(2,"B",3,date(1991,1,1))]
    patch_models(monkeypatch)
    with pytest.raises(Exception, match="Cantidad incorrecta de jugadores"):
        await start_game(3, types.SimpleNamespace(user_id=1), db)

@pytest.mark.asyncio
async def test_not_host(monkeypatch, setup_db):
    patch_models(monkeypatch)
    with pytest.raises(Exception, match="Solo el host puede iniciar"):
        await start_game(1, types.SimpleNamespace(user_id=11), setup_db)

@pytest.mark.asyncio
async def test_ws_failure(monkeypatch, setup_db, fake_create):
    patch_models(monkeypatch)
    monkeypatch.setattr("app.routes.start.get_websocket_service", lambda: FakeWSService(True))
    res = await start_game(1, types.SimpleNamespace(user_id=10), setup_db)
    assert res["game"]["id"] == 100

@pytest.mark.asyncio
async def test_commit_fail(monkeypatch, setup_db, fake_ws, fake_create):
    patch_models(monkeypatch)
    setup_db.commit = lambda: (_ for _ in ()).throw(Exception("commit fail"))
    with pytest.raises(Exception, match="commit fail"):
        await start_game(1, types.SimpleNamespace(user_id=10), setup_db)

@pytest.mark.asyncio
async def test_refresh_fail(monkeypatch, setup_db, fake_ws, fake_create):
    patch_models(monkeypatch)
    setup_db.refresh = lambda _: (_ for _ in ()).throw(Exception("refresh fail"))
    with pytest.raises(Exception, match="refresh fail"):
        await start_game(1, types.SimpleNamespace(user_id=10), setup_db)

@pytest.mark.asyncio
async def test_unexpected_exception(monkeypatch, setup_db, fake_ws, fake_create):
    patch_models(monkeypatch)
    monkeypatch.setattr("builtins.enumerate", lambda *_: (_ for _ in ()).throw(Exception("unexpected fail")))
    with pytest.raises(Exception, match="Error interno al iniciar la partida"):
        await start_game(1, types.SimpleNamespace(user_id=10), setup_db)

@pytest.mark.asyncio
async def test_five_players(monkeypatch, fake_ws, fake_create):
    db = FakeDB(); db.rooms.append(Room(1))
    db.players += [Player(10+i, f"P{i}", 1, date(1990+i,1,1), i==0) for i in range(5)]
    db.cards += [Card(i, f"C{i}", CardType.SECRET if i>4 else CardType.EVENT, 3) for i in range(1,10)]
    patch_models(monkeypatch)
    res = await start_game(1, types.SimpleNamespace(user_id=10), db)
    assert res["game"]["id"] == 100

def test_get_db_generator():
    gen = route_mod.get_db()
    db = next(gen); assert db
    with pytest.raises(StopIteration): next(gen)

# test para el 100% de coverage
class DummyModel:
    pass

@pytest.mark.asyncio
async def test_queryfake_all_other_model():
    db = FakeDB()
    q = db.query(DummyModel)
    res = q.all()
    assert res == []

# Test para cubrir el rollback en excepcion general
@pytest.mark.asyncio
async def test_rollback_on_flush_exception(monkeypatch, setup_db, fake_ws, fake_create):
    patch_models(monkeypatch)
    def fail_flush():
        raise Exception("flush fail")
    setup_db.flush = fail_flush
    with pytest.raises(Exception, match="Error interno al iniciar la partida: flush fail"):
        await start_game(1, types.SimpleNamespace(user_id=10), setup_db)
    assert hasattr(setup_db, '_rolledback') and setup_db._rolledback