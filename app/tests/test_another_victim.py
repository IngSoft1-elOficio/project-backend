import pytest
from unittest.mock import Mock, patch, AsyncMock
from fastapi import HTTPException
from datetime import datetime

from app.routes.another_victim import another_victim, VictimRequest
from app.db.models import CardState, TurnStatus, ActionType, ActionResult


class TestAnotherVictim:
    """Tests para el endpoint another_victim"""
    
    @pytest.fixture
    def mock_db(self):
        """Mock de la sesión de base de datos"""
        db = Mock()
        db.add = Mock()
        db.commit = Mock()
        db.flush = Mock()
        db.rollback = Mock()
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
    def mock_victim(self):
        """Mock del jugador víctima"""
        victim = Mock()
        victim.id = 20
        victim.name = "Victim"
        victim.id_room = 1
        return victim
    
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
    def mock_victim_set_cards(self):
        """Mock de las cartas del set del jugador víctima"""
        cards = []
        for i in range(3):
            card = Mock()
            card.id = i + 1
            card.player_id = 20
            card.id_game = 1
            card.is_in = CardState.DETECTIVE_SET
            card.position = 1
            card.card = Mock()
            card.card.name = f"Card {i}"
            card.card.type = Mock()
            card.card.type.value = "VICTIM"
            cards.append(card)
        return cards
    
    @pytest.fixture
    def mock_another_victim_card(self):
        """Mock de la carta Another Victim"""
        card = Mock()
        card.id = 100
        card.player_id = 10
        card.id_game = 1
        card.is_in = CardState.HAND
        card.card = Mock()
        card.card.id = 13
        return card
    
    def setup_query_chain(self, mock_db, responses):
        """
        Helper para configurar cadenas de queries de SQLAlchemy.
        responses: lista de respuestas en orden de ejecución
        """
        response_iter = iter(responses)
        
        def create_query_mock(*args, **kwargs):
            mock_query = Mock()
            
            # Mock para .filter()
            def mock_filter(*filter_args, **filter_kwargs):
                mock_query.filter = Mock(return_value=mock_query)
                return mock_query
            
            # Mock para .join()
            def mock_join(*join_args, **join_kwargs):
                mock_query.join = Mock(return_value=mock_query)
                return mock_query
            
            # Mock para .order_by()
            def mock_order_by(*order_args, **order_kwargs):
                mock_query.order_by = Mock(return_value=mock_query)
                return mock_query
            
            # Mock para .first()
            def mock_first():
                try:
                    return next(response_iter)
                except StopIteration:
                    return None
            
            # Mock para .all()
            def mock_all():
                try:
                    result = next(response_iter)
                    return result if isinstance(result, list) else [result]
                except StopIteration:
                    return []
            
            mock_query.filter = mock_filter
            mock_query.join = mock_join
            mock_query.order_by = mock_order_by
            mock_query.first = mock_first
            mock_query.all = mock_all
            
            return mock_query
        
        mock_db.query = create_query_mock
    
    @pytest.mark.asyncio
    async def test_another_victim_success(
        self, mock_db, mock_room, mock_game, mock_actor, 
        mock_victim, mock_turn, mock_victim_set_cards, mock_another_victim_card
    ):
        """Test de caso exitoso: robo de set"""
        
        # Configurar respuestas en el orden exacto del código
        self.setup_query_chain(mock_db, [
            mock_room,                  # Room query
            mock_game,                  # Game query
            mock_actor,                 # Actor query
            mock_turn,                  # Turn query
            mock_victim,                # Victim query
            mock_victim_set_cards,      # victim_set_cards.all()
            mock_another_victim_card,   # Another Victim card query
            (5,)                        # max_discard_position
        ])
        
        # Mock websocket service
        mock_ws = AsyncMock()
        mock_ws.notificar_event_step_update = AsyncMock()
        mock_ws.notificar_event_action_complete = AsyncMock()
        mock_ws.notificar_estado_publico = AsyncMock()
        mock_ws.notificar_estados_privados = AsyncMock()
        
        with patch('app.routes.another_victim.get_websocket_service', return_value=mock_ws), \
             patch('app.routes.another_victim.build_complete_game_state', return_value={
                 "game_id": 1,
                 "status": "INGAME",
                 "turno_actual": 10,
                 "jugadores": [],
                 "mazos": {},
                 "estados_privados": {}
             }):
            
            request = VictimRequest(originalOwnerId=20, setPosition=1)
            
            response = await another_victim(
                room_id=1,
                request=request,
                actor_user_id=10,
                db=mock_db
            )
            
            # Verificaciones de la respuesta
            assert response.success is True
            assert response.transferredSet.position == 1
            assert response.transferredSet.newOwnerId == 10
            assert response.transferredSet.originalOwnerId == 20
            assert len(response.transferredSet.cards) == 3
            
            # Verificar que se llamó a commit
            mock_db.commit.assert_called_once()
            
            # Verificar que se crearon las acciones correctas
            assert mock_db.add.call_count >= 3  # event, steal, moves
            
            # Verificar notificaciones WebSocket
            mock_ws.notificar_event_step_update.assert_called_once()
            mock_ws.notificar_event_action_complete.assert_called_once()
            mock_ws.notificar_estado_publico.assert_called_once()
            mock_ws.notificar_estados_privados.assert_called_once()
            
            # Verificar estructura de la notificación de step_update
            call_args = mock_ws.notificar_event_step_update.call_args
            assert call_args.kwargs['room_id'] == 1
            assert call_args.kwargs['player_id'] == 10
            assert call_args.kwargs['event_type'] == "another_victim"
            assert call_args.kwargs['step'] == "set_stolen"
    
    @pytest.mark.asyncio
    async def test_room_not_found(self, mock_db):
        """Test cuando no se encuentra la sala"""
        self.setup_query_chain(mock_db, [None])
        
        request = VictimRequest(originalOwnerId=20, setPosition=1)
        
        with pytest.raises(HTTPException) as exc_info:
            await another_victim(
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
        self.setup_query_chain(mock_db, [mock_room, None])
        
        request = VictimRequest(originalOwnerId=20, setPosition=1)
        
        with pytest.raises(HTTPException) as exc_info:
            await another_victim(
                room_id=1,
                request=request,
                actor_user_id=10,
                db=mock_db
            )
        
        assert exc_info.value.status_code == 404
        assert "Game not found" in exc_info.value.detail
    
    @pytest.mark.asyncio
    async def test_actor_not_found(self, mock_db, mock_room, mock_game):
        """Test cuando no se encuentra el actor"""
        self.setup_query_chain(mock_db, [mock_room, mock_game, None])
        
        request = VictimRequest(originalOwnerId=20, setPosition=1)
        
        with pytest.raises(HTTPException) as exc_info:
            await another_victim(
                room_id=1,
                request=request,
                actor_user_id=10,
                db=mock_db
            )
        
        assert exc_info.value.status_code == 404
        assert "Actor player not found" in exc_info.value.detail
    
    @pytest.mark.asyncio
    async def test_not_player_turn(self, mock_db, mock_room, mock_game, mock_actor):
        """Test cuando no es el turno del jugador"""
        mock_game.player_turn_id = 999  # Different player
        
        self.setup_query_chain(mock_db, [mock_room, mock_game, mock_actor])
        
        request = VictimRequest(originalOwnerId=20, setPosition=1)
        
        with pytest.raises(HTTPException) as exc_info:
            await another_victim(
                room_id=1,
                request=request,
                actor_user_id=10,
                db=mock_db
            )
        
        assert exc_info.value.status_code == 403
        assert "Not your turn" in exc_info.value.detail
    
    @pytest.mark.asyncio
    async def test_no_active_turn(self, mock_db, mock_room, mock_game, mock_actor):
        """Test cuando no hay turno activo"""
        self.setup_query_chain(mock_db, [mock_room, mock_game, mock_actor, None])
        
        request = VictimRequest(originalOwnerId=20, setPosition=1)
        
        with pytest.raises(HTTPException) as exc_info:
            await another_victim(
                room_id=1,
                request=request,
                actor_user_id=10,
                db=mock_db
            )
        
        assert exc_info.value.status_code == 403
        assert "No active turn found" in exc_info.value.detail
    
    @pytest.mark.asyncio
    async def test_victim_not_found(
        self, mock_db, mock_room, mock_game, mock_actor, mock_turn
    ):
        """Test cuando no se encuentra la víctima"""
        self.setup_query_chain(mock_db, [mock_room, mock_game, mock_actor, mock_turn, None])
        
        request = VictimRequest(originalOwnerId=20, setPosition=1)
        
        with pytest.raises(HTTPException) as exc_info:
            await another_victim(
                room_id=1,
                request=request,
                actor_user_id=10,
                db=mock_db
            )
        
        assert exc_info.value.status_code == 404
        assert "Target player not found" in exc_info.value.detail
    
    @pytest.mark.asyncio
    async def test_cannot_steal_from_yourself(
        self, mock_db, mock_room, mock_game, mock_actor, mock_turn
    ):
        """Test cuando intentas robarte a ti mismo"""
        self.setup_query_chain(mock_db, [mock_room, mock_game, mock_actor, mock_turn, mock_actor])
        
        request = VictimRequest(originalOwnerId=10, setPosition=1)
        
        with pytest.raises(HTTPException) as exc_info:
            await another_victim(
                room_id=1,
                request=request,
                actor_user_id=10,
                db=mock_db
            )
        
        assert exc_info.value.status_code == 400
        assert "Cannot steal from yourself" in exc_info.value.detail
    
    @pytest.mark.asyncio
    async def test_no_detective_set_found(
        self, mock_db, mock_room, mock_game, mock_actor, mock_turn, mock_victim
    ):
        """Test cuando no existe el set especificado"""
        self.setup_query_chain(mock_db, [
            mock_room, mock_game, mock_actor, mock_turn, mock_victim, []
        ])
        
        request = VictimRequest(originalOwnerId=20, setPosition=5)
        
        with pytest.raises(HTTPException) as exc_info:
            await another_victim(
                room_id=1,
                request=request,
                actor_user_id=10,
                db=mock_db
            )
        
        assert exc_info.value.status_code == 404
        assert "No detective set found" in exc_info.value.detail
    
    @pytest.mark.asyncio
    async def test_invalid_detective_set(
        self, mock_db, mock_room, mock_game, mock_actor, 
        mock_turn, mock_victim
    ):
        """Test cuando el set tiene menos de 2 cartas"""
        single_card = [Mock()]
        
        self.setup_query_chain(mock_db, [
            mock_room, mock_game, mock_actor, mock_turn, mock_victim, single_card
        ])
        
        request = VictimRequest(originalOwnerId=20, setPosition=1)
        
        with pytest.raises(HTTPException) as exc_info:
            await another_victim(
                room_id=1,
                request=request,
                actor_user_id=10,
                db=mock_db
            )
        
        assert exc_info.value.status_code == 400
        assert "Invalid detective set" in exc_info.value.detail
    
    @pytest.mark.asyncio
    async def test_database_error_rollback(
        self, mock_db, mock_room, mock_game, mock_actor, 
        mock_turn, mock_victim, mock_victim_set_cards
    ):
        """Test que se hace rollback en caso de error"""
        self.setup_query_chain(mock_db, [
            mock_room, mock_game, mock_actor, mock_turn, 
            mock_victim, mock_victim_set_cards, None, (5,)
        ])
        
        mock_db.commit.side_effect = Exception("Database error")
        
        request = VictimRequest(originalOwnerId=20, setPosition=1)
        
        with pytest.raises(HTTPException) as exc_info:
            await another_victim(
                room_id=1,
                request=request,
                actor_user_id=10,
                db=mock_db
            )
        
        assert exc_info.value.status_code == 500
        mock_db.rollback.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_card_transfer_updates(
        self, mock_db, mock_room, mock_game, mock_actor, 
        mock_turn, mock_victim, mock_victim_set_cards, mock_another_victim_card
    ):
        """Test que las cartas se transfieren correctamente"""
        self.setup_query_chain(mock_db, [
            mock_room, mock_game, mock_actor, mock_turn, 
            mock_victim, mock_victim_set_cards, 
            mock_another_victim_card, (5,)
        ])
        
        mock_ws = AsyncMock()
        
        with patch('app.routes.another_victim.get_websocket_service', return_value=mock_ws), \
             patch('app.routes.another_victim.build_complete_game_state', return_value={
                 "estados_privados": {}
             }):
            
            request = VictimRequest(originalOwnerId=20, setPosition=1)
            
            await another_victim(
                room_id=1,
                request=request,
                actor_user_id=10,
                db=mock_db
            )
            
            # Verificar que todas las cartas del set cambiaron de dueño
            for card in mock_victim_set_cards:
                assert card.player_id == 10
            
            # Verificar que la carta Another Victim fue descartada
            assert mock_another_victim_card.is_in == CardState.DISCARD
            assert mock_another_victim_card.position == 6
            assert mock_another_victim_card.hidden is False
            assert mock_another_victim_card.player_id is None
    
    @pytest.mark.asyncio
    async def test_another_victim_without_card_in_hand(
        self, mock_db, mock_room, mock_game, mock_actor, 
        mock_turn, mock_victim, mock_victim_set_cards
    ):
        """Test cuando el jugador no tiene la carta Another Victim en la mano"""
        self.setup_query_chain(mock_db, [
            mock_room, mock_game, mock_actor, mock_turn, 
            mock_victim, mock_victim_set_cards, 
            None,  # No tiene la carta Another Victim
            None   # No hay max_discard_position (primera carta descartada)
        ])
        
        mock_ws = AsyncMock()
        
        with patch('app.routes.another_victim.get_websocket_service', return_value=mock_ws), \
             patch('app.routes.another_victim.build_complete_game_state', return_value={}):
            
            request = VictimRequest(originalOwnerId=20, setPosition=1)
            
            response = await another_victim(
                room_id=1,
                request=request,
                actor_user_id=10,
                db=mock_db
            )
            
            # Debe continuar exitosamente aunque no tenga la carta
            assert response.success is True
            
            # Verificar que las cartas del set fueron transferidas
            for card in mock_victim_set_cards:
                assert card.player_id == 10