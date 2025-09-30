import sys
import types
import pytest
from types import SimpleNamespace

from fastapi import HTTPException

# --- create fake modules before importing app.routes.game to avoid importing real DB/engine ---
class RoomTest:
    name = "name"

    def __init__(self, name=None, player_qty=None, status=None):
        self.name = name
        self.player_qty = player_qty
        self.status = status
        self.id = None


class PlayerTest:
    def __init__(self, is_host=None, name=None, avatar_src=None, birthdate=None):
        self.is_host = is_host
        self.name = name
        self.avatar_src = avatar_src
        self.birthdate = birthdate
        self.id = None


class QueryMock:
    def __init__(self, result=None):
        self._result = result

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self._result


class MockDB:
    def __init__(self, query_result=None):
        self._query_result = query_result
        self.added = []

    def query(self, model):
        return QueryMock(self._query_result)

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        for obj in self.added:
            if getattr(obj, "id", None) is None:
                obj.id = 1 if isinstance(obj, RoomTest) else 2

    def refresh(self, obj):
        if getattr(obj, "id", None) is None:
            obj.id = 1 if isinstance(obj, RoomTest) else 2


# inject fake app.db.database and app.db.models modules
fake_db_mod = types.ModuleType("app.db.database")
fake_db_mod.SessionLocal = lambda: MockDB()
sys.modules["app.db.database"] = fake_db_mod

fake_models_mod = types.ModuleType("app.db.models")
fake_models_mod.Room = RoomTest
fake_models_mod.Player = PlayerTest
fake_models_mod.RoomStatus = SimpleNamespace(WAITING="waiting")
sys.modules["app.db.models"] = fake_models_mod

# now import the module under test
from app.routes import game


def make_newgame_payload():
    return SimpleNamespace(
        room=SimpleNamespace(nombre_partida="test-room", jugadores=4),
        player=SimpleNamespace(host_id=True, nombre="host-player", avatar="/img/1.png", fechaNacimiento="2000-01-01"),
    )


def test_create_game_success():
    db = MockDB(query_result=None)  # no existing room
    newgame = make_newgame_payload()
    result = game.create_game(newgame, db=db)

    assert isinstance(result, dict)
    assert result["id_partida"] == 1
    assert result["nombre_partida"] == "test-room"
    assert result["jugadores"] == 4
    assert result["estado"] == "waiting"
    assert result["host_id"] == 2
    assert any(isinstance(o, RoomTest) for o in db.added)
    assert any(isinstance(o, PlayerTest) for o in db.added)


def test_create_game_conflict():
    db = MockDB(query_result=SimpleNamespace())
    newgame = make_newgame_payload()

    with pytest.raises(HTTPException) as excinfo:
        game.create_game(newgame, db=db)

    assert excinfo.value.status_code == 409
