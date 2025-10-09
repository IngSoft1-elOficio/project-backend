# app/tests/test_take_deck.py
import pytest
from unittest.mock import Mock, patch

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