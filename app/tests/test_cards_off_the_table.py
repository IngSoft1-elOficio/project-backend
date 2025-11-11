import pytest
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from fastapi import HTTPException
from datetime import datetime

from app.routes.cards_off_the_table import cards_off_the_table, TargetRequest
from app.db.models import CardState, TurnStatus, ActionType, ActionResult, ActionName, CardType


class TestCardsOffTheTable:
    """Tests para el endpoint cards_off_the_table"""
    
    @pytest.fixture
    def mock_db(self):
        """Mock de la sesión de base de datos"""
        db = Mock()
        db.add = Mock()
        db.commit = Mock()
        db.flush = Mock()
        db.rollback = Mock()
        
        # Mock para query() que retorna un objeto query mock
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
        actor.name = "Actor"
        actor.id_room = 1
        return actor
    
    @pytest.fixture
    def mock_target(self):
        """Mock del jugador objetivo"""
        target = Mock()
        target.id = 20
        target.name = "Target"
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
    def mock_cott_card(self):
        """Mock de la carta Cards off the table"""
        card = Mock()
        card.id = 100
        card.player_id = 10
        card.id_game = 1
        card.is_in = CardState.HAND
        card.position = 1
        card.hidden = True
        card.card = Mock()
        card.card.name = "Cards off the table"
        card.card.type = Mock()
        card.card.type.value = "EVENT"
        return card
    
    @pytest.fixture
    def mock_nsf_cards(self):
        """Mock de cartas Not so fast del objetivo"""
        cards = []
        for i in range(2):
            card = Mock()
            card.id = 200 + i
            card.player_id = 20
            card.id_game = 1
            card.is_in = CardState.HAND
            card.position = i + 1
            card.hidden = True
            card.card = Mock()
            card.card.name = "Not so fast"
            card.card.type = Mock()
            card.card.type.value = "INSTANT"
            cards.append(card)
        return cards
    
    @pytest.fixture
    def mock_target_remaining_cards(self):
        """Mock de cartas restantes del objetivo después del descarte"""
        card = Mock()
        card.id = 300
        card.player_id = 20
        card.id_game = 1
        card.is_in = CardState.HAND
        card.position = 3
        card.hidden = True
        card.card = Mock()
        card.card.name = "Normal Card"
        card.card.type = Mock()
        card.card.type.value = "ACTION"
        return [card]
    
    def setup_db_queries(self, mock_db, actor, target, turn, cott_card, nsf_cards, 
                         max_discard_pos, remaining_cards, top_discard, discard_count, deck_count):
        """Configura todos los queries del db en orden"""
        
        # Query 1: Actor player
        mock_actor_query = Mock()
        mock_actor_query.filter.return_value.first.return_value = actor
        
        # Query 2: Target player
        mock_target_query = Mock()
        mock_target_query.filter.return_value.first.return_value = target
        
        # Query 3: Turn
        mock_turn_query = Mock()
        mock_turn_query.filter.return_value.first.return_value = turn
        
        # Query 4: COTT card
        mock_cott_query = Mock()
        mock_cott_query.join.return_value.filter.return_value.first.return_value = cott_card
        
        # Query 5: NSF cards
        mock_nsf_query = Mock()
        mock_nsf_query.join.return_value.filter.return_value.all.return_value = nsf_cards
        
        # Query 6: Max discard position
        mock_discard_pos_query = Mock()
        mock_discard_pos_query.filter.return_value.order_by.return_value.first.return_value = max_discard_pos
        
        # Query 7: Target remaining cards
        mock_remaining_query = Mock()
        mock_remaining_query.filter.return_value.all.return_value = remaining_cards
        
        # Query 8: Top discard
        mock_top_discard_query = Mock()
        mock_top_discard_query.filter.return_value.order_by.return_value.first.return_value = top_discard
        
        # Query 9: Discard count
        mock_discard_count_query = Mock()
        mock_discard_count_query.filter.return_value.count.return_value = discard_count
        
        # Query 10: Deck count
        mock_deck_count_query = Mock()
        mock_deck_count_query.filter.return_value.count.return_value = deck_count
        
        # Configurar side_effect para db.query()
        query_responses = [
            mock_actor_query,           # Player (actor)
            mock_target_query,          # Player (target)
            mock_turn_query,            # Turn
            mock_cott_query,            # CardsXGame (COTT)
            mock_nsf_query,             # CardsXGame (NSF)
            mock_discard_pos_query,     # CardsXGame.position (max discard)
            mock_remaining_query,       # CardsXGame (remaining)
            mock_top_discard_query,     # CardsXGame (top discard)
            mock_discard_count_query,   # CardsXGame (discard count)
            mock_deck_count_query       # CardsXGame (deck count)
        ]
        
        mock_db.query.side_effect = query_responses
    
    @pytest.mark.asyncio
    async def test_cards_off_the_table_success(
        self, mock_db, mock_room, mock_game, mock_actor, 
        mock_target, mock_turn, mock_cott_card, mock_nsf_cards,
        mock_target_remaining_cards
    ):
        """Test de caso exitoso: descarte de todas las cartas NSF"""
        
        # Configurar queries
        self.setup_db_queries(
            mock_db, 
            mock_actor, 
            mock_target, 
            mock_turn, 
            mock_cott_card, 
            mock_nsf_cards, 
            (5,),  # max_discard_position
            mock_target_remaining_cards, 
            mock_cott_card,  # top_discard
            3,  # discard_count
            10  # deck_count
        )
        
        # Mock websocket service
        mock_ws = AsyncMock()
        mock_ws.notificar_estado_partida = AsyncMock()
        
        with patch('app.routes.cards_off_the_table.get_websocket_service', return_value=mock_ws), \
             patch('app.routes.cards_off_the_table.build_complete_game_state', return_value={
                 "game_id": 1,
                 "status": "INGAME"
             }), \
             patch('app.routes.cards_off_the_table.get_room_by_id', return_value=mock_room), \
             patch('app.routes.cards_off_the_table.get_game_by_id', return_value=mock_game):
            
            request = TargetRequest(targetPlayerId=20)
            
            response = await cards_off_the_table(
                room_id=1,
                request=request,
                actor_user_id=10,
                db=mock_db
            )
            
            # Verificaciones de la respuesta
            assert response.success is True
            assert response.eventCardDiscarded.name == "Cards off the table"
            assert len(response.discardedNSFCards) == 2
            assert all(card.name == "Not so fast" for card in response.discardedNSFCards)
            assert response.targetPlayerHand.player_id == 20
            assert len(response.targetPlayerHand.discardedPositions) == 2
            assert len(response.targetPlayerHand.remainingCards) == 1
            assert response.discard.count == 3
            assert response.deck.remaining == 10
            
            # Verificar que se llamó a commit
            mock_db.commit.assert_called_once()
            
            # Verificar que se crearon las acciones correctas
            assert mock_db.add.call_count >= 3
            
            # Verificar que la carta COTT fue descartada
            assert mock_cott_card.is_in == CardState.DISCARD
            assert mock_cott_card.position == 6
            assert mock_cott_card.hidden is False
            assert mock_cott_card.player_id is None
            
            # Verificar que las NSF fueron descartadas
            for i, card in enumerate(mock_nsf_cards):
                assert card.is_in == CardState.DISCARD
                assert card.player_id is None
                assert card.position == 7 + i
                assert card.hidden is False
            
            # Verificar notificaciones WebSocket
            mock_ws.notificar_estado_partida.assert_called_once()
            call_args = mock_ws.notificar_estado_partida.call_args
            assert call_args.kwargs['room_id'] == 1
            assert call_args.kwargs['jugador_que_actuo'] == 10
    
    @pytest.mark.asyncio
    async def test_cards_off_the_table_no_nsf_cards(
        self, mock_db, mock_room, mock_game, mock_actor, 
        mock_target, mock_turn, mock_cott_card, mock_target_remaining_cards
    ):
        """Test cuando el objetivo no tiene cartas NSF"""
        
        # Configurar queries (sin NSF cards)
        self.setup_db_queries(
            mock_db,
            mock_actor,
            mock_target,
            mock_turn,
            mock_cott_card,
            [],  # No NSF cards
            (5,),
            mock_target_remaining_cards,
            mock_cott_card,
            1,  # discard_count
            10
        )
        
        mock_ws = AsyncMock()
        
        with patch('app.routes.cards_off_the_table.get_websocket_service', return_value=mock_ws), \
             patch('app.routes.cards_off_the_table.build_complete_game_state', return_value={}), \
             patch('app.routes.cards_off_the_table.get_room_by_id', return_value=mock_room), \
             patch('app.routes.cards_off_the_table.get_game_by_id', return_value=mock_game):
            
            request = TargetRequest(targetPlayerId=20)
            
            response = await cards_off_the_table(
                room_id=1,
                request=request,
                actor_user_id=10,
                db=mock_db
            )
            
            assert response.success is True
            assert len(response.discardedNSFCards) == 0
            assert response.discard.count == 1
    
    @pytest.mark.asyncio
    async def test_room_not_found(self, mock_db):
        """Test cuando no se encuentra la sala"""
        
        with patch('app.routes.cards_off_the_table.get_room_by_id', return_value=None):
            request = TargetRequest(targetPlayerId=20)
            
            with pytest.raises(HTTPException) as exc_info:
                await cards_off_the_table(
                    room_id=999,
                    request=request,
                    actor_user_id=10,
                    db=mock_db
                )
            
            assert exc_info.value.status_code == 404
            assert "Room not found" in exc_info.value.detail
    
    @pytest.mark.asyncio
    async def test_game_not_found(self, mock_db, mock_room):
        """Test cuando no se encuentra el juego"""
        
        with patch('app.routes.cards_off_the_table.get_room_by_id', return_value=mock_room), \
             patch('app.routes.cards_off_the_table.get_game_by_id', return_value=None):
            
            request = TargetRequest(targetPlayerId=20)
            
            with pytest.raises(HTTPException) as exc_info:
                await cards_off_the_table(
                    room_id=1,
                    request=request,
                    actor_user_id=10,
                    db=mock_db
                )
            
            assert exc_info.value.status_code == 404
            assert "Game not found" in exc_info.value.detail
    
    @pytest.mark.asyncio
    async def test_not_player_turn(self, mock_db, mock_room, mock_game):
        """Test cuando no es el turno del jugador"""
        mock_game.player_turn_id = 999  # Different player
        
        with patch('app.routes.cards_off_the_table.get_room_by_id', return_value=mock_room), \
             patch('app.routes.cards_off_the_table.get_game_by_id', return_value=mock_game):
            
            request = TargetRequest(targetPlayerId=20)
            
            with pytest.raises(HTTPException) as exc_info:
                await cards_off_the_table(
                    room_id=1,
                    request=request,
                    actor_user_id=10,
                    db=mock_db
                )
            
            assert exc_info.value.status_code == 403
            assert "Not your turn" in exc_info.value.detail
    
    @pytest.mark.asyncio
    async def test_actor_not_found(self, mock_db, mock_room, mock_game):
        """Test cuando no se encuentra el actor"""
        
        # Mock query que retorna None para el actor
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query
        
        with patch('app.routes.cards_off_the_table.get_room_by_id', return_value=mock_room), \
             patch('app.routes.cards_off_the_table.get_game_by_id', return_value=mock_game):
            
            request = TargetRequest(targetPlayerId=20)
            
            with pytest.raises(HTTPException) as exc_info:
                await cards_off_the_table(
                    room_id=1,
                    request=request,
                    actor_user_id=10,
                    db=mock_db
                )
            
            assert exc_info.value.status_code == 404
            assert "Actor player not found" in exc_info.value.detail
    
    @pytest.mark.asyncio
    async def test_target_not_found(self, mock_db, mock_room, mock_game, mock_actor):
        """Test cuando no se encuentra el jugador objetivo"""
        
        # Primera query retorna actor, segunda retorna None (target)
        mock_actor_query = Mock()
        mock_actor_query.filter.return_value.first.return_value = mock_actor
        
        mock_target_query = Mock()
        mock_target_query.filter.return_value.first.return_value = None
        
        mock_db.query.side_effect = [mock_actor_query, mock_target_query]
        
        with patch('app.routes.cards_off_the_table.get_room_by_id', return_value=mock_room), \
             patch('app.routes.cards_off_the_table.get_game_by_id', return_value=mock_game):
            
            request = TargetRequest(targetPlayerId=20)
            
            with pytest.raises(HTTPException) as exc_info:
                await cards_off_the_table(
                    room_id=1,
                    request=request,
                    actor_user_id=10,
                    db=mock_db
                )
            
            assert exc_info.value.status_code == 400
            assert "Invalid target player" in exc_info.value.detail
    
    @pytest.mark.asyncio
    async def test_no_active_turn(self, mock_db, mock_room, mock_game, mock_actor, mock_target):
        """Test cuando no hay turno activo"""
        
        mock_actor_query = Mock()
        mock_actor_query.filter.return_value.first.return_value = mock_actor
        
        mock_target_query = Mock()
        mock_target_query.filter.return_value.first.return_value = mock_target
        
        mock_turn_query = Mock()
        mock_turn_query.filter.return_value.first.return_value = None
        
        mock_db.query.side_effect = [mock_actor_query, mock_target_query, mock_turn_query]
        
        with patch('app.routes.cards_off_the_table.get_room_by_id', return_value=mock_room), \
             patch('app.routes.cards_off_the_table.get_game_by_id', return_value=mock_game):
            
            request = TargetRequest(targetPlayerId=20)
            
            with pytest.raises(HTTPException) as exc_info:
                await cards_off_the_table(
                    room_id=1,
                    request=request,
                    actor_user_id=10,
                    db=mock_db
                )
            
            assert exc_info.value.status_code == 403
            assert "No active turn found" in exc_info.value.detail
    
    @pytest.mark.asyncio
    async def test_cott_card_not_found(
        self, mock_db, mock_room, mock_game, mock_actor, mock_target, mock_turn
    ):
        """Test cuando el jugador no tiene la carta Cards off the table"""
        
        mock_actor_query = Mock()
        mock_actor_query.filter.return_value.first.return_value = mock_actor
        
        mock_target_query = Mock()
        mock_target_query.filter.return_value.first.return_value = mock_target
        
        mock_turn_query = Mock()
        mock_turn_query.filter.return_value.first.return_value = mock_turn
        
        mock_cott_query = Mock()
        mock_cott_query.join.return_value.filter.return_value.first.return_value = None
        
        mock_db.query.side_effect = [mock_actor_query, mock_target_query, mock_turn_query, mock_cott_query]
        
        with patch('app.routes.cards_off_the_table.get_room_by_id', return_value=mock_room), \
             patch('app.routes.cards_off_the_table.get_game_by_id', return_value=mock_game):
            
            request = TargetRequest(targetPlayerId=20)
            
            with pytest.raises(HTTPException) as exc_info:
                await cards_off_the_table(
                    room_id=1,
                    request=request,
                    actor_user_id=10,
                    db=mock_db
                )
            
            assert exc_info.value.status_code == 404
            assert "Cards Off the Table card not found in hand" in exc_info.value.detail
    
    @pytest.mark.asyncio
    async def test_database_error_rollback(
        self, mock_db, mock_room, mock_game, mock_actor, 
        mock_target, mock_turn, mock_cott_card, mock_nsf_cards
    ):
        """Test que se hace rollback en caso de error"""
        
        self.setup_db_queries(
            mock_db,
            mock_actor,
            mock_target,
            mock_turn,
            mock_cott_card,
            mock_nsf_cards,
            (5,),
            [],
            mock_cott_card,
            3,
            10
        )
        
        mock_db.commit.side_effect = Exception("Database error")
        
        with patch('app.routes.cards_off_the_table.get_room_by_id', return_value=mock_room), \
             patch('app.routes.cards_off_the_table.get_game_by_id', return_value=mock_game):
            
            request = TargetRequest(targetPlayerId=20)
            
            with pytest.raises(HTTPException) as exc_info:
                await cards_off_the_table(
                    room_id=1,
                    request=request,
                    actor_user_id=10,
                    db=mock_db
                )
            
            assert exc_info.value.status_code == 500
            mock_db.rollback.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_first_discard_in_game(
        self, mock_db, mock_room, mock_game, mock_actor, 
        mock_target, mock_turn, mock_cott_card, mock_nsf_cards,
        mock_target_remaining_cards
    ):
        """Test cuando es el primer descarte del juego (discard vacío)"""
        
        self.setup_db_queries(
            mock_db,
            mock_actor,
            mock_target,
            mock_turn,
            mock_cott_card,
            mock_nsf_cards,
            None,  # No hay max_discard_position
            mock_target_remaining_cards,
            mock_cott_card,
            3,
            10
        )
        
        mock_ws = AsyncMock()
        
        with patch('app.routes.cards_off_the_table.get_websocket_service', return_value=mock_ws), \
             patch('app.routes.cards_off_the_table.build_complete_game_state', return_value={}), \
             patch('app.routes.cards_off_the_table.get_room_by_id', return_value=mock_room), \
             patch('app.routes.cards_off_the_table.get_game_by_id', return_value=mock_game):
            
            request = TargetRequest(targetPlayerId=20)
            
            response = await cards_off_the_table(
                room_id=1,
                request=request,
                actor_user_id=10,
                db=mock_db
            )
            
            # Verificar que el descarte empieza en posición 1
            assert response.success is True
            assert mock_cott_card.position == 1
            
            # Verificar posiciones de las NSF
            for i, card in enumerate(mock_nsf_cards):
                assert card.position == 2 + i