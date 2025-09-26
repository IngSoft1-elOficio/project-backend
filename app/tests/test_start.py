import sys
import types
import pytest
from types import SimpleNamespace
from fastapi import HTTPException


# Build simple mocks for models used in start.py
class RoomMock:
    # class attrs to allow expressions like Room.id in filters
    id = None
    name = None
    player_qty = None
    status = None

    def __init__(self, id, name, player_qty, status):
        self.id = id
        self.name = name
        self.player_qty = player_qty
        self.status = status
        self.id_game = None


class PlayerMock:
    # class attrs so Player.id, Player.is_host accessible in expressions
    id = None
    is_host = None
    id_room = None

    def __init__(self, id, name, birthdate, is_host, id_room):
        self.id = id
        self.name = name
        self.birthdate = birthdate
        self.is_host = is_host
        self.id_room = id_room
        self.order = None


class CardMock:
    # class attrs for Card.id/name/type
    id = None
    name = None
    type = None

    def __init__(self, id, name, type):
        self.id = id
        self.name = name
        self.type = type


# Small expression/column stubs so code can call .in_(), __eq__ and ~ without error
class Expr:
    def __init__(self, op, left, right=None):
        self.op = op
        self.left = left
        self.right = right

    def __invert__(self):
        return Expr('NOT', self)

    def __repr__(self):
        return f"Expr({self.op}, {self.left}, {self.right})"


class ColumnMock:
    def __init__(self, name):
        self.name = name

    def in_(self, seq):
        return Expr('IN', self, tuple(seq))

    def __eq__(self, other):
        return Expr('EQ', self, other)

    def __repr__(self):
        return f"Column({self.name})"

# attach class-level ColumnMock attributes so expressions like Card.type.in_(...) work
RoomMock.id = ColumnMock('room.id')
PlayerMock.id = ColumnMock('player.id')
PlayerMock.is_host = ColumnMock('player.is_host')
PlayerMock.id_room = ColumnMock('player.id_room')
CardMock.id = ColumnMock('card.id')
CardMock.type = ColumnMock('card.type')


class CardsXGameMock:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class MockDB:
    def __init__(self, room: RoomMock, players: list, cards: list):
        self._room = room
        self._players = players
        self._cards = cards
        self.added = []

    def query(self, model):
        outer = self

        class Q:
            def __init__(self, model):
                self.model = model

            def filter(self, *args, **kwargs):
                if self.model == RoomMock:
                    class RQ:
                        def first(self_in):
                            return outer._room
                    return RQ()

                if self.model == PlayerMock:
                    class PQ:
                        def all(self_in):
                            return outer._players

                        def first(self_in):
                            # try to emulate filtering for host or by id
                            id_filter = kwargs.get('id')
                            if id_filter is not None:
                                for p in outer._players:
                                    if p.id == id_filter:
                                        return p
                            # fallback: return first host in same room if any
                            for p in outer._players:
                                if getattr(p, 'is_host', False) and p.id_room == outer._room.id:
                                    return p
                            return None
                    return PQ()

                if self.model == CardMock:
                    class CQ:
                        def order_by(self_in, *a, **k):
                            return self_in

                        def limit(self_in, n):
                            return self_in

                        def all(self_in):
                            return outer._cards

                        def first(self_in):
                            return outer._cards[0] if outer._cards else None
                    return CQ()

                return Q(self.model)

        return Q(model)

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        pass

    def refresh(self, obj):
        if hasattr(obj, 'id') and obj.id is None:
            obj.id = 999


# inject fake modules used by the start route
fake_db = types.ModuleType("app.db.database")
fake_db.SessionLocal = lambda: None
sys.modules["app.db.database"] = fake_db

fake_models = types.ModuleType("app.db.models")
fake_models.Room = RoomMock
fake_models.Player = PlayerMock
fake_models.Game = lambda: SimpleNamespace(id=None, player_turn_id=None)
fake_models.Card = CardMock
fake_models.CardsXGame = CardsXGameMock
fake_models.CardState = SimpleNamespace(HAND="HAND", SECRET_SET="SECRET_SET", DECK="DECK")
fake_models.CardType = SimpleNamespace(EVENT="EVENT", SECRET="SECRET", INSTANT="INSTANT", DEVIUOS="DEVIUOS", DETECTIVE="DETECTIVE")
fake_models.RoomStatus = SimpleNamespace(WAITING="WAITING", INGAME="INGAME")
sys.modules["app.db.models"] = fake_models

# patch sockets manager
fake_ws = types.ModuleType("app.sockets.socket_manager")
class FakeWSManager:
    async def emit_to_room(self, game_id, event, payload):
        return True

def fake_get_ws_manager():
    return FakeWSManager()

fake_ws.get_ws_manager = fake_get_ws_manager
sys.modules["app.sockets.socket_manager"] = fake_ws

# now import the function under test
from app.routes.start import start_game


def test_start_forbidden_when_not_host():
    room = RoomMock(1, "r", 2, fake_models.RoomStatus.WAITING)
    players = [PlayerMock(1, "a", __import__('datetime').date(2000,1,1), False, 1), PlayerMock(2, "b", __import__('datetime').date(2000,1,2), False, 1)]
    cards = [CardMock(i, f"c{i}", fake_models.CardType.EVENT) for i in range(1, 20)]
    db = MockDB(room, players, cards)

    with pytest.raises(HTTPException) as excinfo:
        start_game(1, SimpleNamespace(user_id=1), db=db)
    assert excinfo.value.status_code == 403


def test_start_success_creates_game_and_payload():
    room = RoomMock(1, "r", 2, fake_models.RoomStatus.WAITING)
    # host is player 1
    players = [PlayerMock(1, "a", __import__('datetime').date(2000,1,1), True, 1), PlayerMock(2, "b", __import__('datetime').date(1999,1,2), False, 1)]
    # create many cards including secrets and instants
    cards = []
    for i in range(1, 100):
        t = fake_models.CardType.SECRET if i % 10 == 0 else fake_models.CardType.EVENT
        cards.append(CardMock(i, f"c{i}", t))
    db = MockDB(room, players, cards)

    payload = start_game(1, SimpleNamespace(user_id=1), db=db)
    assert isinstance(payload, dict)
    assert payload['game']['id'] is not None
    assert 'turn' in payload
    # ensure CxG entries were added to db.added
    assert any(isinstance(a, CardsXGameMock) for a in db.added)
