# app/tests/test_discard.py
import pytest
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from fastapi import HTTPException

def test_discard_new_format_parsing():
    """Test que verifica el parsing del nuevo formato"""
    from app.schemas.discard_schema import CardWithOrder, DiscardRequest
    
    # Simular request con nuevo formato
    request_data = {
        "card_ids": [
            {"order": 1, "card_id": 10},
            {"order": 2, "card_id": 11},
            {"order": 3, "card_id": 12}
        ]
    }
    
    # Parsear con Pydantic
    request = DiscardRequest(**request_data)
    
    # Verificar que se parseó correctamente
    assert len(request.card_ids) == 3
    assert request.card_ids[0].order == 1
    assert request.card_ids[0].card_id == 10
    assert request.card_ids[1].order == 2
    assert request.card_ids[1].card_id == 11

def test_discard_order_extraction():
    """Test que verifica la extracción de IDs en orden"""
    from app.schemas.discard_schema import DiscardRequest
    
    request_data = {
        "card_ids": [
            {"order": 1, "card_id": 45},
            {"order": 2, "card_id": 23},
            {"order": 3, "card_id": 67}
        ]
    }
    
    request = DiscardRequest(**request_data)
    
    # Extraer solo los card_ids
    card_ids = [c.card_id for c in request.card_ids]
    
    # Verificar orden
    assert card_ids == [45, 23, 67]

@pytest.mark.asyncio
async def test_descartar_cartas_service():
    """Test unitario del servicio de descarte"""
    from app.services.discard import descartar_cartas
    
    # Mock de DB y objetos
    mock_db = Mock()
    mock_game = Mock(id=1)
    user_id = 1
    
    # Mock de cartas ordenadas
    mock_card1 = Mock(id_card=10, card=Mock(name="Card 10"))
    mock_card2 = Mock(id_card=11, card=Mock(name="Card 11"))
    ordered_cards = [mock_card1, mock_card2]
    
    # Mock del query para contar cartas en descarte
    mock_query = Mock()
    mock_query.filter.return_value.count.return_value = 5
    mock_db.query.return_value = mock_query
    
    # Ejecutar
    result = await descartar_cartas(mock_db, mock_game, user_id, ordered_cards)
    
    # Verificar
    assert len(result) == 2
    assert mock_card1.position == 5
    assert mock_card2.position == 6
    assert mock_db.commit.called

# Mantener los tests simples originales
def test_discard_logic_simple():
    """Test simple de lógica (sin DB)"""
    card_ids = [10, 11]
    owned_ids = [10, 11, 12]
    
    for cid in card_ids:
        assert cid in owned_ids
    
    # Simular descarte
    discarded = [{"id": cid} for cid in card_ids]
    assert len(discarded) == 2

def test_discard_validations():
    """Validaciones de discard"""
    # Lista vacía
    card_ids = []
    assert len(card_ids) == 0
    
    # Carta inválida
    hand_cards = [{"id": 10}]
    card_ids = [999]
    owned_ids = [c["id"] for c in hand_cards]
    assert not all(cid in owned_ids for cid in card_ids)


# ========== TESTS DEL ENDPOINT ==========

@pytest.mark.asyncio
async def test_discard_room_not_found():
    """Test cuando la sala no existe"""
    from app.routes.discard import discard_cards
    from app.schemas.discard_schema import DiscardRequest
    
    mock_db = Mock()
    mock_db.query.return_value.filter.return_value.first.return_value = None
    
    request = DiscardRequest(card_ids=[{"order": 1, "card_id": 10}])
    
    with pytest.raises(HTTPException) as exc_info:
        await discard_cards(room_id=999, request=request, user_id=1, db=mock_db)
    
    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "not_found"


@pytest.mark.asyncio
async def test_discard_game_not_found():
    """Test cuando el juego no existe"""
    from app.routes.discard import discard_cards
    from app.schemas.discard_schema import DiscardRequest
    from app.db.models import Room
    
    mock_db = Mock()
    mock_room = Mock(spec=Room)
    mock_room.id_game = 10
    
    # Primera query retorna room, segunda retorna None (game)
    mock_db.query.return_value.filter.return_value.first.side_effect = [mock_room, None]
    
    request = DiscardRequest(card_ids=[{"order": 1, "card_id": 10}])
    
    with pytest.raises(HTTPException) as exc_info:
        await discard_cards(room_id=1, request=request, user_id=1, db=mock_db)
    
    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "game_not_found"


@pytest.mark.asyncio
async def test_discard_not_your_turn():
    """Test cuando no es el turno del jugador"""
    from app.routes.discard import discard_cards
    from app.schemas.discard_schema import DiscardRequest
    from app.db.models import Room, Game
    
    mock_db = Mock()
    mock_room = Mock(spec=Room)
    mock_room.id_game = 10
    
    mock_game = Mock(spec=Game)
    mock_game.id = 10
    mock_game.player_turn_id = 2  # Turno del jugador 2
    
    mock_db.query.return_value.filter.return_value.first.side_effect = [mock_room, mock_game]
    
    request = DiscardRequest(card_ids=[{"order": 1, "card_id": 10}])
    
    with pytest.raises(HTTPException) as exc_info:
        await discard_cards(room_id=1, request=request, user_id=1, db=mock_db)  # Usuario 1 intenta
    
    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "forbidden"


@pytest.mark.asyncio
async def test_discard_empty_card_list():
    """Test cuando la lista de cartas está vacía"""
    from app.routes.discard import discard_cards
    from app.schemas.discard_schema import DiscardRequest
    from app.db.models import Room, Game
    
    mock_db = Mock()
    mock_room = Mock(spec=Room)
    mock_room.id_game = 10
    
    mock_game = Mock(spec=Game)
    mock_game.id = 10
    mock_game.player_turn_id = 1
    
    mock_db.query.return_value.filter.return_value.first.side_effect = [mock_room, mock_game]
    
    request = DiscardRequest(card_ids=[])
    
    with pytest.raises(HTTPException) as exc_info:
        await discard_cards(room_id=1, request=request, user_id=1, db=mock_db)
    
    assert exc_info.value.status_code == 400
    assert "empty card list" in exc_info.value.detail


@pytest.mark.asyncio
async def test_discard_invalid_cards():
    """Test cuando las cartas no son del jugador o no existen"""
    from app.routes.discard import discard_cards
    from app.schemas.discard_schema import DiscardRequest
    from app.db.models import Room, Game, CardsXGame
    
    mock_db = Mock()
    mock_room = Mock(spec=Room)
    mock_room.id_game = 10
    
    mock_game = Mock(spec=Game)
    mock_game.id = 10
    mock_game.player_turn_id = 1
    
    # Setup queries: room, game, then player_cards query returns fewer cards
    def query_side_effect(*args):
        mock_query = Mock()
        if len(mock_db.query.call_args_list) == 1:  # Room query
            mock_query.filter.return_value.first.return_value = mock_room
        elif len(mock_db.query.call_args_list) == 2:  # Game query
            mock_query.filter.return_value.first.return_value = mock_game
        else:  # Player cards query - returns only 1 card but request has 2
            mock_query.filter.return_value.all.return_value = [Mock(spec=CardsXGame)]
        return mock_query
    
    mock_db.query.side_effect = query_side_effect
    
    request = DiscardRequest(card_ids=[
        {"order": 1, "card_id": 10},
        {"order": 2, "card_id": 11}
    ])
    
    with pytest.raises(HTTPException) as exc_info:
        await discard_cards(room_id=1, request=request, user_id=1, db=mock_db)
    
    assert exc_info.value.status_code == 400
    assert "invalid or not owned cards" in exc_info.value.detail


@pytest.mark.asyncio
@patch('app.routes.discard.build_complete_game_state')
@patch('app.routes.discard.get_websocket_service')
@patch('app.routes.discard.descartar_cartas')
async def test_discard_success(mock_descartar, mock_ws, mock_build_state):
    """Test exitoso de descarte de cartas"""
    from app.routes.discard import discard_cards
    from app.schemas.discard_schema import DiscardRequest
    from app.db.models import Room, Game, CardsXGame, CardState
    
    mock_db = Mock()
    mock_room = Mock(spec=Room)
    mock_room.id_game = 10
    
    mock_game = Mock(spec=Game)
    mock_game.id = 10
    mock_game.player_turn_id = 1
    
    # Mock cartas
    mock_card1 = Mock(spec=CardsXGame)
    mock_card1.id = 10
    mock_card1.id_card = 10
    mock_card1.player_id = 1
    mock_card1.card = Mock()
    mock_card1.card.name = "Card 1"
    mock_card1.card.type = Mock(value="EVENT")
    mock_card1.card.img_src = "img1.png"
    
    mock_card2 = Mock(spec=CardsXGame)
    mock_card2.id = 11
    mock_card2.id_card = 11
    mock_card2.player_id = 1
    mock_card2.card = Mock()
    mock_card2.card.name = "Card 2"
    mock_card2.card.type = Mock(value="DETECTIVE")
    mock_card2.card.img_src = "img2.png"
    
    mock_card3 = Mock(spec=CardsXGame)
    mock_card3.id = 12
    mock_card3.id_card = 12
    mock_card3.player_id = 1
    mock_card3.card = Mock()
    mock_card3.card.name = "Card 3"
    mock_card3.card.type = Mock(value="INSTANT")
    mock_card3.card.img_src = "img3.png"
    
    # Mock descartar_cartas service
    mock_descartar.return_value = [mock_card1, mock_card2]
    
    # Mock WebSocket
    mock_ws_service = Mock()
    mock_ws_service.notificar_estado_partida = AsyncMock()
    mock_ws_service.notificar_player_must_draw = AsyncMock()
    mock_ws.return_value = mock_ws_service
    
    # Mock build_complete_game_state
    mock_build_state.return_value = {"jugadores": []}
    
    # Setup queries with proper chaining
    query_count = [0]
    
    def query_side_effect(*args):
        nonlocal query_count
        query_count[0] += 1
        mock_query = Mock()
        
        if query_count[0] == 1:  # Room query
            mock_filter = Mock()
            mock_filter.first.return_value = mock_room
            mock_query.filter.return_value = mock_filter
        elif query_count[0] == 2:  # Game query
            mock_filter = Mock()
            mock_filter.first.return_value = mock_game
            mock_query.filter.return_value = mock_filter
        elif query_count[0] == 3:  # Player cards query (hand validation)
            mock_filter = Mock()
            mock_filter.all.return_value = [mock_card1, mock_card2]
            mock_query.filter.return_value = mock_filter
        elif query_count[0] == 4:  # Discarded cards query (with order_by)
            mock_filter = Mock()
            mock_order = Mock()
            mock_order.all.return_value = [mock_card1, mock_card2]
            mock_filter.order_by.return_value = mock_order
            mock_query.filter.return_value = mock_filter
        elif query_count[0] == 5:  # All hand cards query
            mock_filter = Mock()
            mock_filter.all.return_value = [mock_card3]
            mock_query.filter.return_value = mock_filter
        elif query_count[0] == 6:  # Deck remaining count
            mock_filter = Mock()
            mock_filter.count.return_value = 15
            mock_query.filter.return_value = mock_filter
        elif query_count[0] == 7:  # Discard count
            mock_filter = Mock()
            mock_filter.count.return_value = 2
            mock_query.filter.return_value = mock_filter
        elif query_count[0] == 8:  # All discarded cards query (with order_by)
            mock_filter = Mock()
            mock_order = Mock()
            mock_order.all.return_value = [mock_card1, mock_card2]
            mock_filter.order_by.return_value = mock_order
            mock_query.filter.return_value = mock_filter
        else:
            mock_filter = Mock()
            mock_filter.all.return_value = []
            mock_filter.count.return_value = 0
            mock_query.filter.return_value = mock_filter
        
        return mock_query
    
    mock_db.query.side_effect = query_side_effect
    
    request = DiscardRequest(card_ids=[
        {"order": 1, "card_id": 10},
        {"order": 2, "card_id": 11}
    ])
    
    # Execute
    response = await discard_cards(room_id=1, request=request, user_id=1, db=mock_db)
    
    # Verify response
    assert response is not None
    assert len(response.action.discarded) == 2
    assert response.action.discarded[0].name == "Card 1"
    assert response.action.discarded[1].name == "Card 2"
    assert response.hand.player_id == 1
    assert len(response.hand.cards) == 1
    assert response.hand.cards[0].name == "Card 3"
    assert response.deck.remaining == 15
    assert response.discard.count == 2
    assert response.discard.top.name == "Card 2"
    
    # Verify WebSocket calls
    mock_ws_service.notificar_estado_partida.assert_called_once()
    mock_ws_service.notificar_player_must_draw.assert_called_once_with(
        room_id=1,
        player_id=1,
        cards_to_draw=2
    )
    mock_descartar.assert_called_once()