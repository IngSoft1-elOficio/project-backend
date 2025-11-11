import pytest
from unittest.mock import Mock, patch, AsyncMock
from fastapi import HTTPException

from app.routes.early_train_to_paddington import early_train_to_paddington, EarlyTrainRequest
from app.db.models import CardState, TurnStatus, CardType


class TestEarlyTrainToPaddington:
    """Tests para el endpoint early_train_to_paddington"""
    
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
        actor.name = "Actor"
        actor.id_room = 1
        return actor
    
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
    def mock_event_card(self):
        """Mock de la carta Early train to paddington"""
        card = Mock()
        card.id = 100
        card.id_card = 15
        card.player_id = 10
        card.id_game = 1
        card.is_in = CardState.HAND
        card.position = 1
        card.hidden = True
        card.card = Mock()
        card.card.name = "Early train to paddington"
        card.card.type = Mock()
        card.card.type.value = "EVENT"
        return card
    
    @pytest.fixture
    def mock_deck_cards(self):
        """Mock de 6 cartas en el deck"""
        cards = []
        for i in range(6):
            card = Mock()
            card.id = 200 + i
            card.id_game = 1
            card.is_in = CardState.DECK
            card.position = 10 - i  # Posiciones descendentes
            card.hidden = True
            card.player_id = None
            card.card = Mock()
            card.card.name = f"Deck Card {i}"
            card.card.type = Mock()
            card.card.type.value = "DETECTIVE"
            cards.append(card)
        return cards
    
    @pytest.fixture
    def mock_remaining_deck_cards(self):
        """Mock de cartas restantes en el deck después de mover 6"""
        cards = []
        for i in range(4):
            card = Mock()
            card.id = 300 + i
            card.is_in = CardState.DECK
            card.position = i + 1  # Será actualizado
            cards.append(card)
        return cards
    
    @pytest.fixture
    def mock_top_discard(self):
        """Mock del top del discard pile"""
        card = Mock()
        card.id = 400
        card.card = Mock()
        card.card.name = "Top Discard"
        card.card.type = Mock()
        card.card.type.value = "EVENT"
        return card
    
    def setup_db_queries(self, mock_db, actor, turn, event_card, deck_cards, 
                         max_discard_pos, remaining_deck_cards, top_discard, 
                         discard_count, deck_count):
        """Configura todos los queries del db en orden"""
        
        # Query 1: Actor player
        mock_actor_query = Mock()
        mock_actor_query.filter.return_value.first.return_value = actor
        
        # Query 2: Turn
        mock_turn_query = Mock()
        mock_turn_query.filter.return_value.first.return_value = turn
        
        # Query 3: Event card
        mock_event_query = Mock()
        mock_event_query.join.return_value.filter.return_value.first.return_value = event_card
        
        # Query 4: First 6 deck cards
        mock_deck_query = Mock()
        mock_deck_query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = deck_cards
        
        # Query 5: Max discard position
        mock_discard_pos_query = Mock()
        mock_discard_pos_query.filter.return_value.order_by.return_value.first.return_value = max_discard_pos
        
        # Query 6: Remaining deck cards
        mock_remaining_deck_query = Mock()
        mock_remaining_deck_query.filter.return_value.order_by.return_value.all.return_value = remaining_deck_cards
        
        # Query 7: Top discard
        mock_top_discard_query = Mock()
        mock_top_discard_query.filter.return_value.order_by.return_value.first.return_value = top_discard
        
        # Query 8: Discard count
        mock_discard_count_query = Mock()
        mock_discard_count_query.filter.return_value.count.return_value = discard_count
        
        # Query 9: Deck count
        mock_deck_count_query = Mock()
        mock_deck_count_query.filter.return_value.count.return_value = deck_count
        
        # Configurar side_effect para db.query()
        query_responses = [
            mock_actor_query,           # Player (actor)
            mock_turn_query,            # Turn
            mock_event_query,           # CardsXGame (event card)
            mock_deck_query,            # CardsXGame (first 6)
            mock_discard_pos_query,     # CardsXGame.position (max discard)
            mock_remaining_deck_query,  # CardsXGame (remaining deck)
            mock_top_discard_query,     # CardsXGame (top discard)
            mock_discard_count_query,   # CardsXGame (discard count)
            mock_deck_count_query       # CardsXGame (deck count)
        ]
        
        mock_db.query.side_effect = query_responses
    
    @pytest.mark.asyncio
    async def test_early_train_success(
        self, mock_db, mock_room, mock_game, mock_actor, mock_turn,
        mock_event_card, mock_deck_cards, mock_remaining_deck_cards, mock_top_discard
    ):
        """Test de caso exitoso: mueve 6 cartas del deck al discard"""
        
        # Configurar queries
        self.setup_db_queries(
            mock_db,
            mock_actor,
            mock_turn,
            mock_event_card,
            mock_deck_cards,
            (5,),  # max_discard_position
            mock_remaining_deck_cards,
            mock_top_discard,
            9,  # discard_count (3 originales + 6 movidas)
            4   # deck_count (10 - 6)
        )
        
        # Mock websocket service
        mock_ws = AsyncMock()
        mock_ws.notificar_estado_partida = AsyncMock()
        
        with patch('app.routes.early_train_to_paddington.get_websocket_service', return_value=mock_ws), \
             patch('app.routes.early_train_to_paddington.build_complete_game_state', return_value={
                 "game_id": 1,
                 "status": "INGAME"
             }), \
             patch('app.routes.early_train_to_paddington.get_room_by_id', return_value=mock_room), \
             patch('app.routes.early_train_to_paddington.get_game_by_id', return_value=mock_game):
            
            request = EarlyTrainRequest(card_id=100)
            
            response = await early_train_to_paddington(
                room_id=1,
                request=request,
                actor_user_id=10,
                db=mock_db
            )
            
            # Verificaciones de la respuesta
            assert response.success is True
            assert response.eventCardDiscarded.cardId == 100
            assert response.eventCardDiscarded.name == "Early train to paddington"
            assert response.eventCardDiscarded.type == "EVENT"
            assert response.discard.count == 9
            assert response.deck.remaining == 4
            
            # Verificar que se llamó a commit
            mock_db.commit.assert_called_once()
            
            # Verificar que se crearon las acciones correctas
            assert mock_db.add.call_count >= 7  # 1 evento + 1 padre + 6 hijas (mínimo)
            
            # Verificar que la carta del evento fue removida
            assert mock_event_card.is_in == CardState.REMOVED
            assert mock_event_card.position == 0
            assert mock_event_card.player_id is None
            
            # Verificar que las 6 cartas del deck se movieron al discard
            for i, card in enumerate(mock_deck_cards):
                assert card.is_in == CardState.DISCARD
                assert card.player_id is None
                assert card.position == 6 + i  # Empiezan después de max_discard_position
                assert card.hidden is False
            
            # Verificar notificaciones WebSocket
            mock_ws.notificar_estado_partida.assert_called_once()
            call_args = mock_ws.notificar_estado_partida.call_args
            assert call_args.kwargs['room_id'] == 1
    
    @pytest.mark.asyncio
    async def test_room_not_found(self, mock_db):
        """Test cuando no se encuentra la sala"""
        
        with patch('app.routes.early_train_to_paddington.get_room_by_id', return_value=None):
            request = EarlyTrainRequest(card_id=100)
            
            with pytest.raises(HTTPException) as exc_info:
                await early_train_to_paddington(
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
        
        with patch('app.routes.early_train_to_paddington.get_room_by_id', return_value=mock_room), \
             patch('app.routes.early_train_to_paddington.get_game_by_id', return_value=None):
            
            request = EarlyTrainRequest(card_id=100)
            
            with pytest.raises(HTTPException) as exc_info:
                await early_train_to_paddington(
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
        
        with patch('app.routes.early_train_to_paddington.get_room_by_id', return_value=mock_room), \
             patch('app.routes.early_train_to_paddington.get_game_by_id', return_value=mock_game):
            
            request = EarlyTrainRequest(card_id=100)
            
            with pytest.raises(HTTPException) as exc_info:
                await early_train_to_paddington(
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
        
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query
        
        with patch('app.routes.early_train_to_paddington.get_room_by_id', return_value=mock_room), \
             patch('app.routes.early_train_to_paddington.get_game_by_id', return_value=mock_game):
            
            request = EarlyTrainRequest(card_id=100)
            
            with pytest.raises(HTTPException) as exc_info:
                await early_train_to_paddington(
                    room_id=1,
                    request=request,
                    actor_user_id=10,
                    db=mock_db
                )
            
            assert exc_info.value.status_code == 404
            assert "Actor player not found" in exc_info.value.detail
    
    @pytest.mark.asyncio
    async def test_no_active_turn(self, mock_db, mock_room, mock_game, mock_actor):
        """Test cuando no hay turno activo"""
        
        mock_actor_query = Mock()
        mock_actor_query.filter.return_value.first.return_value = mock_actor
        
        mock_turn_query = Mock()
        mock_turn_query.filter.return_value.first.return_value = None
        
        mock_db.query.side_effect = [mock_actor_query, mock_turn_query]
        
        with patch('app.routes.early_train_to_paddington.get_room_by_id', return_value=mock_room), \
             patch('app.routes.early_train_to_paddington.get_game_by_id', return_value=mock_game):
            
            request = EarlyTrainRequest(card_id=100)
            
            with pytest.raises(HTTPException) as exc_info:
                await early_train_to_paddington(
                    room_id=1,
                    request=request,
                    actor_user_id=10,
                    db=mock_db
                )
            
            assert exc_info.value.status_code == 403
            assert "No active turn found" in exc_info.value.detail
    
    @pytest.mark.asyncio
    async def test_event_card_not_found(self, mock_db, mock_room, mock_game, mock_actor, mock_turn):
        """Test cuando el jugador no tiene la carta del evento"""
        
        mock_actor_query = Mock()
        mock_actor_query.filter.return_value.first.return_value = mock_actor
        
        mock_turn_query = Mock()
        mock_turn_query.filter.return_value.first.return_value = mock_turn
        
        mock_event_query = Mock()
        mock_event_query.join.return_value.filter.return_value.first.return_value = None
        
        mock_db.query.side_effect = [mock_actor_query, mock_turn_query, mock_event_query]
        
        with patch('app.routes.early_train_to_paddington.get_room_by_id', return_value=mock_room), \
             patch('app.routes.early_train_to_paddington.get_game_by_id', return_value=mock_game):
            
            request = EarlyTrainRequest(card_id=100)
            
            with pytest.raises(HTTPException) as exc_info:
                await early_train_to_paddington(
                    room_id=1,
                    request=request,
                    actor_user_id=10,
                    db=mock_db
                )
            
            assert exc_info.value.status_code == 404
            assert "Event card not found in hand" in exc_info.value.detail
    
    @pytest.mark.asyncio
    async def test_empty_deck(self, mock_db, mock_room, mock_game, mock_actor, mock_turn, mock_event_card):
        """Test cuando el deck está vacío"""
        
        mock_actor_query = Mock()
        mock_actor_query.filter.return_value.first.return_value = mock_actor
        
        mock_turn_query = Mock()
        mock_turn_query.filter.return_value.first.return_value = mock_turn
        
        mock_event_query = Mock()
        mock_event_query.join.return_value.filter.return_value.first.return_value = mock_event_card
        
        mock_deck_query = Mock()
        mock_deck_query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        
        mock_db.query.side_effect = [mock_actor_query, mock_turn_query, mock_event_query, mock_deck_query]
        
        with patch('app.routes.early_train_to_paddington.get_room_by_id', return_value=mock_room), \
             patch('app.routes.early_train_to_paddington.get_game_by_id', return_value=mock_game):
            
            request = EarlyTrainRequest(card_id=100)
            
            with pytest.raises(HTTPException) as exc_info:
                await early_train_to_paddington(
                    room_id=1,
                    request=request,
                    actor_user_id=10,
                    db=mock_db
                )
            
            assert exc_info.value.status_code == 409
            assert "Deck is empty" in exc_info.value.detail
    
    @pytest.mark.asyncio
    async def test_less_than_6_cards_in_deck(
        self, mock_db, mock_room, mock_game, mock_actor, mock_turn,
        mock_event_card, mock_top_discard
    ):
        """Test cuando hay menos de 6 cartas en el deck"""
        
        # Solo 3 cartas en el deck
        deck_cards = []
        for i in range(3):
            card = Mock()
            card.id = 200 + i
            card.is_in = CardState.DECK
            card.position = 3 - i
            card.player_id = None
            card.hidden = True
            card.card = Mock()
            card.card.name = f"Card {i}"
            card.card.type = Mock()
            card.card.type.value = "DETECTIVE"
            deck_cards.append(card)
        
        self.setup_db_queries(
            mock_db,
            mock_actor,
            mock_turn,
            mock_event_card,
            deck_cards,  # Solo 3 cartas
            (5,),
            [],  # Deck vacío después
            mock_top_discard,
            6,  # 3 originales + 3 movidas
            0   # Deck vacío
        )
        
        mock_ws = AsyncMock()
        
        with patch('app.routes.early_train_to_paddington.get_websocket_service', return_value=mock_ws), \
             patch('app.routes.early_train_to_paddington.build_complete_game_state', return_value={}), \
             patch('app.routes.early_train_to_paddington.get_room_by_id', return_value=mock_room), \
             patch('app.routes.early_train_to_paddington.get_game_by_id', return_value=mock_game):
            
            request = EarlyTrainRequest(card_id=100)
            
            response = await early_train_to_paddington(
                room_id=1,
                request=request,
                actor_user_id=10,
                db=mock_db
            )
            
            # Verificar que se movieron las 3 cartas disponibles
            assert response.success is True
            assert response.deck.remaining == 0
            assert response.discard.count == 6
            
            # Verificar que las 3 cartas se movieron
            for i, card in enumerate(deck_cards):
                assert card.is_in == CardState.DISCARD
                assert card.position == 6 + i
    
    @pytest.mark.asyncio
    async def test_database_error_rollback(
        self, mock_db, mock_room, mock_game, mock_actor, mock_turn,
        mock_event_card, mock_deck_cards
    ):
        """Test que se hace rollback en caso de error"""
        
        self.setup_db_queries(
            mock_db,
            mock_actor,
            mock_turn,
            mock_event_card,
            mock_deck_cards,
            (5,),
            [],
            mock_deck_cards[0],
            9,
            4
        )
        
        mock_db.commit.side_effect = Exception("Database error")
        
        with patch('app.routes.early_train_to_paddington.get_room_by_id', return_value=mock_room), \
             patch('app.routes.early_train_to_paddington.get_game_by_id', return_value=mock_game):
            
            request = EarlyTrainRequest(card_id=100)
            
            with pytest.raises(HTTPException) as exc_info:
                await early_train_to_paddington(
                    room_id=1,
                    request=request,
                    actor_user_id=10,
                    db=mock_db
                )
            
            assert exc_info.value.status_code == 500
            mock_db.rollback.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_first_discard_in_game(
        self, mock_db, mock_room, mock_game, mock_actor, mock_turn,
        mock_event_card, mock_deck_cards, mock_remaining_deck_cards, mock_top_discard
    ):
        """Test cuando es el primer descarte del juego"""
        
        self.setup_db_queries(
            mock_db,
            mock_actor,
            mock_turn,
            mock_event_card,
            mock_deck_cards,
            None,  # No hay max_discard_position
            mock_remaining_deck_cards,
            mock_top_discard,
            6,
            4
        )
        
        mock_ws = AsyncMock()
        
        with patch('app.routes.early_train_to_paddington.get_websocket_service', return_value=mock_ws), \
             patch('app.routes.early_train_to_paddington.build_complete_game_state', return_value={}), \
             patch('app.routes.early_train_to_paddington.get_room_by_id', return_value=mock_room), \
             patch('app.routes.early_train_to_paddington.get_game_by_id', return_value=mock_game):
            
            request = EarlyTrainRequest(card_id=100)
            
            response = await early_train_to_paddington(
                room_id=1,
                request=request,
                actor_user_id=10,
                db=mock_db
            )
            
            # Verificar que el descarte empieza en posición 1
            assert response.success is True
            assert mock_event_card.position == 0  # REMOVED no tiene posición en discard
            
            # Las 6 cartas del deck empiezan en posición 1
            for i, card in enumerate(mock_deck_cards):
                assert card.position == 1 + i


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])