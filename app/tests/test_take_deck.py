# app/tests/test_take_deck.py
import pytest
from unittest.mock import Mock, patch, AsyncMock
from fastapi import HTTPException
from app.schemas.take_deck import TakeDeckRequest, TakeDeckResponse, CardSummary
from app.db.models import Room, Game, CardsXGame, CardState, CardType, Player

def test_take_deck_request_schema():
    """Test que verifica el schema de TakeDeckRequest"""
    from app.schemas.take_deck import TakeDeckRequest
    
    # Request válido
    request_data = {"cantidad": 3}
    request = TakeDeckRequest(**request_data)
    assert request.cantidad == 3
    
    # Request con valor por defecto
    request_default = TakeDeckRequest()
    assert request_default.cantidad == 1
    
    # Request con cantidad máxima
    request_max = TakeDeckRequest(cantidad=10)
    assert request_max.cantidad == 10

def test_take_deck_request_validation():
    """Test de validaciones del schema"""
    from app.schemas.take_deck import TakeDeckRequest
    from pydantic import ValidationError
    
    # Cantidad menor a 1 (inválido)
    with pytest.raises(ValidationError):
        TakeDeckRequest(cantidad=0)
    
    # Cantidad mayor a 10 (inválido)
    with pytest.raises(ValidationError):
        TakeDeckRequest(cantidad=11)
    
    # Cantidad negativa (inválido)
    with pytest.raises(ValidationError):
        TakeDeckRequest(cantidad=-1)

def test_take_deck_response_schema():
    """Test del schema de respuesta"""
    from app.schemas.take_deck import TakeDeckResponse, CardSummary
    
    response_data = {
        "drawn": [
            {"id": 1, "name": "Card 1", "type": "EVENT", "img": "img1.png"},
            {"id": 2, "name": "Card 2", "type": "DETECTIVE", "img": None}
        ],
        "hand": [
            {"id": 1, "name": "Card 1", "type": "EVENT", "img": "img1.png"},
            {"id": 2, "name": "Card 2", "type": "DETECTIVE", "img": None},
            {"id": 3, "name": "Card 3", "type": "INSTANT", "img": "img3.png"}
        ],
        "deck_remaining": 15
    }
    
    response = TakeDeckResponse(**response_data)
    
    assert len(response.drawn) == 2
    assert len(response.hand) == 3
    assert response.deck_remaining == 15
    assert response.drawn[0].id == 1
    assert response.drawn[0].name == "Card 1"

@pytest.mark.asyncio
async def test_robar_cartas_del_mazo_service():
    """Test unitario del servicio robar_cartas_del_mazo"""
    from app.services.take_deck import robar_cartas_del_mazo
    
    # Mock de DB y objetos
    mock_db = Mock()
    mock_game = Mock(id=1)
    user_id = 1
    cantidad = 3
    
    # Mock de cartas en el mazo
    mock_card1 = Mock(id_card=10, card=Mock(name="Card 10"))
    mock_card2 = Mock(id_card=11, card=Mock(name="Card 11"))
    mock_card3 = Mock(id_card=12, card=Mock(name="Card 12"))
    mock_cards = [mock_card1, mock_card2, mock_card3]
    
    # Mock del query
    mock_query = Mock()
    mock_query.filter.return_value = mock_query
    mock_query.order_by.return_value = mock_query
    mock_query.limit.return_value = mock_query
    mock_query.all.return_value = mock_cards
    mock_db.query.return_value = mock_query
    
    # Ejecutar
    result = await robar_cartas_del_mazo(mock_db, mock_game, user_id, cantidad)
    
    # Verificar
    assert len(result) == 3
    assert mock_card1.player_id == user_id
    assert mock_card2.player_id == user_id
    assert mock_card3.player_id == user_id
    assert mock_db.commit.called

@pytest.mark.asyncio
async def test_robar_cartas_mazo_vacio():
    """Test cuando el mazo está vacío"""
    from app.services.take_deck import robar_cartas_del_mazo
    
    # Mock de DB con mazo vacío
    mock_db = Mock()
    mock_game = Mock(id=1)
    user_id = 1
    cantidad = 3
    
    # Mock del query que retorna lista vacía
    mock_query = Mock()
    mock_query.filter.return_value = mock_query
    mock_query.order_by.return_value = mock_query
    mock_query.limit.return_value = mock_query
    mock_query.all.return_value = []  # Mazo vacío
    mock_db.query.return_value = mock_query
    
    # Ejecutar
    result = await robar_cartas_del_mazo(mock_db, mock_game, user_id, cantidad)
    
    # Verificar que retorna lista vacía
    assert len(result) == 0
    assert mock_db.commit.called

@pytest.mark.asyncio
async def test_robar_menos_cartas_de_las_solicitadas():
    """Test cuando quedan menos cartas de las solicitadas"""
    from app.services.take_deck import robar_cartas_del_mazo
    
    # Mock de DB
    mock_db = Mock()
    mock_game = Mock(id=1)
    user_id = 1
    cantidad = 5  # Solicita 5
    
    # Mock con solo 2 cartas disponibles
    mock_card1 = Mock(id_card=10, card=Mock(name="Card 10"))
    mock_card2 = Mock(id_card=11, card=Mock(name="Card 11"))
    mock_cards = [mock_card1, mock_card2]  # Solo 2 cartas
    
    # Mock del query
    mock_query = Mock()
    mock_query.filter.return_value = mock_query
    mock_query.order_by.return_value = mock_query
    mock_query.limit.return_value = mock_query
    mock_query.all.return_value = mock_cards
    mock_db.query.return_value = mock_query
    
    # Ejecutar
    result = await robar_cartas_del_mazo(mock_db, mock_game, user_id, cantidad)
    
    # Verificar que retorna solo las 2 disponibles
    assert len(result) == 2

def test_card_summary_schema():
    """Test del schema CardSummary"""
    from app.schemas.take_deck import CardSummary
    
    # Con imagen
    card_with_img = CardSummary(
        id=1,
        name="Test Card",
        type="EVENT",
        img="test.png"
    )
    assert card_with_img.id == 1
    assert card_with_img.img == "test.png"
    
    # Sin imagen (None es opcional)
    card_no_img = CardSummary(
        id=2,
        name="Test Card 2",
        type="DETECTIVE",
        img=None
    )
    assert card_no_img.img is None


# ========== TESTS DEL ENDPOINT ==========

@pytest.mark.asyncio
async def test_take_from_deck_room_not_found():
    """Test cuando la sala no existe"""
    from app.routes.take_deck import take_from_deck
    from app.schemas.take_deck import TakeDeckRequest
    
    mock_db = Mock()
    mock_db.query.return_value.filter.return_value.first.return_value = None
    
    request = TakeDeckRequest(cantidad=2)
    
    with pytest.raises(HTTPException) as exc_info:
        await take_from_deck(room_id=999, request=request, user_id=1, db=mock_db)
    
    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "room_not_found"


@pytest.mark.asyncio
async def test_take_from_deck_game_not_found():
    """Test cuando el juego no existe"""
    from app.routes.take_deck import take_from_deck
    from app.schemas.take_deck import TakeDeckRequest
    from app.db.models import Room
    
    mock_db = Mock()
    mock_room = Mock(spec=Room)
    mock_room.id_game = 10
    
    # Primera query retorna room, segunda retorna None (game)
    mock_db.query.return_value.filter.return_value.first.side_effect = [mock_room, None]
    
    request = TakeDeckRequest(cantidad=2)
    
    with pytest.raises(HTTPException) as exc_info:
        await take_from_deck(room_id=1, request=request, user_id=1, db=mock_db)
    
    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "game_not_found"


@pytest.mark.asyncio
async def test_take_from_deck_not_your_turn():
    """Test cuando no es el turno del jugador"""
    from app.routes.take_deck import take_from_deck
    from app.schemas.take_deck import TakeDeckRequest
    from app.db.models import Room, Game
    
    mock_db = Mock()
    mock_room = Mock(spec=Room)
    mock_room.id_game = 10
    
    mock_game = Mock(spec=Game)
    mock_game.id = 10
    mock_game.player_turn_id = 2  # Turno del jugador 2
    
    mock_db.query.return_value.filter.return_value.first.side_effect = [mock_room, mock_game]
    
    request = TakeDeckRequest(cantidad=2)
    
    with pytest.raises(HTTPException) as exc_info:
        await take_from_deck(room_id=1, request=request, user_id=1, db=mock_db)  # Usuario 1 intenta
    
    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "not_your_turn"


@pytest.mark.asyncio
@patch('app.routes.take_deck.get_websocket_service')
@patch('app.routes.take_deck.robar_cartas_del_mazo')
async def test_take_from_deck_deck_empty(mock_robar, mock_ws):
    """Test cuando el mazo está vacío"""
    from app.routes.take_deck import take_from_deck
    from app.schemas.take_deck import TakeDeckRequest
    from app.db.models import Room, Game
    
    mock_db = Mock()
    mock_room = Mock(spec=Room)
    mock_room.id_game = 10
    
    mock_game = Mock(spec=Game)
    mock_game.id = 10
    mock_game.player_turn_id = 1
    
    mock_db.query.return_value.filter.return_value.first.side_effect = [mock_room, mock_game]
    
    # robar_cartas_del_mazo retorna lista vacía
    mock_robar.return_value = []
    
    request = TakeDeckRequest(cantidad=2)
    
    with pytest.raises(HTTPException) as exc_info:
        await take_from_deck(room_id=1, request=request, user_id=1, db=mock_db)
    
    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "deck_empty"


@pytest.mark.asyncio
@patch('app.routes.take_deck.build_complete_game_state')
@patch('app.routes.take_deck.get_websocket_service')
@patch('app.routes.take_deck.robar_cartas_del_mazo')
async def test_take_from_deck_success(mock_robar, mock_ws, mock_build_game_state):
    """Test exitoso de robar cartas"""
    from app.routes.take_deck import take_from_deck

    mock_db = Mock()
    mock_room = Mock(spec=Room)
    mock_room.id = 1
    mock_room.id_game = 10

    mock_game = Mock(spec=Game)
    mock_game.id = 10
    mock_game.player_turn_id = 1

    # Mock cartas robadas
    mock_card1 = Mock(spec=CardsXGame)
    mock_card1.id = 10
    mock_card1.id_card = 10
    mock_card1.card = Mock()
    mock_card1.card.name = "Drawn Card 1"
    mock_card1.card.type = Mock(value="EVENT")
    mock_card1.card.img_src = "img1.png"

    mock_card2 = Mock(spec=CardsXGame)
    mock_card2.id = 11
    mock_card2.id_card = 11
    mock_card2.card = Mock()
    mock_card2.card.name = "Drawn Card 2"
    mock_card2.card.type = Mock(value="DETECTIVE")
    mock_card2.card.img_src = "img2.png"

    mock_card3 = Mock(spec=CardsXGame)
    mock_card3.id = 12
    mock_card3.id_card = 12
    mock_card3.card = Mock()
    mock_card3.card.name = "Hand Card 3"
    mock_card3.card.type = Mock(value="INSTANT")
    mock_card3.card.img_src = "img3.png"

    drawn_cards = [mock_card1, mock_card2]
    hand_cards = [mock_card1, mock_card2, mock_card3]

    # Mock robar_cartas_del_mazo
    mock_robar.return_value = drawn_cards

    # Mock WebSocket
    mock_ws_service = Mock()
    mock_ws_service.notificar_estado_partida = AsyncMock()
    mock_ws_service.notificar_card_drawn_simple = AsyncMock()
    mock_ws.return_value = mock_ws_service

    # Mock build_complete_game_state
    game_state_mock = {
        "mazos": {"deck": {"count": 15}},
        "jugadores": [],
        "estados_privados": {}
    }
    mock_build_game_state.return_value = game_state_mock

    # Mock mock_player para Players query
    mock_player = Mock(spec=Player)
    mock_player.id = 1
    mock_player.order = 1

    # Setup query mocks
    query_count = [0]

    def query_side_effect(*args):
        nonlocal query_count
        query_count[0] += 1
        mock_query = Mock()

        if query_count[0] == 1:  # Room query
            mock_query.filter.return_value.first.return_value = mock_room
        elif query_count[0] == 2:  # Game query
            mock_query.filter.return_value.first.return_value = mock_game
        elif query_count[0] == 3:  # Hand query
            mock_query.filter.return_value.all.return_value = hand_cards
        elif query_count[0] == 4:  # Deck remaining count
            mock_query.filter.return_value.count.return_value = 15
        elif query_count[0] == 5:  # Players query
            mock_query.filter.return_value.order_by.return_value.all.return_value = [mock_player]
        else:
            mock_query.filter.return_value.all.return_value = []
            mock_query.filter.return_value.count.return_value = 0

        return mock_query

    mock_db.query.side_effect = query_side_effect

    request = TakeDeckRequest(cantidad=2)

    # Execute
    result = await take_from_deck(room_id=1, request=request, user_id=1, db=mock_db)

    # Verify response structure
    assert isinstance(result, TakeDeckResponse)
    assert len(result.drawn) == 2
    assert result.drawn[0].name == "Drawn Card 1"
    assert result.drawn[0].type == "EVENT"
    assert result.drawn[0].img == "img1.png"
    assert result.drawn[1].name == "Drawn Card 2"
    assert result.drawn[1].type == "DETECTIVE"
    assert result.drawn[1].img == "img2.png"
    
    # Verify hand contains all cards
    assert len(result.hand) == 3
    assert result.hand[0].name == "Drawn Card 1"
    assert result.hand[1].name == "Drawn Card 2"
    assert result.hand[2].name == "Hand Card 3"
    
    # Verify deck remaining
    assert result.deck_remaining == 15

    # Verify service calls
    mock_robar.assert_called_once_with(mock_db, mock_game, 1, 2)
    mock_build_game_state.assert_called_once_with(mock_db, 10)
    mock_ws_service.notificar_estado_partida.assert_called_once()
    mock_ws_service.notificar_card_drawn_simple.assert_called_once_with(
        room_id=1,
        player_id=1,
        drawn_from="deck",
        cards_remaining=3  # 6 - len(hand)
    )
