import pytest
from unittest.mock import AsyncMock, patch, Mock
from fastapi import HTTPException
from app.routes.delay import delay_murderer_step_1, delay_murderer_order
from app.schemas.delay_schema import delay_escape_start_request, delay_escape_order_request


class TestDelayMurdererEscapeMocked:
    """Tests aislados del endpoint Delay the Murderer's Escape"""

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

    # ---------- STEP 1 ----------

    @pytest.mark.asyncio
    @patch("app.routes.delay.build_complete_game_state", return_value={})
    @patch("app.routes.delay.get_websocket_service", return_value=AsyncMock())
    @patch("app.routes.delay.crud")
    async def test_step1_returns_available_cards_ok(self, mock_crud, mock_ws, mock_state, mock_db, mock_room, mock_game):
        mock_crud.get_room_by_id.return_value = mock_room
        mock_crud.get_game_by_id.return_value = mock_game
        mock_crud.get_current_turn.return_value = Mock(id=123)
        mock_crud.create_action.return_value = Mock(id=999)
        mock_crud.count_cards_by_state.return_value = 3
        mock_crud.list_players_by_room.return_value = []

        # Mock carta válida en mano
        event_card = Mock()
        event_card.id = 99
        event_card.card.type = "EVENT"
        mock_db.query.return_value.filter.return_value.first.return_value = event_card

        mock_card1 = Mock(id=11)
        mock_card2 = Mock(id=12)
        mock_db.query.return_value.join.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [mock_card1, mock_card2]

        payload = delay_escape_start_request(card_id=99, quantity=2)
        result = await delay_murderer_step_1(room_id=1, payload=payload, user_id=7, db=mock_db)

        assert result["action_id"] == 999
        assert result["available_cards"] == [11, 12]

    @pytest.mark.asyncio
    @patch("app.routes.delay.build_complete_game_state", return_value={})
    @patch("app.routes.delay.crud.get_room_by_id", return_value=None)
    async def test_step1_room_not_found_raises_404(self, mock_room, mock_state, mock_db):
        payload = delay_escape_start_request(card_id=1, quantity=1)
        with pytest.raises(HTTPException) as excinfo:
            await delay_murderer_step_1(room_id=99, payload=payload, user_id=7, db=mock_db)
        assert excinfo.value.status_code == 404

    @pytest.mark.asyncio
    @patch("app.routes.delay.build_complete_game_state", return_value={})
    @patch("app.routes.delay.crud")
    async def test_step1_not_your_turn_raises_403(self, mock_crud, mock_state, mock_db, mock_room, mock_game):
        mock_crud.get_room_by_id.return_value = mock_room
        mock_game.player_turn_id = 99
        mock_crud.get_game_by_id.return_value = mock_game
        payload = delay_escape_start_request(card_id=1, quantity=1)
        with pytest.raises(HTTPException) as excinfo:
            await delay_murderer_step_1(room_id=1, payload=payload, user_id=7, db=mock_db)
        assert excinfo.value.status_code == 403

    # ---------- STEP 2 ----------

    @pytest.mark.asyncio
    @patch("app.routes.delay.build_complete_game_state", return_value={})
    @patch("app.routes.delay.get_websocket_service", return_value=AsyncMock())
    @patch("app.routes.delay.crud")
    async def test_step2_moves_cards_ok(self, mock_crud, mock_ws, mock_state, mock_db, mock_room, mock_game):
        mock_crud.get_room_by_id.return_value = mock_room
        mock_crud.get_game_by_id.return_value = mock_game
        mock_crud.get_top_card_by_state.return_value = Mock(position=10)
        mock_crud.get_action_by_id.return_value = Mock(id=55, turn_id=22, selected_card_id=999)
        mock_crud.create_action.return_value = Mock(id=101)
        mock_crud.list_players_by_room.return_value = []

        mock_card = Mock(id=1)
        mock_db.query.return_value.filter.return_value.first.return_value = mock_card

        payload = delay_escape_order_request(action_id=55, ordered_cards_ids=[1, 2, 3])
        result = await delay_murderer_order(room_id=1, payload=payload, user_id=7, db=mock_db)

        assert result["status"] == "ok"
        assert result["moved_cards"] == [1, 2, 3]
        assert result["action_id"] == 55

    @pytest.mark.asyncio
    @patch("app.routes.delay.build_complete_game_state", return_value={})
    @patch("app.routes.delay.crud.get_room_by_id", return_value=None)
    async def test_step2_room_not_found_raises_404(self, mock_room, mock_state, mock_db):
        payload = delay_escape_order_request(action_id=1, ordered_cards_ids=[1])
        with pytest.raises(HTTPException) as excinfo:
            await delay_murderer_order(room_id=99, payload=payload, user_id=7, db=mock_db)
        assert excinfo.value.status_code == 404
