import pytest
from unittest.mock import MagicMock, AsyncMock
from fastapi import HTTPException
from app.routes import draft
from app.services import draft_service

def test_list_draft_cards_returns_list(monkeypatch):
    mock_deck = MagicMock()
    mock_deck.draft = [MagicMock(id=1), MagicMock(id=2)]
    monkeypatch.setattr(draft_service, "_build_deck_view", lambda db, gid: mock_deck)
    result = draft_service.list_draft_cards("db", 1)
    assert len(result) == 2

def test_pick_card_from_draft_moves_and_replaces_topdeck(monkeypatch):
    class CardMock:
        def __init__(self, id, name, type_value, img_src):
            self.id = id
            self.name = name
            self.type = MagicMock(value=type_value)
            self.img_src = img_src
    draft_card = MagicMock(id=1, is_in="DRAFT", position=2, player_id=None)
    draft_card.card = CardMock(1, "CardX", "event", "img.png")
    deck_card = MagicMock(id=3, is_in="DECK", position=1)
    deck_card.card = CardMock(3, "CardY", "event", "img2.png")
    db = MagicMock()
    db.query().filter().first.side_effect = [draft_card, (5,), deck_card]
    result = draft_service.pick_card_from_draft(db, 1, 99)
    assert draft_card.is_in == "HAND"
    assert draft_card.player_id == 99
    assert deck_card.is_in == "DECK"
    assert deck_card.position == 1
    assert result.id == 1
    assert result.name == "CardX"
    assert result.type == "event"

def test_pick_card_from_draft_no_topdeck(monkeypatch):
    class CardMock:
        def __init__(self, id, name, type_value, img_src):
            self.id = id
            self.name = name
            self.type = MagicMock(value=type_value)
            self.img_src = img_src
    db = MagicMock()
    draft_card = MagicMock(id=1, is_in="DRAFT", position=1)
    draft_card.card = CardMock(1, "CardX", "event", "img.png")
    db.query().filter().first.side_effect = [draft_card, None, None]
    result = draft_service.pick_card_from_draft(db, 1, 5)
    assert result.id == 1
    assert result.name == "CardX"
    assert result.type == "event"
    # No se verifica img_src porque CardSummary no lo tiene

def test_pick_card_from_draft_not_found(monkeypatch):
    db = MagicMock()
    db.query().filter().first.return_value = None
    result = draft_service.pick_card_from_draft(db, 999, 5)
    assert result is None

@pytest.fixture
def mock_db_game_room():
    db = MagicMock()
    mock_game = MagicMock(player_turn_id=1)
    mock_room = MagicMock(id=77)
    db.query().filter().first.side_effect = [mock_game, mock_room]
    db.query().filter().count.return_value = 3
    return db, mock_game, mock_room

@pytest.mark.asyncio
@pytest.mark.parametrize("side_effect, hand, status, detail", [
    ([None, None], None, 404, "game_not_found"),
    ([MagicMock(player_turn_id=99), None], MagicMock(cards=[1]), 403, "not_your_turn"),
    ([MagicMock(player_turn_id=1), None], MagicMock(cards=[1,2,3,4,5,6]), 403, "must_discard_before_draft"),
    ([MagicMock(player_turn_id=1), None], MagicMock(cards=[1,2]), 404, "Card not found in draft"),
])
async def test_pick_card_errors(monkeypatch, side_effect, hand, status, detail):
    db = MagicMock()
    db.query().filter().first.side_effect = side_effect
    monkeypatch.setattr(draft, "logger", MagicMock())
    monkeypatch.setattr(draft, "_build_hand_view", lambda *a, **kw: hand)
    monkeypatch.setattr(draft, "list_draft_cards", lambda *a, **kw: [MagicMock(id=99)])
    request = MagicMock(user_id=1, card_id=123)
    with pytest.raises(HTTPException) as exc:
        await draft.pick_card(10, request, db)
    assert exc.value.status_code == status
    assert detail in exc.value.detail

@pytest.mark.asyncio
async def test_pick_card_success_with_ws(monkeypatch, mock_db_game_room):
    db, mock_game, mock_room = mock_db_game_room
    fake_card = MagicMock(id=1)
    fake_picked = MagicMock(id=1)
    fake_game_state = {"estados_privados": {}}
    monkeypatch.setattr(draft, "list_draft_cards", lambda *a, **kw: [fake_card])
    monkeypatch.setattr(draft, "_build_hand_view", lambda *a, **kw: MagicMock(cards=[1, 2]))
    monkeypatch.setattr(draft, "_build_deck_view", lambda *a, **kw: MagicMock())
    monkeypatch.setattr(draft, "pick_card_from_draft", lambda *a, **kw: fake_picked)
    monkeypatch.setattr(draft, "build_complete_game_state", lambda *a, **kw: fake_game_state)
    monkeypatch.setattr(draft, "procesar_ultima_carta", AsyncMock())
    mock_ws = AsyncMock()
    mock_ws.notificar_estados_privados = AsyncMock()
    mock_ws.notificar_estado_partida = AsyncMock()
    monkeypatch.setattr(draft, "get_websocket_service", lambda: mock_ws)
    request = MagicMock(user_id=1, card_id=1)
    result = await draft.pick_card(10, request, db)
    assert "picked_card" in result
    assert result["picked_card"].id == 1
    mock_ws.notificar_estado_partida.assert_awaited_once()

@pytest.mark.asyncio
async def test_pick_card_empty_draft_triggers_procesar_ultima(monkeypatch, mock_db_game_room):
    db, mock_game, mock_room = mock_db_game_room
    db.query().filter().count.return_value = 0
    monkeypatch.setattr(draft, "list_draft_cards", lambda *a, **kw: [MagicMock(id=1)])
    monkeypatch.setattr(draft, "_build_hand_view", lambda *a, **kw: MagicMock(cards=[1]))
    monkeypatch.setattr(draft, "_build_deck_view", lambda *a, **kw: {})
    monkeypatch.setattr(draft, "pick_card_from_draft", lambda *a, **kw: MagicMock(id=1))
    monkeypatch.setattr(draft, "build_complete_game_state", lambda *a, **kw: {})
    mock_ws = AsyncMock()
    monkeypatch.setattr(draft, "get_websocket_service", lambda: mock_ws)
    mock_proc = AsyncMock()
    monkeypatch.setattr(draft, "procesar_ultima_carta", mock_proc)
    request = MagicMock(user_id=1, card_id=1)
    await draft.pick_card(10, request, db)
    mock_proc.assert_awaited_once()

@pytest.mark.asyncio
async def test_pick_card_ws_exception(monkeypatch, mock_db_game_room):
    db, mock_game, mock_room = mock_db_game_room
    monkeypatch.setattr("app.routes.draft._build_hand_view", lambda *a, **kw: MagicMock(cards=[1, 2]))
    monkeypatch.setattr("app.routes.draft.list_draft_cards", lambda *a, **kw: [MagicMock(id=1)])
    monkeypatch.setattr("app.routes.draft.pick_card_from_draft", lambda *a, **kw: MagicMock(id=1))
    monkeypatch.setattr("app.routes.draft.build_complete_game_state", lambda *a, **kw: {"estados_privados": {}})
    monkeypatch.setattr("app.routes.draft._build_deck_view", lambda *a, **kw: MagicMock())
    ws_mock = AsyncMock()
    ws_mock.notificar_estados_privados.side_effect = Exception("ws fail")
    monkeypatch.setattr("app.routes.draft.get_websocket_service", lambda: ws_mock)
    monkeypatch.setattr("app.routes.draft.logger", MagicMock())
    request = MagicMock(user_id=1, card_id=1)
    import app.routes.draft as draft_mod
    await draft_mod.pick_card(10, request, db)
    draft_mod.logger.error.assert_called()

@pytest.mark.asyncio
async def test_pick_card_hand_is_list(monkeypatch, mock_db_game_room):
    db, mock_game, mock_room = mock_db_game_room
    monkeypatch.setattr("app.routes.draft._build_hand_view", lambda *a, **kw: [1, 2, 3, 4, 5, 6])
    monkeypatch.setattr("app.routes.draft.list_draft_cards", lambda *a, **kw: [MagicMock(id=1)])
    monkeypatch.setattr("app.routes.draft.pick_card_from_draft", lambda *a, **kw: MagicMock(id=1))
    monkeypatch.setattr("app.routes.draft.build_complete_game_state", lambda *a, **kw: {"estados_privados": {}})
    monkeypatch.setattr("app.routes.draft._build_deck_view", lambda *a, **kw: MagicMock())
    monkeypatch.setattr("app.routes.draft.logger", MagicMock())
    request = MagicMock(user_id=1, card_id=1)
    import app.routes.draft as draft_mod
    with pytest.raises(HTTPException) as exc:
        await draft_mod.pick_card(10, request, db)
    assert exc.value.status_code == 403
    assert "must_discard_before_draft" in exc.value.detail

@pytest.mark.asyncio
async def test_pick_card_hand_is_other(monkeypatch, mock_db_game_room):
    db, mock_game, mock_room = mock_db_game_room
    monkeypatch.setattr("app.routes.draft._build_hand_view", lambda *a, **kw: None)
    monkeypatch.setattr("app.routes.draft.list_draft_cards", lambda *a, **kw: [MagicMock(id=1)])
    monkeypatch.setattr("app.routes.draft.pick_card_from_draft", lambda *a, **kw: MagicMock(id=1))
    monkeypatch.setattr("app.routes.draft.build_complete_game_state", lambda *a, **kw: {"estados_privados": {}})
    monkeypatch.setattr("app.routes.draft._build_deck_view", lambda *a, **kw: MagicMock())
    monkeypatch.setattr("app.routes.draft.logger", MagicMock())
    request = MagicMock(user_id=1, card_id=1)
    import app.routes.draft as draft_mod
    await draft_mod.pick_card(10, request, db)
    request = MagicMock(user_id=1, card_id=1)

def test_get_db_finally_executes():
    from app.routes.draft import get_db
    gen = get_db()
    db = next(gen)
    assert db is not None
    try:
        pass
    finally:
        gen.close()
