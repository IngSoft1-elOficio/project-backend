# app/tests/test_discard.py
import pytest
from unittest.mock import Mock, patch, MagicMock

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