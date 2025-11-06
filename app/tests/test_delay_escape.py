import pytest
from unittest.mock import AsyncMock, patch, Mock
from fastapi import HTTPException
from app.routes.delay import delay_murderer_escape
from app.schemas.delay_schema import delay_escape_request


class TestDelayMurdererEscape:
    """Tests unitarios para el endpoint delay_murderer_escape"""

    # ---------- FIXTURES ----------
    @pytest.fixture
    def mock_db(self):
        db = Mock()
        db.add = Mock()
        db.commit = Mock()
        db.flush = Mock()
        db.rollback = Mock()
        db.query = Mock()
        return db

    @pytest.fixture
    def mock_room(self):
        room = Mock()
        room.id = 1
        room.id_game = 1
        return room

    @pytest.fixture
    def mock_game(self):
        game = Mock()
        game.id = 1
        game.player_turn_id = 7
        return game

    # ---------- TEST: CASO OK ----------
    @pytest.mark.asyncio
    @patch("app.routes.delay.build_complete_game_state", return_value={})
    @patch("app.routes.delay.get_websocket_service", return_value=AsyncMock())
    @patch("app.routes.delay.crud")
    async def test_delay_murderer_escape_ok(self, mock_crud, mock_ws, mock_state, mock_db, mock_room, mock_game):
        """Debe devolver status=ok y las cartas movidas correctamente"""

        mock_crud.get_room_by_id.return_value = mock_room
        mock_crud.get_game_by_id.return_value = mock_game
        mock_crud.get_current_turn.return_value = Mock(id=10)
        mock_crud.create_action.return_value = Mock(id=123)
        mock_crud.list_players_by_room.return_value = []

        event_card = Mock()
        event_card.id = 99
        event_card.card.type = "EVENT"
        mock_db.query.return_value.filter.return_value.first.return_value = event_card

        card1 = Mock(id=1, position=5)
        card2 = Mock(id=2, position=4)
        mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [card1, card2]

        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = Mock(position=10)
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []

        payload = delay_escape_request(card_id=99, quantity=2)
        result = await delay_murderer_escape(room_id=1, payload=payload, user_id=7, db=mock_db)

        assert result["status"] == "ok"
        assert result["action_id"] == 123
        assert result["moved_cards"] == [2, 1]

    # ---------- TEST: ROOM NOT FOUND ----------
    @pytest.mark.asyncio
    @patch("app.routes.delay.crud.get_room_by_id", return_value=None)
    async def test_room_not_found_raises_404(self, mock_room, mock_db):
        payload = delay_escape_request(card_id=1, quantity=1)
        with pytest.raises(HTTPException) as excinfo:
            await delay_murderer_escape(room_id=999, payload=payload, user_id=7, db=mock_db)
        assert excinfo.value.status_code == 404
        assert "room_not_found" in excinfo.value.detail

    # ---------- TEST: NOT YOUR TURN ----------
    @pytest.mark.asyncio
    @patch("app.routes.delay.crud")
    async def test_not_your_turn_raises_403(self, mock_crud, mock_db, mock_room, mock_game):
        mock_crud.get_room_by_id.return_value = mock_room
        mock_game.player_turn_id = 9
        mock_crud.get_game_by_id.return_value = mock_game
        payload = delay_escape_request(card_id=1, quantity=1)
        with pytest.raises(HTTPException) as excinfo:
            await delay_murderer_escape(room_id=1, payload=payload, user_id=7, db=mock_db)
        assert excinfo.value.status_code == 403
        assert "not_your_turn" in excinfo.value.detail

    # ---------- TEST: EVENT CARD NOT FOUND ----------
    @pytest.mark.asyncio
    @patch("app.routes.delay.crud")
    async def test_event_card_not_found_raises_404(self, mock_crud, mock_db, mock_room, mock_game):
        mock_crud.get_room_by_id.return_value = mock_room
        mock_crud.get_game_by_id.return_value = mock_game
        mock_game.player_turn_id = 7
        mock_db.query.return_value.filter.return_value.first.return_value = None
        payload = delay_escape_request(card_id=123, quantity=2)
        with pytest.raises(HTTPException) as excinfo:
            await delay_murderer_escape(room_id=1, payload=payload, user_id=7, db=mock_db)
        assert excinfo.value.status_code == 404
        assert "event_card_not_found" in excinfo.value.detail

    # ---------- TEST: DISCARD EMPTY ----------
    @pytest.mark.asyncio
    @patch("app.routes.delay.build_complete_game_state", return_value={})
    @patch("app.routes.delay.get_websocket_service", return_value=AsyncMock())
    @patch("app.routes.delay.crud")
    async def test_discard_empty_returns_500(self, mock_crud, mock_ws, mock_state, mock_db, mock_room, mock_game):
        """Debe devolver 500 porque el HTTPException(400) interno se captura y se transforma en 500"""
        mock_crud.get_room_by_id.return_value = mock_room
        mock_crud.get_game_by_id.return_value = mock_game
        mock_crud.get_current_turn.return_value = Mock(id=10)
        mock_crud.create_action.return_value = Mock(id=123)

        event_card = Mock()
        event_card.id = 1
        event_card.card.type = "EVENT"
        mock_db.query.return_value.filter.return_value.first.return_value = event_card

        # Descarte vacío → produce el HTTPException(400) interno → atrapado y convertido a 500
        mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []

        payload = delay_escape_request(card_id=1, quantity=1)
        with pytest.raises(HTTPException) as excinfo:
            await delay_murderer_escape(room_id=1, payload=payload, user_id=7, db=mock_db)
        assert excinfo.value.status_code == 500
        assert "internal_error_delay_murderer_escape" in excinfo.value.detail
