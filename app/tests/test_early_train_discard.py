import pytest
from unittest.mock import Mock, patch, AsyncMock, call
from app.services.early_train_discard import early_train_discard_effect
from app.db.models import CardState, ActionType, ActionName, SourcePile, ActionResult


class TestEarlyTrainDiscardEffect:
    """Tests para el servicio early_train_discard_effect"""
    
    @pytest.fixture
    def mock_db(self):
        """Mock de la sesión de base de datos"""
        db = Mock()
        db.add = Mock()
        db.commit = Mock()
        db.flush = Mock()
        db.query = Mock()
        return db
    
    @pytest.fixture
    def mock_deck_cards(self):
        """Mock de 6 cartas en el deck"""
        cards = []
        for i in range(6):
            card = Mock()
            card.id = 200 + i
            card.id_card = 10 + i
            card.id_game = 1
            card.is_in = CardState.DECK
            card.position = 10 - i  # Posiciones descendentes
            card.hidden = True
            card.player_id = None
            cards.append(card)
        return cards
    
    @pytest.fixture
    def mock_parent_action(self):
        """Mock de la acción padre creada"""
        action = Mock()
        action.id = 999
        return action
    
    def setup_db_queries(self, mock_db, deck_cards, max_discard_pos):
        """Configura los queries del db en orden"""
        
        # Query 1: First 6 deck cards
        mock_deck_query = Mock()
        mock_deck_query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = deck_cards
        
        # Query 2: Max discard position
        mock_discard_pos_query = Mock()
        mock_discard_pos_query.filter.return_value.order_by.return_value.first.return_value = max_discard_pos
        
        mock_db.query.side_effect = [mock_deck_query, mock_discard_pos_query]
    
    @pytest.mark.asyncio
    async def test_early_train_success_6_cards(self, mock_db, mock_deck_cards):
        """Test exitoso: mueve 6 cartas del deck al discard"""
        
        self.setup_db_queries(mock_db, mock_deck_cards, (5,))
        
        mock_ws = AsyncMock()
        mock_ws.notificar_event_step_update = AsyncMock()
        
        with patch('app.services.early_train_discard.get_websocket_service', return_value=mock_ws), \
             patch('app.services.early_train_discard.create_parent_card_action') as mock_create_parent, \
             patch('app.services.early_train_discard.create_card_action') as mock_create_card:
            
            mock_parent = Mock()
            mock_parent.id = 999
            mock_create_parent.return_value = mock_parent
            
            await early_train_discard_effect(
                db=mock_db,
                game_id=1,
                player_id=10,
                room_id=1
            )
            
            # Verificar que se llamó a create_parent_card_action
            mock_create_parent.assert_called_once_with(
                db=mock_db,
                game_id=1,
                turn_id=None,
                player_id=10,
                action_type=ActionType.DISCARD,
                action_name=ActionName.EARLY_TRAIN_TO_PADDINGTON,
                source_pile=SourcePile.DISCARD_PILE
            )
            
            # Verificar que se crearon 6 acciones hijas
            assert mock_create_card.call_count == 6
            
            # Verificar que las 6 cartas se movieron al discard
            for i, card in enumerate(mock_deck_cards):
                assert card.is_in == CardState.DISCARD
                assert card.position == 6 + i  # Empiezan en 6 (5+1)
                assert card.player_id is None
                assert card.hidden is False
            
            # Verificar flush y commit
            mock_db.flush.assert_called_once()
            mock_db.commit.assert_called_once()
            
            # Verificar notificación WebSocket
            mock_ws.notificar_event_step_update.assert_called_once_with(
                room_id=1,
                player_id=10,
                event_type="early_train",
                step="finish",
                message="Jugador 10 activó Early Train to Paddington: 6 cartas movidas al descarte."
            )
    
    @pytest.mark.asyncio
    async def test_early_train_less_than_6_cards(self, mock_db):
        """Test cuando hay menos de 6 cartas en el deck"""
        
        # Solo 3 cartas en el deck
        deck_cards = []
        for i in range(3):
            card = Mock()
            card.id = 200 + i
            card.id_card = 10 + i
            card.position = 3 - i
            card.is_in = CardState.DECK
            card.player_id = None
            card.hidden = True
            deck_cards.append(card)
        
        self.setup_db_queries(mock_db, deck_cards, (5,))
        
        mock_ws = AsyncMock()
        
        with patch('app.services.early_train_discard.get_websocket_service', return_value=mock_ws), \
             patch('app.services.early_train_discard.create_parent_card_action') as mock_create_parent, \
             patch('app.services.early_train_discard.create_card_action') as mock_create_card:
            
            mock_parent = Mock()
            mock_parent.id = 999
            mock_create_parent.return_value = mock_parent
            
            await early_train_discard_effect(
                db=mock_db,
                game_id=1,
                player_id=10,
                room_id=1
            )
            
            # Verificar que se movieron solo 3 cartas
            assert mock_create_card.call_count == 3
            
            for i, card in enumerate(deck_cards):
                assert card.is_in == CardState.DISCARD
                assert card.position == 6 + i
            
            # Verificar mensaje con 3 cartas
            call_args = mock_ws.notificar_event_step_update.call_args
            assert "3 cartas movidas al descarte" in call_args.kwargs['message']
    
    @pytest.mark.asyncio
    async def test_early_train_empty_deck(self, mock_db):
        """Test cuando el deck está vacío"""
        
        # Deck vacío
        self.setup_db_queries(mock_db, [], None)
        
        mock_ws = AsyncMock()
        
        with patch('app.services.early_train_discard.get_websocket_service', return_value=mock_ws), \
             patch('app.services.early_train_discard.create_parent_card_action') as mock_create_parent, \
             patch('app.services.early_train_discard.create_card_action') as mock_create_card:
            
            await early_train_discard_effect(
                db=mock_db,
                game_id=1,
                player_id=10,
                room_id=1
            )
            
            # Verificar que NO se creó acción padre
            mock_create_parent.assert_not_called()
            mock_create_card.assert_not_called()
            
            # Verificar que NO se llamó a flush/commit
            mock_db.flush.assert_not_called()
            mock_db.commit.assert_not_called()
            
            # Verificar notificación de deck vacío
            mock_ws.notificar_event_step_update.assert_called_once_with(
                room_id=1,
                player_id=10,
                event_type="early_train",
                step="finish",
                message="Jugador 10 activó Early Train to Paddington, pero el mazo está vacío."
            )
    
    @pytest.mark.asyncio
    async def test_early_train_first_discard(self, mock_db, mock_deck_cards):
        """Test cuando es el primer descarte del juego (discard vacío)"""
        
        # max_discard_pos = None (discard vacío)
        self.setup_db_queries(mock_db, mock_deck_cards, None)
        
        mock_ws = AsyncMock()
        
        with patch('app.services.early_train_discard.get_websocket_service', return_value=mock_ws), \
             patch('app.services.early_train_discard.create_parent_card_action') as mock_create_parent, \
             patch('app.services.early_train_discard.create_card_action'):
            
            mock_parent = Mock()
            mock_parent.id = 999
            mock_create_parent.return_value = mock_parent
            
            await early_train_discard_effect(
                db=mock_db,
                game_id=1,
                player_id=10,
                room_id=1
            )
            
            # Verificar que las cartas empiezan en posición 1
            for i, card in enumerate(mock_deck_cards):
                assert card.position == 1 + i
  
    
    @pytest.mark.asyncio
    async def test_early_train_websocket_error(self, mock_db, mock_deck_cards):
        """Test cuando falla la notificación WebSocket (no debe afectar la lógica)"""
        
        self.setup_db_queries(mock_db, mock_deck_cards, (5,))
        
        mock_ws = AsyncMock()
        mock_ws.notificar_event_step_update.side_effect = Exception("WS Error")
        
        with patch('app.services.early_train_discard.get_websocket_service', return_value=mock_ws), \
             patch('app.services.early_train_discard.create_parent_card_action') as mock_create_parent, \
             patch('app.services.early_train_discard.create_card_action'):
            
            mock_parent = Mock()
            mock_parent.id = 999
            mock_create_parent.return_value = mock_parent
            
            # No debe lanzar excepción
            await early_train_discard_effect(
                db=mock_db,
                game_id=1,
                player_id=10,
                room_id=1
            )
            
            # Verificar que las cartas se movieron igual
            for card in mock_deck_cards:
                assert card.is_in == CardState.DISCARD
            
            # Verificar que se hizo commit (la lógica continuó)
            mock_db.commit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_early_train_positions_correct(self, mock_db, mock_deck_cards):
        """Test que las posiciones en discard son correctas y consecutivas"""
        
        # Discard ya tiene 10 cartas
        self.setup_db_queries(mock_db, mock_deck_cards, (10,))
        
        mock_ws = AsyncMock()
        
        with patch('app.services.early_train_discard.get_websocket_service', return_value=mock_ws), \
             patch('app.services.early_train_discard.create_parent_card_action') as mock_create_parent, \
             patch('app.services.early_train_discard.create_card_action') as mock_create_card:
            
            mock_parent = Mock()
            mock_parent.id = 999
            mock_create_parent.return_value = mock_parent
            
            await early_train_discard_effect(
                db=mock_db,
                game_id=1,
                player_id=10,
                room_id=1
            )
            
            # Verificar posiciones consecutivas empezando desde 11
            expected_positions = [11, 12, 13, 14, 15, 16]
            actual_positions = [card.position for card in mock_deck_cards]
            
            assert actual_positions == expected_positions
            
            # Verificar que create_card_action se llamó con las posiciones correctas
            for i, call_obj in enumerate(mock_create_card.call_args_list):
                assert call_obj.kwargs['position'] == expected_positions[i]
    
    @pytest.mark.asyncio
    async def test_early_train_card_attributes(self, mock_db, mock_deck_cards):
        """Test que todos los atributos de las cartas se actualizan correctamente"""
        
        self.setup_db_queries(mock_db, mock_deck_cards, (5,))
        
        mock_ws = AsyncMock()
        
        with patch('app.services.early_train_discard.get_websocket_service', return_value=mock_ws), \
             patch('app.services.early_train_discard.create_parent_card_action') as mock_create_parent, \
             patch('app.services.early_train_discard.create_card_action'):
            
            mock_parent = Mock()
            mock_parent.id = 999
            mock_create_parent.return_value = mock_parent
            
            await early_train_discard_effect(
                db=mock_db,
                game_id=1,
                player_id=10,
                room_id=1
            )
            
            # Verificar todos los atributos de cada carta
            for card in mock_deck_cards:
                assert card.is_in == CardState.DISCARD, "Card should be in DISCARD"
                assert card.player_id is None, "Card should have no player_id"
                assert card.hidden is False, "Card should be visible in discard"
                assert card.position >= 6, "Card should have valid discard position"
    
    @pytest.mark.asyncio
    async def test_early_train_action_logging(self, mock_db, mock_deck_cards):
        """Test que las acciones se registran correctamente"""
        
        self.setup_db_queries(mock_db, mock_deck_cards, (5,))
        
        mock_ws = AsyncMock()
        
        with patch('app.services.early_train_discard.get_websocket_service', return_value=mock_ws), \
             patch('app.services.early_train_discard.create_parent_card_action') as mock_create_parent, \
             patch('app.services.early_train_discard.create_card_action') as mock_create_card:
            
            mock_parent = Mock()
            mock_parent.id = 999
            mock_create_parent.return_value = mock_parent
            
            await early_train_discard_effect(
                db=mock_db,
                game_id=1,
                player_id=10,
                room_id=1
            )
            
            # Verificar acción padre
            mock_create_parent.assert_called_once()
            parent_call = mock_create_parent.call_args
            assert parent_call.kwargs['game_id'] == 1
            assert parent_call.kwargs['player_id'] == 10
            assert parent_call.kwargs['turn_id'] is None
            assert parent_call.kwargs['action_type'] == ActionType.DISCARD
            assert parent_call.kwargs['action_name'] == ActionName.EARLY_TRAIN_TO_PADDINGTON
            
            # Verificar acciones hijas
            assert mock_create_card.call_count == 6
            for i, call_obj in enumerate(mock_create_card.call_args_list):
                kwargs = call_obj.kwargs
                assert kwargs['game_id'] == 1
                assert kwargs['player_id'] == 10
                assert kwargs['turn_id'] is None
                assert kwargs['action_type'] == ActionType.DISCARD
                assert kwargs['source_pile'] == SourcePile.DISCARD_PILE
                assert kwargs['card_id'] == mock_deck_cards[i].id_card
                assert kwargs['result'] == ActionResult.SUCCESS
                assert kwargs['parent_action_id'] == 999


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])