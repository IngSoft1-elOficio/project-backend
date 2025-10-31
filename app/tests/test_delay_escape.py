import pytest
from unittest.mock import Mock, patch, AsyncMock
from fastapi import HTTPException
from app.routes.event import delay_murderer_step_1, delay_murderer_order
from app.schemas.event_schema import (
    delay_escape_start_request,
    delay_escape_order_request,
)


@pytest.mark.asyncio
class TestDelayMurdererEscapeMocked:
    """Tests mockeados para Delay The Murderer’s Escape"""

    @pytest.fixture
    def mock_db(self):
        """Mock de la sesión de base de datos"""
        db = Mock()
        db.add = Mock()
        db.commit = Mock()
        db.rollback = Mock()
        db.query = Mock()
        return db

    @pytest.fixture
    def mock_room(self):
        room = Mock()
        room.id = 1
        room.id_game = 10
        room.status = "INGAME"
        return room

    @pytest.fixture
    def mock_game(self):
        game = Mock()
        game.id = 10
        game.player_turn_id = 99
        return game

    # ============================================================
    # STEP 1 - delay-murderer-escape
    # ============================================================

    @patch("app.routes.event.get_websocket_service")
    @patch("app.routes.event.crud.count_cards_by_state")
    @patch("app.routes.event.crud.create_action")
    @patch("app.routes.event.crud.get_current_turn")
    @patch("app.routes.event.crud.get_game_by_id")
    @patch("app.routes.event.crud.get_room_by_id")
    async def test_step1_returns_available_cards_ok(
        self,
        mock_get_room,
        mock_get_game,
        mock_get_turn,
        mock_create_action,
        mock_count_cards,
        mock_ws_service,
        mock_db,
        mock_room,
        mock_game,
    ):
        """Debe devolver lista de cartas disponibles del descarte"""
        from app.db import models  # ✅ import correcto

        # --- setup mocks
        mock_get_room.return_value = mock_room
        mock_get_game.return_value = mock_game
        mock_get_turn.return_value = Mock(id=55)
        mock_create_action.return_value = Mock(id=888)
        mock_count_cards.return_value = 3

        # Carta en mano simulada (validación de tipo EVENT)
        event_card = Mock()
        event_card.id = 123
        event_card.card = Mock()
        event_card.card.type = models.CardType.EVENT
        mock_db.query.return_value.filter.return_value.first.return_value = event_card

        # Simular cartas del descarte devueltas por query
        fake_card = Mock()
        fake_card.id = 1
        fake_card.card = Mock()
        fake_card.card.type = models.CardType.EVENT
        (
            mock_db.query.return_value.join.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value
        ) = [fake_card]

        # Mock del websocket
        ws_instance = AsyncMock()
        mock_ws_service.return_value = ws_instance

        payload = delay_escape_start_request(card_id=123, quantity=1)
        result = await delay_murderer_step_1(
            room_id=1, payload=payload, user_id=99, db=mock_db
        )

        assert "action_id" in result
        assert "available_cards" in result
        assert result["available_cards"] == [1]
        ws_instance.notificar_event_action_started.assert_awaited_once()
        mock_create_action.assert_called_once()
        mock_db.commit.assert_called_once()

    @patch("app.routes.event.crud.get_room_by_id")
    async def test_step1_room_not_found_raises_404(self, mock_get_room, mock_db):
        """Debe lanzar 404 si la sala no existe"""
        mock_get_room.return_value = None
        payload = delay_escape_start_request(card_id=1, quantity=1)
        with pytest.raises(HTTPException) as exc:
            await delay_murderer_step_1(1, payload, user_id=99, db=mock_db)
        assert exc.value.status_code == 404

    @patch("app.routes.event.crud.get_room_by_id")
    @patch("app.routes.event.crud.get_game_by_id")
    async def test_step1_not_your_turn_raises_403(
        self, mock_get_game, mock_get_room, mock_db, mock_room, mock_game
    ):
        """Debe lanzar 403 si no es tu turno"""
        mock_get_room.return_value = mock_room
        mock_game.player_turn_id = 10  # otro jugador
        mock_get_game.return_value = mock_game
        payload = delay_escape_start_request(card_id=1, quantity=1)

        with pytest.raises(HTTPException) as exc:
            await delay_murderer_step_1(1, payload, user_id=99, db=mock_db)
        assert exc.value.status_code == 403

    # ============================================================
    # STEP 2 - delay-murderer-escape/order
    # ============================================================

    @patch("app.routes.event.get_websocket_service")
    @patch("app.routes.event.crud.create_action")
    @patch("app.routes.event.crud.get_action_by_id")
    @patch("app.routes.event.crud.get_top_card_by_state")
    @patch("app.routes.event.crud.get_game_by_id")
    @patch("app.routes.event.crud.get_room_by_id")
    async def test_step2_moves_cards_ok(
        self,
        mock_get_room,
        mock_get_game,
        mock_get_top_card,
        mock_get_action,
        mock_create_action,
        mock_ws_service,
        mock_db,
        mock_room,
        mock_game,
    ):
        """Debe mover cartas del descarte al mazo (mockeado)"""
        mock_get_room.return_value = mock_room
        mock_get_game.return_value = mock_game
        mock_get_top_card.return_value = Mock(position=10)
        mock_get_action.return_value = Mock(id=77, turn_id=3)
        mock_create_action.return_value = Mock(id=999)
        ws_instance = AsyncMock()
        mock_ws_service.return_value = ws_instance

        # Simulamos que el query encuentra una carta
        fake_card = Mock()
        fake_card.id = 1
        fake_query = Mock()
        fake_query.filter.return_value.first.return_value = fake_card
        mock_db.query.return_value = fake_query

        payload = delay_escape_order_request(action_id=77, ordered_cards_ids=[1, 2, 3])

        result = await delay_murderer_order(
            room_id=1, payload=payload, user_id=99, db=mock_db
        )

        assert result["status"] == "ok"
        assert result["moved_cards"] == [1, 2, 3]
        ws_instance.notificar_event_action_complete.assert_awaited_once()
        mock_create_action.assert_called_once()
        mock_db.commit.assert_called_once()

    @patch("app.routes.event.crud.get_room_by_id")
    async def test_step2_room_not_found_raises_404(self, mock_get_room, mock_db):
        """Debe lanzar 404 si la room no existe"""
        mock_get_room.return_value = None
        payload = delay_escape_order_request(action_id=1, ordered_cards_ids=[1])
        with pytest.raises(HTTPException) as exc:
            await delay_murderer_order(1, payload, user_id=1, db=mock_db)
        assert exc.value.status_code == 404
