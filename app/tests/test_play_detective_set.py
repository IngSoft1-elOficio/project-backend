# app/tests/test_play_detective_set.py
import pytest
from unittest.mock import Mock, MagicMock, patch
from fastapi import HTTPException

from app.schemas.detective_set_schema import (
    SetType, PlayDetectiveSetRequest, NextActionType
)
from app.services.detective_set_service import DetectiveSetService
from app.db.models import CardState, ActionType, ActionResult, TurnStatus


# ============================================
# TESTS DE SCHEMAS
# ============================================

def test_play_detective_set_request_parsing():
    """Test que verifica el parsing del request"""
    request_data = {
        "owner": 4,
        "setType": "marple",
        "cards": [100, 101, 102],
        "hasWildcard": False
    }
    
    request = PlayDetectiveSetRequest(**request_data)
    
    assert request.owner == 4
    assert request.setType == SetType.MARPLE
    assert request.cards == [100, 101, 102]
    assert request.hasWildcard == False


def test_play_detective_set_request_with_wildcard():
    """Test request con comodín"""
    request_data = {
        "owner": 5,
        "setType": "satterthwaite",
        "cards": [200, 201],
        "hasWildcard": True
    }
    
    request = PlayDetectiveSetRequest(**request_data)
    
    assert request.setType == SetType.SATTERTHWAITE
    assert request.hasWildcard == True


def test_play_detective_set_request_validates_cards_not_empty():
    """Test que valida que cards no esté vacío"""
    with pytest.raises(ValueError, match=".*at least 1.*"):
        PlayDetectiveSetRequest(
            owner=1,
            setType="poirot",
            cards=[],
            hasWildcard=False
        )


def test_play_detective_set_request_validates_cards_unique():
    """Test que valida que no haya IDs duplicados"""
    with pytest.raises(ValueError, match="No se pueden repetir IDs de cartas"):
        PlayDetectiveSetRequest(
            owner=1,
            setType="marple",
            cards=[100, 101, 100],  # 100 duplicado
            hasWildcard=False
        )


# ============================================
# TESTS DE VALIDACIONES DE SETS
# ============================================

def test_validate_marple_set_valid():
    """Test validación de set válido de Marple (3 iguales)"""
    mock_db = Mock()
    service = DetectiveSetService(mock_db)
    
    # Simular 3 cartas de Marple
    mock_cards = [
        Mock(id_card=6),  # Miss Marple
        Mock(id_card=6),
        Mock(id_card=6)
    ]
    
    # No debería lanzar excepción
    service._validate_set_combination(mock_cards, SetType.MARPLE, has_wildcard=False)


def test_validate_marple_set_with_wildcard():
    """Test validación de Marple con comodín (1 Marple + 2 Harley Quin)"""
    mock_db = Mock()
    service = DetectiveSetService(mock_db)
    
    mock_cards = [
        Mock(id_card=6),  # Miss Marple
        Mock(id_card=4),  # Harley Quin
        Mock(id_card=4)   # Harley Quin
    ]
    
    # No debería lanzar excepción
    service._validate_set_combination(mock_cards, SetType.MARPLE, has_wildcard=True)


def test_validate_marple_set_insufficient_cards():
    """Test que falla con menos de 3 cartas"""
    mock_db = Mock()
    service = DetectiveSetService(mock_db)
    
    mock_cards = [
        Mock(id_card=6),
        Mock(id_card=6)
    ]
    
    with pytest.raises(HTTPException) as exc_info:
        service._validate_set_combination(mock_cards, SetType.MARPLE, has_wildcard=False)
    
    assert exc_info.value.status_code == 400
    assert "at least 3 cards" in str(exc_info.value.detail)


def test_validate_beresford_tommy_tuppence():
    """Test set válido de Beresford: Tommy + Tuppence"""
    mock_db = Mock()
    service = DetectiveSetService(mock_db)
    
    card_types = [8, 10]  # Tommy + Tuppence
    
    # No debería lanzar excepción
    service._validate_beresford_set(card_types, wildcard_count=0)


def test_validate_beresford_two_tommy():
    """Test set válido de Beresford: 2 Tommy"""
    mock_db = Mock()
    service = DetectiveSetService(mock_db)
    
    card_types = [8, 8]  # Tommy + Tommy
    
    service._validate_beresford_set(card_types, wildcard_count=0)


def test_validate_beresford_tommy_wildcard():
    """Test set válido de Beresford: 1 Tommy + comodín"""
    mock_db = Mock()
    service = DetectiveSetService(mock_db)
    
    card_types = [8, 4]  # Tommy + Harley Quin
    
    service._validate_beresford_set(card_types, wildcard_count=1)


def test_validate_beresford_invalid():
    """Test set inválido de Beresford"""
    mock_db = Mock()
    service = DetectiveSetService(mock_db)
    
    card_types = [8]  # Solo 1 Tommy sin comodín
    
    with pytest.raises(HTTPException) as exc_info:
        service._validate_beresford_set(card_types, wildcard_count=0)
    
    assert exc_info.value.status_code == 400


def test_validate_set_wildcard_mismatch():
    """Test que falla si hasWildcard no coincide con las cartas"""
    mock_db = Mock()
    service = DetectiveSetService(mock_db)
    
    # Dice que tiene comodín pero no hay ninguno
    mock_cards = [
        Mock(id_card=6),
        Mock(id_card=6),
        Mock(id_card=6)
    ]
    
    with pytest.raises(HTTPException) as exc_info:
        service._validate_set_combination(mock_cards, SetType.MARPLE, has_wildcard=True)
    
    assert exc_info.value.status_code == 400
    assert "no Harley Quin card found" in str(exc_info.value.detail)


def test_validate_set_has_invalid_cards():
    """Test que falla si hay cartas inválidas en el set"""
    mock_db = Mock()
    service = DetectiveSetService(mock_db)
    
    # 2 Marple + 1 Poirot (inválido)
    mock_cards = [
        Mock(id_card=6),   # Marple
        Mock(id_card=6),   # Marple
        Mock(id_card=11)   # Poirot (no válido en set de Marple)
    ]
    
    with pytest.raises(HTTPException) as exc_info:
        service._validate_set_combination(mock_cards, SetType.MARPLE, has_wildcard=False)
    
    assert exc_info.value.status_code == 400
    # El mensaje puede ser "invalid cards" o "requires at least"
    assert "marple" in str(exc_info.value.detail).lower()


# ============================================
# TESTS DE LÓGICA DE NEXT ACTION
# ============================================

def test_determine_next_action_poirot():
    """Test que Poirot retorna SELECT_PLAYER_AND_SECRET con todos los secretos"""
    mock_db = Mock()
    service = DetectiveSetService(mock_db)
    
    # Mock de secretos disponibles
    from app.schemas.detective_set_schema import SecretInfo
    mock_secrets = [
        SecretInfo(playerId=2, position=1, hidden=True, cardId=None),
        SecretInfo(playerId=3, position=1, hidden=False, cardId=15)
    ]
    
    with patch.object(service, '_get_allowed_players', return_value=[2, 3, 4]), \
         patch.object(service, '_get_secrets_info', return_value=mock_secrets):
        next_action = service._determine_next_action(
            set_type=SetType.POIROT,
            has_wildcard=False,
            game_id=1,
            owner_id=1
        )
    
    assert next_action.type == NextActionType.SELECT_PLAYER_AND_SECRET
    assert next_action.allowedPlayers == [2, 3, 4]
    assert next_action.metadata.hasWildcard == False
    assert next_action.metadata.secretsPool == mock_secrets


def test_determine_next_action_pyne():
    """Test que Pyne retorna SELECT_PLAYER_AND_SECRET solo con secretos revelados"""
    mock_db = Mock()
    service = DetectiveSetService(mock_db)
    
    # Mock de secretos revelados solamente
    from app.schemas.detective_set_schema import SecretInfo
    mock_revealed_secrets = [
        SecretInfo(playerId=2, position=1, hidden=False, cardId=20)
    ]
    
    with patch.object(service, '_get_allowed_players', return_value=[2, 3]), \
         patch.object(service, '_get_secrets_info', return_value=mock_revealed_secrets):
        next_action = service._determine_next_action(
            set_type=SetType.PYNE,
            has_wildcard=False,
            game_id=1,
            owner_id=1
        )
    
    assert next_action.type == NextActionType.SELECT_PLAYER_AND_SECRET
    assert next_action.metadata.secretsPool == mock_revealed_secrets


def test_determine_next_action_satterthwaite():
    """Test que Satterthwaite retorna SELECT_PLAYER"""
    mock_db = Mock()
    service = DetectiveSetService(mock_db)
    
    with patch.object(service, '_get_allowed_players', return_value=[2, 3, 4]):
        next_action = service._determine_next_action(
            set_type=SetType.SATTERTHWAITE,
            has_wildcard=True,
            game_id=1,
            owner_id=1
        )
    
    assert next_action.type == NextActionType.SELECT_PLAYER
    assert next_action.metadata.hasWildcard == True


def test_determine_next_action_beresford():
    """Test que Beresford retorna SELECT_PLAYER"""
    mock_db = Mock()
    service = DetectiveSetService(mock_db)
    
    with patch.object(service, '_get_allowed_players', return_value=[2]):
        next_action = service._determine_next_action(
            set_type=SetType.BERESFORD,
            has_wildcard=False,
            game_id=1,
            owner_id=1
        )
    
    assert next_action.type == NextActionType.SELECT_PLAYER


# ============================================
# TESTS DE VALIDACIONES DE TURNO
# ============================================

def test_validate_player_turn_success():
    """Test que valida correctamente cuando es el turno del jugador"""
    mock_db = Mock()
    service = DetectiveSetService(mock_db)
    
    mock_game = Mock(player_turn_id=5)
    mock_player = Mock(id=5)
    
    # No debería lanzar excepción
    service._validate_player_turn(mock_game, mock_player)


def test_validate_player_turn_fails():
    """Test que falla cuando no es el turno del jugador"""
    mock_db = Mock()
    service = DetectiveSetService(mock_db)
    
    mock_game = Mock(player_turn_id=5)
    mock_player = Mock(id=3)  # Jugador diferente
    
    with pytest.raises(HTTPException) as exc_info:
        service._validate_player_turn(mock_game, mock_player)
    
    assert exc_info.value.status_code == 403
    assert "Not your turn" in str(exc_info.value.detail)


# ============================================
# TESTS DE INTEGRACIÓN CON CRUD
# ============================================

def test_get_next_set_position_first_set():
    """Test que retorna posición 1 para el primer set"""
    mock_db = Mock()
    service = DetectiveSetService(mock_db)
    
    with patch('app.services.detective_set_service.crud') as mock_crud:
        mock_crud.get_max_position_for_player_by_state.return_value = 0
        
        position = service._get_next_set_position(game_id=1, player_id=10)
        
        assert position == 1
        mock_crud.get_max_position_for_player_by_state.assert_called_once_with(
            mock_db, 1, 10, CardState.DETECTIVE_SET
        )


def test_get_next_set_position_second_set():
    """Test que retorna posición 2 cuando ya hay un set"""
    mock_db = Mock()
    service = DetectiveSetService(mock_db)
    
    with patch('app.services.detective_set_service.crud') as mock_crud:
        mock_crud.get_max_position_for_player_by_state.return_value = 1
        
        position = service._get_next_set_position(game_id=1, player_id=10)
        
        assert position == 2


def test_move_cards_to_detective_set():
    """Test que llama correctamente a crud.update_cards_state"""
    mock_db = Mock()
    service = DetectiveSetService(mock_db)
    
    mock_cards = [Mock(), Mock(), Mock()]
    
    with patch('app.services.detective_set_service.crud') as mock_crud:
        service._move_cards_to_detective_set(mock_cards, position=1)
        
        mock_crud.update_cards_state.assert_called_once_with(
            mock_db, mock_cards, CardState.DETECTIVE_SET, 1, hidden=False
        )


def test_create_detective_action():
    """Test que crea la acción correctamente"""
    mock_db = Mock()
    service = DetectiveSetService(mock_db)
    
    mock_action = Mock(id=501)
    
    with patch('app.services.detective_set_service.crud') as mock_crud:
        mock_crud.create_action.return_value = mock_action
        
        action = service._create_detective_action(
            game_id=1,
            turn_id=10,
            player_id=5,
            set_type=SetType.MARPLE
        )
        
        assert action.id == 501
        
        # Verificar que se llamó con los datos correctos
        call_args = mock_crud.create_action.call_args[0]
        action_data = call_args[1]
        
        assert action_data["id_game"] == 1
        assert action_data["turn_id"] == 10
        assert action_data["player_id"] == 5
        assert action_data["action_name"] == "play_Marple_set"
        assert action_data["action_type"] == ActionType.DETECTIVE_SET
        assert action_data["result"] == ActionResult.PENDING


def test_get_allowed_players_uses_crud():
    """Test que usa la función CRUD que excluye jugadores en desgracia"""
    mock_db = Mock()
    service = DetectiveSetService(mock_db)
    
    with patch('app.services.detective_set_service.crud') as mock_crud:
        mock_crud.get_players_not_in_disgrace.return_value = [2, 3, 4]
        
        players = service._get_allowed_players(game_id=1, exclude_player_id=1)
        
        assert players == [2, 3, 4]
        mock_crud.get_players_not_in_disgrace.assert_called_once_with(
            mock_db, 1, 1
        )


# ============================================
# TESTS DE FLUJO COMPLETO (MOCK)
# ============================================

def test_play_detective_set_full_flow_mock():
    """Test del flujo completo con mocks"""
    mock_db = Mock()
    service = DetectiveSetService(mock_db)
    
    request = PlayDetectiveSetRequest(
        owner=4,
        setType=SetType.MARPLE,
        cards=[100, 101, 102],
        hasWildcard=False
    )
    
    # Mock de todas las dependencias
    mock_game = Mock(id=1, player_turn_id=4)
    mock_player = Mock(id=4, room=Mock(id_game=1))
    mock_turn = Mock(id=10, status=TurnStatus.IN_PROGRESS)
    mock_cards = [
        Mock(id=100, id_card=6),
        Mock(id=101, id_card=6),
        Mock(id=102, id_card=6)
    ]
    mock_action = Mock(id=501)
    
    from app.schemas.detective_set_schema import SecretInfo
    mock_secrets = [SecretInfo(playerId=2, position=1, hidden=True, cardId=None)]
    
    with patch('app.services.detective_set_service.crud') as mock_crud, \
         patch.object(service, '_get_secrets_info', return_value=mock_secrets):
        # Setup mocks
        mock_crud.get_game_by_id.return_value = mock_game
        mock_crud.get_player_by_id.return_value = mock_player
        mock_crud.get_active_turn_for_player.return_value = mock_turn
        mock_crud.get_cards_in_hand_by_ids.return_value = mock_cards
        mock_crud.get_max_position_by_state.return_value = 0
        mock_crud.create_action.return_value = mock_action
        mock_crud.get_players_not_in_disgrace.return_value = [2, 3]
        
        # Ejecutar
        action_id, next_action = service.play_detective_set(game_id=1, request=request)
        
        # Verificar resultados
        assert action_id == 501
        assert next_action.type == NextActionType.SELECT_PLAYER_AND_SECRET
        assert next_action.allowedPlayers == [2, 3]
        assert next_action.metadata.secretsPool == mock_secrets
        
        # Verificar que se llamó commit
        mock_db.commit.assert_called_once()


# ============================================
# TESTS DE ERRORES
# ============================================

def test_play_detective_set_game_not_found():
    """Test que falla si el juego no existe"""
    mock_db = Mock()
    service = DetectiveSetService(mock_db)
    
    request = PlayDetectiveSetRequest(
        owner=4,
        setType=SetType.MARPLE,
        cards=[100, 101, 102],
        hasWildcard=False
    )
    
    with patch('app.services.detective_set_service.crud') as mock_crud:
        mock_crud.get_game_by_id.return_value = None
        
        with pytest.raises(HTTPException) as exc_info:
            service.play_detective_set(game_id=999, request=request)
        
        assert exc_info.value.status_code == 404
        assert "Game not found" in str(exc_info.value.detail)


def test_play_detective_set_player_not_found():
    """Test que falla si el jugador no existe"""
    mock_db = Mock()
    service = DetectiveSetService(mock_db)
    
    request = PlayDetectiveSetRequest(
        owner=999,
        setType=SetType.MARPLE,
        cards=[100, 101, 102],
        hasWildcard=False
    )
    
    mock_game = Mock(id=1)
    
    with patch('app.services.detective_set_service.crud') as mock_crud:
        mock_crud.get_game_by_id.return_value = mock_game
        mock_crud.get_player_by_id.return_value = None
        
        with pytest.raises(HTTPException) as exc_info:
            service.play_detective_set(game_id=1, request=request)
        
        assert exc_info.value.status_code == 404
        assert "Player not found" in str(exc_info.value.detail)


def test_play_detective_set_cards_not_in_hand():
    """Test que falla si las cartas no están en la mano"""
    mock_db = Mock()
    service = DetectiveSetService(mock_db)
    
    request = PlayDetectiveSetRequest(
        owner=4,
        setType=SetType.MARPLE,
        cards=[100, 101, 102],
        hasWildcard=False
    )
    
    mock_game = Mock(id=1, player_turn_id=4)
    mock_player = Mock(id=4, room=Mock(id_game=1))
    mock_turn = Mock(id=10)
    
    with patch('app.services.detective_set_service.crud') as mock_crud:
        mock_crud.get_game_by_id.return_value = mock_game
        mock_crud.get_player_by_id.return_value = mock_player
        mock_crud.get_active_turn_for_player.return_value = mock_turn
        mock_crud.get_cards_in_hand_by_ids.return_value = [Mock(), Mock()]  # Solo 2 cartas
        
        with pytest.raises(HTTPException) as exc_info:
            service.play_detective_set(game_id=1, request=request)
        
        assert exc_info.value.status_code == 400
        assert "not in player's hand" in str(exc_info.value.detail)
