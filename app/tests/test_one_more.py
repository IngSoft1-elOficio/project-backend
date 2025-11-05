import pytest
from unittest.mock import Mock, patch, AsyncMock
from fastapi import HTTPException
from datetime import datetime

from app.routes.one_more import (
    one_more_step_1,
    one_more_step_2,
    one_more_step_3
)
from app.db.models import CardState


# =======================================================
# STEP 1
# =======================================================
class TestOneMoreStep1:
    """Tests para el endpoint One-More Step 1"""

    @pytest.fixture
    def mock_db(self):
        db = Mock()
        db.add = Mock()
        db.commit = Mock()
        db.flush = Mock()
        db.rollback = Mock()
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
        game.player_turn_id = 10
        return game

    @pytest.fixture
    def mock_event_card(self):
        card = Mock()
        card.id = 100
        card.player_id = 10
        card.id_game = 1
        card.is_in = CardState.HAND
        card.card = Mock()
        card.card.type = "EVENT"
        return card

    @pytest.mark.asyncio
    async def test_step1_success(self, mock_db, mock_room, mock_game, mock_event_card):
        """Debe devolver action_id y lista de secretos vacía"""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_event_card
        mock_db.query.return_value.filter.return_value.all.return_value = []

        with patch("app.routes.one_more.crud.get_room_by_id", return_value=mock_room), \
             patch("app.routes.one_more.crud.get_game_by_id", return_value=mock_game), \
             patch("app.routes.one_more.crud.get_current_turn", return_value=Mock(id=1)), \
             patch("app.routes.one_more.crud.create_action", return_value=Mock(id=999)), \
             patch("app.routes.one_more.crud.get_max_position_by_state", return_value=0), \
             patch("app.routes.one_more.get_websocket_service", return_value=AsyncMock()), \
             patch("app.routes.one_more.build_complete_game_state", return_value={}):
            
            payload = Mock(card_id=100)
            response = await one_more_step_1(room_id=1, payload=payload, user_id=10, db=mock_db)

            assert "action_id" in response
            assert "available_secrets" in response
            assert isinstance(response["available_secrets"], list)
            mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_step1_room_not_found(self, mock_db):
        with patch("app.routes.one_more.crud.get_room_by_id", return_value=None):
            payload = Mock(card_id=1)
            with pytest.raises(HTTPException) as exc:
                await one_more_step_1(room_id=99, payload=payload, user_id=10, db=mock_db)
            assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_step1_not_your_turn(self, mock_db, mock_room, mock_game):
        mock_game.player_turn_id = 99
        with patch("app.routes.one_more.crud.get_room_by_id", return_value=mock_room), \
             patch("app.routes.one_more.crud.get_game_by_id", return_value=mock_game):
            payload = Mock(card_id=1)
            with pytest.raises(HTTPException) as exc:
                await one_more_step_1(room_id=1, payload=payload, user_id=10, db=mock_db)
            assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_step1_invalid_card_type(self, mock_db, mock_room, mock_game):
        fake_card = Mock()
        fake_card.card = Mock()
        fake_card.card.type = "SECRET"
        mock_db.query.return_value.filter.return_value.first.return_value = fake_card

        with patch("app.routes.one_more.crud.get_room_by_id", return_value=mock_room), \
             patch("app.routes.one_more.crud.get_game_by_id", return_value=mock_game):
            payload = Mock(card_id=100)
            with pytest.raises(HTTPException) as exc:
                await one_more_step_1(room_id=1, payload=payload, user_id=10, db=mock_db)
            assert exc.value.status_code == 400


# =======================================================
# STEP 2
# =======================================================
class TestOneMoreStep2:
    """Tests para el endpoint One-More Step 2"""

    @pytest.fixture
    def mock_db(self):
        db = Mock()
        db.add = Mock()
        db.commit = Mock()
        db.rollback = Mock()
        return db

    @pytest.fixture
    def mock_room(self):
        r = Mock()
        r.id = 1
        r.id_game = 1
        return r

    @pytest.fixture
    def mock_game(self):
        g = Mock()
        g.id = 1
        g.player_turn_id = 10
        return g

    @pytest.fixture
    def mock_secret_card(self):
        c = Mock()
        c.id = 5
        c.player_id = 2
        c.hidden = False
        c.card = Mock()
        c.card.name = "Secret"
        return c

    @pytest.mark.asyncio
    async def test_step2_success(self, mock_db, mock_room, mock_game, mock_secret_card):
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            Mock(player_id=10),  # acción
            mock_secret_card     # secreto
        ]
        mock_player = Mock()
        mock_player.id = 1
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_player]

        with patch("app.routes.one_more.crud.get_room_by_id", return_value=mock_room), \
             patch("app.routes.one_more.crud.get_game_by_id", return_value=mock_game), \
             patch("app.routes.one_more.get_websocket_service", return_value=AsyncMock()):
            
            payload = Mock(action_id=1, selected_secret_id=5)
            response = await one_more_step_2(room_id=1, payload=payload, user_id=10, db=mock_db)
            assert hasattr(response, "allowed_players")
            assert response.allowed_players == [1]

    @pytest.mark.asyncio
    async def test_step2_secret_not_found(self, mock_db, mock_room, mock_game):
        with patch("app.routes.one_more.crud.get_room_by_id", return_value=mock_room), \
             patch("app.routes.one_more.crud.get_game_by_id", return_value=mock_game):
            payload = Mock(action_id=1, selected_secret_id=5)
            mock_db.query.return_value.filter.return_value.first.side_effect = [
                Mock(player_id=10),  # acción
                None                 # secreto no encontrado
            ]
            with pytest.raises(HTTPException):
                await one_more_step_2(room_id=1, payload=payload, user_id=10, db=mock_db)


# =======================================================
# STEP 3
# =======================================================
class TestOneMoreStep3:
    """Tests para el endpoint One-More Step 3"""

    @pytest.fixture
    def mock_db(self):
        db = Mock()
        db.add = Mock()
        db.commit = Mock()
        db.rollback = Mock()
        return db

    @pytest.fixture
    def mock_room(self):
        r = Mock()
        r.id = 1
        r.id_game = 1
        return r

    @pytest.fixture
    def mock_game(self):
        g = Mock()
        g.id = 1
        g.player_turn_id = 10
        return g

    @pytest.fixture
    def mock_action(self):
        a = Mock()
        a.id = 1
        a.secret_target = 99
        a.player_id = 10
        return a

    @pytest.fixture
    def mock_secret_card(self):
        s = Mock()
        s.id = 99
        s.player_id = 2
        s.hidden = False
        return s

    @pytest.mark.asyncio
    async def test_step3_success(self, mock_db, mock_room, mock_game, mock_action, mock_secret_card):
        with patch("app.routes.one_more.crud.get_room_by_id", return_value=mock_room), \
             patch("app.routes.one_more.crud.get_game_by_id", return_value=mock_game), \
             patch("app.routes.one_more.crud.transfer_secret_card", return_value=mock_secret_card), \
             patch("app.routes.one_more.crud.get_max_position_for_player_secrets", return_value=1), \
             patch("app.routes.one_more.build_complete_game_state", return_value={"estados_privados": {10: {}, 3: {}}}), \
             patch("app.routes.one_more.get_websocket_service", return_value=AsyncMock()):
            
            payload = Mock(action_id=1, target_player_id=3)
            mock_db.query.return_value.filter.return_value.first.side_effect = [
                mock_action,                 # parent_action
                Mock(secret_target=99),      # sub_action
                mock_secret_card             # secret
            ]

            response = await one_more_step_3(room_id=1, payload=payload, user_id=10, db=mock_db)
            assert response.success is True

    @pytest.mark.asyncio
    async def test_step3_secret_not_found(self, mock_db, mock_room, mock_game, mock_action):
        with patch("app.routes.one_more.crud.get_room_by_id", return_value=mock_room), \
             patch("app.routes.one_more.crud.get_game_by_id", return_value=mock_game):
            payload = Mock(action_id=1, target_player_id=3)
            mock_db.query.return_value.filter.return_value.first.side_effect = [mock_action, None]
            with pytest.raises(HTTPException):
                await one_more_step_3(room_id=1, payload=payload, user_id=10, db=mock_db)
