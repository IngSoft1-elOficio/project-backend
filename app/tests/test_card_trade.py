import pytest
from unittest.mock import Mock, patch, AsyncMock
from fastapi import HTTPException
from datetime import datetime, date

from app.routes.card_trade import (
    card_trade_play, 
    card_trade_complete,
    CardTradePlayRequest,
    CardTradeCompleteRequest
)
from app.db.models import (
    CardState, TurnStatus, ActionType, ActionResult, 
    ActionName, CardType
)


class TestCardTradePlay:
    """Tests para el endpoint card_trade_play"""
    
    @pytest.fixture
    def mock_db(self):
        """Mock de la sesión de base de datos"""
        db = Mock()
        db.add = Mock()
        db.commit = Mock()
        db.flush = Mock()
        db.rollback = Mock()
        db.query = Mock()
        return db
    
    @pytest.fixture
    def mock_room(self):
        """Mock de una sala"""
        room = Mock()
        room.id = 1
        room.id_game = 1
        return room
    
    @pytest.fixture
    def mock_game(self):
        """Mock de un juego"""
        game = Mock()
        game.id = 1
        game.player_turn_id = 10
        return game
    
    @pytest.fixture
    def mock_actor(self):
        """Mock del jugador que realiza la acción"""
        actor = Mock()
        actor.id = 10
        actor.name = "Player 1"
        actor.id_room = 1
        return actor
    
    @pytest.fixture
    def mock_target(self):
        """Mock del jugador objetivo"""
        target = Mock()
        target.id = 20
        target.name = "Player 2"
        target.id_room = 1
        return target
    
    @pytest.fixture
    def mock_turn(self):
        """Mock de un turno activo"""
        turn = Mock()
        turn.id = 1
        turn.id_game = 1
        turn.player_id = 10
        turn.status = TurnStatus.IN_PROGRESS
        return turn
    
    @pytest.fixture
    def mock_p1_card(self):
        """Mock de la carta del jugador 1"""
        card = Mock()
        card.id = 100
        card.player_id = 10
        card.id_game = 1
        card.is_in = CardState.HAND
        card.card = Mock()
        card.card.name = "Test Card 1"
        card.card.type = Mock()
        card.card.type.value = "EVENT"
        return card
    
    @pytest.fixture
    def mock_p2_card(self):
        """Mock de la carta del jugador 2"""
        card = Mock()
        card.id = 200
        card.player_id = 20
        card.id_game = 1
        card.is_in = CardState.HAND
        card.card = Mock()
        card.card.name = "Test Card 2"
        card.card.type = Mock()
        card.card.type.value = "SECRET"
        return card
    
    def setup_db_queries_play(self, mock_db, actor, target, turn, p1_card, target_has_cards=True):
        """Configura todos los queries del db para card_trade_play"""
        # Query 1: Actor player
        mock_actor_query = Mock()
        mock_actor_query.filter.return_value.first.return_value = actor
        
        # Query 2: Target player
        mock_target_query = Mock()
        mock_target_query.filter.return_value.first.return_value = target
        
        # Query 3: Turn
        mock_turn_query = Mock()
        mock_turn_query.filter.return_value.first.return_value = turn
        
        # Query 4: P1 card
        mock_p1_card_query = Mock()
        mock_p1_card_query.filter.return_value.first.return_value = p1_card
        
        # Query 5: Target has cards count
        mock_target_cards_query = Mock()
        mock_target_cards_query.filter.return_value.count.return_value = 1 if target_has_cards else 0
        
        mock_db.query.side_effect = [
            mock_actor_query,
            mock_target_query,
            mock_turn_query,
            mock_p1_card_query,
            mock_target_cards_query
        ]
    

    @pytest.mark.asyncio
    async def test_card_trade_play_room_not_found(self, mock_db):
        """Test cuando no se encuentra la sala"""
        with patch('app.routes.card_trade.get_room_by_id', return_value=None):
            request = CardTradePlayRequest(own_card_id=100, target_player_id=20)
            
            with pytest.raises(HTTPException) as exc_info:
                await card_trade_play(
                    room_id=999,
                    request=request,
                    actor_user_id=10,
                    db=mock_db
                )
            
            assert exc_info.value.status_code == 404
            assert "Room not found" in exc_info.value.detail
    
    @pytest.mark.asyncio
    async def test_card_trade_play_game_not_found(self, mock_db, mock_room):
        """Test cuando no se encuentra el juego"""
        with patch('app.routes.card_trade.get_room_by_id', return_value=mock_room), \
             patch('app.routes.card_trade.get_game_by_id', return_value=None):
            
            request = CardTradePlayRequest(own_card_id=100, target_player_id=20)
            
            with pytest.raises(HTTPException) as exc_info:
                await card_trade_play(
                    room_id=1,
                    request=request,
                    actor_user_id=10,
                    db=mock_db
                )
            
            assert exc_info.value.status_code == 404
            assert "Game not found" in exc_info.value.detail
    
    @pytest.mark.asyncio
    async def test_card_trade_play_not_your_turn(self, mock_db, mock_room, mock_game):
        """Test cuando no es el turno del jugador"""
        mock_game.player_turn_id = 999
        
        with patch('app.routes.card_trade.get_room_by_id', return_value=mock_room), \
             patch('app.routes.card_trade.get_game_by_id', return_value=mock_game):
            
            request = CardTradePlayRequest(own_card_id=100, target_player_id=20)
            
            with pytest.raises(HTTPException) as exc_info:
                await card_trade_play(
                    room_id=1,
                    request=request,
                    actor_user_id=10,
                    db=mock_db
                )
            
            assert exc_info.value.status_code == 403
            assert "Not your turn" in exc_info.value.detail
    
    @pytest.mark.asyncio
    async def test_card_trade_play_actor_not_found(
        self, mock_db, mock_room, mock_game
    ):
        """Test cuando no se encuentra el actor"""
        mock_actor_query = Mock()
        mock_actor_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_actor_query
        
        with patch('app.routes.card_trade.get_room_by_id', return_value=mock_room), \
             patch('app.routes.card_trade.get_game_by_id', return_value=mock_game):
            
            request = CardTradePlayRequest(own_card_id=100, target_player_id=20)
            
            with pytest.raises(HTTPException) as exc_info:
                await card_trade_play(
                    room_id=1,
                    request=request,
                    actor_user_id=10,
                    db=mock_db
                )
            
            assert exc_info.value.status_code == 404
            assert "Actor not found" in exc_info.value.detail
    
    @pytest.mark.asyncio
    async def test_card_trade_play_target_not_found(
        self, mock_db, mock_room, mock_game, mock_actor
    ):
        """Test cuando no se encuentra el jugador objetivo"""
        mock_actor_query = Mock()
        mock_actor_query.filter.return_value.first.return_value = mock_actor
        
        mock_target_query = Mock()
        mock_target_query.filter.return_value.first.return_value = None
        
        mock_db.query.side_effect = [mock_actor_query, mock_target_query]
        
        with patch('app.routes.card_trade.get_room_by_id', return_value=mock_room), \
             patch('app.routes.card_trade.get_game_by_id', return_value=mock_game):
            
            request = CardTradePlayRequest(own_card_id=100, target_player_id=20)
            
            with pytest.raises(HTTPException) as exc_info:
                await card_trade_play(
                    room_id=1,
                    request=request,
                    actor_user_id=10,
                    db=mock_db
                )
            
            assert exc_info.value.status_code == 403
            assert "Target not found" in exc_info.value.detail
    
    @pytest.mark.asyncio
    async def test_card_trade_play_cannot_trade_yourself(
        self, mock_db, mock_room, mock_game, mock_actor
    ):
        """Test cuando intentas intercambiar contigo mismo"""
        mock_actor.id = 10
        
        mock_actor_query = Mock()
        mock_actor_query.filter.return_value.first.return_value = mock_actor
        
        mock_target_query = Mock()
        mock_target_query.filter.return_value.first.return_value = mock_actor
        
        mock_db.query.side_effect = [mock_actor_query, mock_target_query]
        
        with patch('app.routes.card_trade.get_room_by_id', return_value=mock_room), \
             patch('app.routes.card_trade.get_game_by_id', return_value=mock_game):
            
            request = CardTradePlayRequest(own_card_id=100, target_player_id=10)
            
            with pytest.raises(HTTPException) as exc_info:
                await card_trade_play(
                    room_id=1,
                    request=request,
                    actor_user_id=10,
                    db=mock_db
                )
            
            assert exc_info.value.status_code == 400
            assert "Cannot trade yourself" in exc_info.value.detail
    
    @pytest.mark.asyncio
    async def test_card_trade_play_no_active_turn(
        self, mock_db, mock_room, mock_game, mock_actor, mock_target
    ):
        """Test cuando no hay turno activo"""
        mock_actor_query = Mock()
        mock_actor_query.filter.return_value.first.return_value = mock_actor
        
        mock_target_query = Mock()
        mock_target_query.filter.return_value.first.return_value = mock_target
        
        mock_turn_query = Mock()
        mock_turn_query.filter.return_value.first.return_value = None
        
        mock_db.query.side_effect = [mock_actor_query, mock_target_query, mock_turn_query]
        
        with patch('app.routes.card_trade.get_room_by_id', return_value=mock_room), \
             patch('app.routes.card_trade.get_game_by_id', return_value=mock_game):
            
            request = CardTradePlayRequest(own_card_id=100, target_player_id=20)
            
            with pytest.raises(HTTPException) as exc_info:
                await card_trade_play(
                    room_id=1,
                    request=request,
                    actor_user_id=10,
                    db=mock_db
                )
            
            assert exc_info.value.status_code == 403
            assert "No active turn found" in exc_info.value.detail
    

    
    @pytest.mark.asyncio
    async def test_card_trade_play_database_error(
        self, mock_db, mock_room, mock_game, mock_actor, 
        mock_target, mock_turn, mock_p1_card
    ):
        """Test que se hace rollback en caso de error"""
        self.setup_db_queries_play(
            mock_db, mock_actor, mock_target, mock_turn, mock_p1_card
        )
        
        mock_db.commit.side_effect = Exception("Database error")
        
        mock_ws = AsyncMock()
        
        with patch('app.routes.card_trade.get_websocket_service', return_value=mock_ws), \
             patch('app.routes.card_trade.get_room_by_id', return_value=mock_room), \
             patch('app.routes.card_trade.get_game_by_id', return_value=mock_game):
            
            request = CardTradePlayRequest(own_card_id=100, target_player_id=20)
            
            with pytest.raises(HTTPException) as exc_info:
                await card_trade_play(
                    room_id=1,
                    request=request,
                    actor_user_id=10,
                    db=mock_db
                )
            
            assert exc_info.value.status_code == 500
            mock_db.rollback.assert_called_once()


class TestCardTradeComplete:
    """Tests para el endpoint card_trade_complete"""
    
    @pytest.fixture
    def mock_db(self):
        """Mock de la sesión de base de datos"""
        db = Mock()
        db.add = Mock()
        db.commit = Mock()
        db.flush = Mock()
        db.rollback = Mock()
        db.query = Mock()
        db.refresh = Mock()
        return db
    
    @pytest.fixture
    def mock_room(self):
        """Mock de una sala"""
        room = Mock()
        room.id = 1
        room.id_game = 1
        return room
    
    @pytest.fixture
    def mock_game(self):
        """Mock de un juego"""
        game = Mock()
        game.id = 1
        game.player_turn_id = 10
        return game
    
    @pytest.fixture
    def mock_p1(self):
        """Mock del jugador 1"""
        p1 = Mock()
        p1.id = 10
        p1.name = "Player 1"
        return p1
    
    @pytest.fixture
    def mock_p2(self):
        """Mock del jugador 2"""
        p2 = Mock()
        p2.id = 20
        p2.name = "Player 2"
        return p2
    
    @pytest.fixture
    def mock_action(self):
        """Mock de una acción pendiente"""
        action = Mock()
        action.id = 1
        action.id_game = 1
        action.action_type = ActionType.CARD_EXCHANGE
        action.action_name = ActionName.CARD_TRADE
        action.result = ActionResult.PENDING
        action.player_source = 10
        action.player_target = 20
        action.card_given_id = 100
        action.card_received_id = None
        action.action_time_end = None
        return action
    
    @pytest.fixture
    def mock_p1_card(self):
        """Mock de la carta del jugador 1"""
        card = Mock()
        card.id = 100
        card.player_id = 10
        card.id_game = 1
        card.is_in = CardState.HAND
        card.card = Mock()
        card.card.name = "Card 1"
        card.card.type = Mock()
        card.card.type.value = "EVENT"
        return card
    
    @pytest.fixture
    def mock_p2_card(self):
        """Mock de la carta del jugador 2"""
        card = Mock()
        card.id = 200
        card.player_id = 20
        card.id_game = 1
        card.is_in = CardState.HAND
        card.card = Mock()
        card.card.name = "Card 2"
        card.card.type = Mock()
        card.card.type.value = "SECRET"
        return card
    
    def setup_db_queries_complete(self, mock_db, action, p1, p2, p1_card, p2_card):
        """Configura todos los queries del db para card_trade_complete"""
        # Query 1: Action
        mock_action_query = Mock()
        mock_action_query.filter.return_value.first.return_value = action
        
        # Query 2: P1 (source)
        mock_p1_query = Mock()
        mock_p1_query.filter.return_value.first.return_value = p1
        
        # Query 3: P2 (target/actor)
        mock_p2_query = Mock()
        mock_p2_query.filter.return_value.first.return_value = p2
        
        # Query 4: P1 card
        mock_p1_card_query = Mock()
        mock_p1_card_query.filter.return_value.first.return_value = p1_card
        
        # Query 5: P2 card
        mock_p2_card_query = Mock()
        mock_p2_card_query.filter.return_value.first.return_value = p2_card
        
        mock_db.query.side_effect = [
            mock_action_query,
            mock_p1_query,
            mock_p2_query,
            mock_p1_card_query,
            mock_p2_card_query
        ]
    
    @pytest.mark.asyncio
    async def test_card_trade_complete_success(
        self, mock_db, mock_room, mock_game, mock_p1, mock_p2,
        mock_action, mock_p1_card, mock_p2_card
    ):
        """Test exitoso de completar intercambio de cartas"""
        self.setup_db_queries_complete(
            mock_db, mock_action, mock_p1, mock_p2, mock_p1_card, mock_p2_card
        )
        
        mock_ws = AsyncMock()
        mock_ws.notificar_card_trade_complete = AsyncMock()
        mock_ws.notificar_estado_partida = AsyncMock()
        
        with patch('app.routes.card_trade.get_websocket_service', return_value=mock_ws), \
             patch('app.routes.card_trade.build_complete_game_state', return_value={"test": "state"}), \
             patch('app.routes.card_trade.get_room_by_id', return_value=mock_room), \
             patch('app.routes.card_trade.get_game_by_id', return_value=mock_game):
            
            request = CardTradeCompleteRequest(
                action_id=1,
                own_card_id=200
            )
            
            response = await card_trade_complete(
                room_id=1,
                request=request,
                actor_user_id=20,
                db=mock_db
            )
            
            assert response.success is True
            assert response.player1_id == 10
            assert response.player2_id == 20
            assert response.card_exchanged_p1.cardId == 100
            assert response.card_exchanged_p1.playerId == 20
            assert response.card_exchanged_p2.cardId == 200
            assert response.card_exchanged_p2.playerId == 10
            
            # Verificar que las cartas se intercambiaron
            assert mock_p1_card.player_id == 20
            assert mock_p2_card.player_id == 10
            
            # Verificar que la acción se completó
            assert mock_action.card_received_id == 200
            assert mock_action.result == ActionResult.SUCCESS
            assert mock_action.action_time_end is not None
            
            mock_db.commit.assert_called_once()
            mock_ws.notificar_card_trade_complete.assert_called_once()
            mock_ws.notificar_estado_partida.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_card_trade_complete_room_not_found(self, mock_db):
        """Test cuando no se encuentra la sala"""
        with patch('app.routes.card_trade.get_room_by_id', return_value=None):
            request = CardTradeCompleteRequest(action_id=1, own_card_id=200)
            
            with pytest.raises(HTTPException) as exc_info:
                await card_trade_complete(
                    room_id=999,
                    request=request,
                    actor_user_id=20,
                    db=mock_db
                )
            
            assert exc_info.value.status_code == 404
            assert "Room not found" in exc_info.value.detail
    
    @pytest.mark.asyncio
    async def test_card_trade_complete_game_not_found(self, mock_db, mock_room):
        """Test cuando no se encuentra el juego"""
        with patch('app.routes.card_trade.get_room_by_id', return_value=mock_room), \
             patch('app.routes.card_trade.get_game_by_id', return_value=None):
            
            request = CardTradeCompleteRequest(action_id=1, own_card_id=200)
            
            with pytest.raises(HTTPException) as exc_info:
                await card_trade_complete(
                    room_id=1,
                    request=request,
                    actor_user_id=20,
                    db=mock_db
                )
            
            assert exc_info.value.status_code == 404
            assert "Game not found" in exc_info.value.detail
    
    @pytest.mark.asyncio
    async def test_card_trade_complete_action_not_found(
        self, mock_db, mock_room, mock_game
    ):
        """Test cuando la acción no existe"""
        mock_action_query = Mock()
        mock_action_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_action_query
        
        with patch('app.routes.card_trade.get_room_by_id', return_value=mock_room), \
             patch('app.routes.card_trade.get_game_by_id', return_value=mock_game):
            
            request = CardTradeCompleteRequest(action_id=999, own_card_id=200)
            
            with pytest.raises(HTTPException) as exc_info:
                await card_trade_complete(
                    room_id=1,
                    request=request,
                    actor_user_id=20,
                    db=mock_db
                )
            
            assert exc_info.value.status_code == 404
            assert "Card trade action not found" in exc_info.value.detail
    
    @pytest.mark.asyncio
    async def test_card_trade_complete_not_target(
        self, mock_db, mock_room, mock_game, mock_action
    ):
        """Test cuando el actor no es el objetivo del intercambio"""
        mock_action.player_target = 30  # Diferente al actor
        
        mock_action_query = Mock()
        mock_action_query.filter.return_value.first.return_value = mock_action
        mock_db.query.return_value = mock_action_query
        
        with patch('app.routes.card_trade.get_room_by_id', return_value=mock_room), \
             patch('app.routes.card_trade.get_game_by_id', return_value=mock_game):
            
            request = CardTradeCompleteRequest(action_id=1, own_card_id=200)
            
            with pytest.raises(HTTPException) as exc_info:
                await card_trade_complete(
                    room_id=1,
                    request=request,
                    actor_user_id=20,
                    db=mock_db
                )
            
            assert exc_info.value.status_code == 403
            assert "You are not the target" in exc_info.value.detail
    
    @pytest.mark.asyncio
    async def test_card_trade_complete_already_completed(
        self, mock_db, mock_room, mock_game, mock_action
    ):
        """Test cuando la acción ya fue completada"""
        mock_action.result = ActionResult.SUCCESS
        
        mock_action_query = Mock()
        mock_action_query.filter.return_value.first.return_value = None  # No encuentra porque no está PENDING
        mock_db.query.return_value = mock_action_query
        
        with patch('app.routes.card_trade.get_room_by_id', return_value=mock_room), \
             patch('app.routes.card_trade.get_game_by_id', return_value=mock_game):
            
            request = CardTradeCompleteRequest(action_id=1, own_card_id=200)
            
            with pytest.raises(HTTPException) as exc_info:
                await card_trade_complete(
                    room_id=1,
                    request=request,
                    actor_user_id=20,
                    db=mock_db
                )
            
            assert exc_info.value.status_code == 404
            assert "already completed" in exc_info.value.detail
    
    @pytest.mark.asyncio
    async def test_card_trade_complete_p1_card_not_available(
        self, mock_db, mock_room, mock_game, mock_action, 
        mock_p1, mock_p2, mock_p1_card
    ):
        """Test cuando la carta de P1 ya no está disponible"""
        mock_p1_card.is_in = CardState.DISCARD  # Ya no está en mano
        
        mock_action_query = Mock()
        mock_action_query.filter.return_value.first.return_value = mock_action
        
        mock_p1_query = Mock()
        mock_p1_query.filter.return_value.first.return_value = mock_p1
        
        mock_p2_query = Mock()
        mock_p2_query.filter.return_value.first.return_value = mock_p2
        
        mock_p1_card_query = Mock()
        mock_p1_card_query.filter.return_value.first.return_value = mock_p1_card
        
        mock_db.query.side_effect = [
            mock_action_query, mock_p1_query, mock_p2_query, mock_p1_card_query
        ]
        
        with patch('app.routes.card_trade.get_room_by_id', return_value=mock_room), \
             patch('app.routes.card_trade.get_game_by_id', return_value=mock_game):
            
            request = CardTradeCompleteRequest(action_id=1, own_card_id=200)
            
            with pytest.raises(HTTPException) as exc_info:
                await card_trade_complete(
                    room_id=1,
                    request=request,
                    actor_user_id=20,
                    db=mock_db
                )
            
            assert exc_info.value.status_code == 409
            assert "P1 card is no longer available" in exc_info.value.detail
    
    @pytest.mark.asyncio
    async def test_card_trade_complete_p2_card_not_in_hand(
        self, mock_db, mock_room, mock_game, mock_action, 
        mock_p1, mock_p2, mock_p1_card
    ):
        """Test cuando la carta de P2 no está en su mano"""
        mock_action_query = Mock()
        mock_action_query.filter.return_value.first.return_value = mock_action
        
        mock_p1_query = Mock()
        mock_p1_query.filter.return_value.first.return_value = mock_p1
        
        mock_p2_query = Mock()
        mock_p2_query.filter.return_value.first.return_value = mock_p2
        
        mock_p1_card_query = Mock()
        mock_p1_card_query.filter.return_value.first.return_value = mock_p1_card
        
        mock_p2_card_query = Mock()
        mock_p2_card_query.filter.return_value.first.return_value = None
        
        mock_db.query.side_effect = [
            mock_action_query, mock_p1_query, mock_p2_query, 
            mock_p1_card_query, mock_p2_card_query
        ]
        
        with patch('app.routes.card_trade.get_room_by_id', return_value=mock_room), \
             patch('app.routes.card_trade.get_game_by_id', return_value=mock_game):
            
            request = CardTradeCompleteRequest(action_id=1, own_card_id=200)
            
            with pytest.raises(HTTPException) as exc_info:
                await card_trade_complete(
                    room_id=1,
                    request=request,
                    actor_user_id=20,
                    db=mock_db
                )
            
            assert exc_info.value.status_code == 404
            assert "Card not found in your hand" in exc_info.value.detail
  