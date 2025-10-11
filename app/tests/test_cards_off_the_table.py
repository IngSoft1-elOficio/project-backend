# tests/test_cards_off_the_table.py
import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, AsyncMock
from sqlalchemy.orm import Session
from app.main import app
from app.db.models import Room, Game, Player, CardsXGame, CardState, Card, CardType
from datetime import date

client = TestClient(app)


@pytest.fixture
def mock_db():
    """Mock de la base de datos"""
    db = Mock(spec=Session)
    return db


@pytest.fixture
def mock_room():
    """Mock de una sala válida"""
    room = Mock(spec=Room)
    room.id = 1
    room.id_game = 10
    return room


@pytest.fixture
def mock_game():
    """Mock de un juego válido"""
    game = Mock(spec=Game)
    game.id = 10
    game.player_turn_id = 100
    return game


@pytest.fixture
def mock_victim():
    """Mock del jugador víctima"""
    victim = Mock(spec=Player)
    victim.id = 200
    victim.name = "Victim Player"
    return victim


@pytest.fixture
def mock_players():
    """Mock de lista de jugadores"""
    player1 = Mock(spec=Player)
    player1.id = 100
    player1.name = "Player 1"
    player1.is_host = True
    player1.order = 1
    
    player2 = Mock(spec=Player)
    player2.id = 200
    player2.name = "Victim Player"
    player2.is_host = False
    player2.order = 2
    
    return [player1, player2]


@pytest.fixture
def mock_card():
    """Mock de una carta"""
    card = Mock(spec=Card)
    card.name = "NSF Card"
    card.type = CardType.NSF
    card.img_src = "nsf.png"
    return card


def create_mock_card_in_game(card_id, player_id, state, position=0, card=None):
    """Helper para crear mocks de CardsXGame"""
    cxg = Mock(spec=CardsXGame)
    cxg.id_card = card_id
    cxg.player_id = player_id
    cxg.is_in = state
    cxg.position = position
    cxg.card = card if card else Mock(name="MockCard", type=Mock(value="NSF"), img_src="img.png")
    return cxg


class TestCardsOffTheTable:
    """Tests para el endpoint cards_off_the_table"""

    @patch('app.routes.cards_off_the_table.get_websocket_service')
    @patch('app.routes.cards_off_the_table.actualizar_turno')
    @patch('app.routes.cards_off_the_table.robar_cartas_del_mazo')
    @patch('app.routes.cards_off_the_table.get_db')
    def test_victim_has_nsf_cards_success(
        self, 
        mock_get_db, 
        mock_robar, 
        mock_actualizar_turno,
        mock_ws_service,
        mock_db, 
        mock_room, 
        mock_game, 
        mock_victim, 
        mock_players,
        mock_card
    ):
        """Test: Víctima tiene NSF en mano - Se descartan y reponen"""
        # Setup
        mock_get_db.return_value.__enter__ = Mock(return_value=mock_db)
        mock_get_db.return_value.__exit__ = Mock(return_value=None)
        
        # Mock queries
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            mock_room,  # Room query
            mock_game,  # Game query
            mock_victim  # Victim query
        ]
        
        # Mock victim hand with 2 NSF cards
        nsf_card_1 = create_mock_card_in_game(13, 200, CardState.HAND, card=mock_card)
        nsf_card_2 = create_mock_card_in_game(13, 200, CardState.HAND, card=mock_card)
        other_card = create_mock_card_in_game(5, 200, CardState.HAND, card=mock_card)
        
        victim_hand = [nsf_card_1, nsf_card_2, other_card]
        
        # Mock queries para cartas
        mock_db.query.return_value.filter.return_value.all.side_effect = [
            victim_hand,  # Victim hand
            mock_players,  # Players list
            [nsf_card_1],  # Player 1 hand (for private state)
            [],  # Player 1 secrets
            [nsf_card_2, other_card],  # Player 2 hand (victim)
            []   # Player 2 secrets
        ]
        
        # Mock counts
        mock_db.query.return_value.filter.return_value.count.side_effect = [
            10,  # deck_count_before
            5,   # next_discard_pos
            8,   # deck_count_after
            5,   # discard count (public state)
            3,   # player 1 card count
            2,   # player 2 card count
            8,   # final deck count
            7    # final discard count
        ]
        
        # Mock robar cartas
        drawn_cards = [create_mock_card_in_game(20, 200, CardState.HAND)]
        mock_robar.return_value = drawn_cards
        
        # Mock actualizar_turno
        mock_actualizar_turno.return_value = None
        
        # Mock WebSocket
        mock_ws = Mock()
        mock_ws.emit_to_room = AsyncMock()
        mock_ws.ws_manager.get_sids_in_game.return_value = []
        mock_ws_service.return_value = mock_ws
        
        # Execute
        response = client.post(
            "/game/1/cards_off_the_table",
            json={"user_id": 200},
            headers={"HTTP_USER_ID": "100"}
        )
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["had_nsf"] is True
        assert data["nsf_cards_discarded"] == 2
        assert data["cards_drawn"] == 1
        assert data["victim_id"] == 200
        
        # Verify robar was called
        mock_robar.assert_called_once_with(mock_db, mock_game, 200, 2)
        
        # Verify turno updated
        mock_actualizar_turno.assert_called_once()

    @patch('app.routes.cards_off_the_table.get_websocket_service')
    @patch('app.routes.cards_off_the_table.actualizar_turno')
    @patch('app.routes.cards_off_the_table.get_db')
    def test_victim_no_nsf_cards(
        self, 
        mock_get_db, 
        mock_actualizar_turno,
        mock_ws_service,
        mock_db, 
        mock_room, 
        mock_game, 
        mock_victim, 
        mock_players
    ):
        """Test: Víctima NO tiene NSF - Solo avanza turno"""
        # Setup
        mock_get_db.return_value.__enter__ = Mock(return_value=mock_db)
        mock_get_db.return_value.__exit__ = Mock(return_value=None)
        
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            mock_room,
            mock_game,
            mock_victim
        ]
        
        # Victim hand without NSF
        other_card = create_mock_card_in_game(5, 200, CardState.HAND)
        victim_hand = [other_card]
        
        mock_db.query.return_value.filter.return_value.all.side_effect = [
            victim_hand,
            mock_players,
            [],  # Player 1 hand
            [],  # Player 1 secrets
            [other_card],  # Player 2 hand
            []   # Player 2 secrets
        ]
        
        mock_db.query.return_value.filter.return_value.count.side_effect = [
            10,  # deck_count_before
            8,   # deck_count_after
            5,   # discard count
            1,   # player 1 card count
            1,   # player 2 card count
            8,   # final deck
            5    # final discard
        ]
        
        mock_actualizar_turno.return_value = None
        
        mock_ws = Mock()
        mock_ws.emit_to_room = AsyncMock()
        mock_ws.ws_manager.get_sids_in_game.return_value = []
        mock_ws_service.return_value = mock_ws
        
        # Execute
        response = client.post(
            "/game/1/cards_off_the_table",
            json={"user_id": 200},
            headers={"HTTP_USER_ID": "100"}
        )
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["had_nsf"] is False
        assert data["nsf_cards_discarded"] == 0
        assert data["cards_drawn"] == 0
        
        # Turno should still advance
        mock_actualizar_turno.assert_called_once()

    @patch('app.routes.cards_off_the_table.get_db')
    def test_room_not_found(self, mock_get_db, mock_db):
        """Test: Sala no encontrada - 404"""
        mock_get_db.return_value.__enter__ = Mock(return_value=mock_db)
        mock_get_db.return_value.__exit__ = Mock(return_value=None)
        
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        response = client.post(
            "/game/999/cards_off_the_table",
            json={"user_id": 200},
            headers={"HTTP_USER_ID": "100"}
        )
        
        assert response.status_code == 404
        assert response.json()["detail"] == "room_not_found"

    @patch('app.routes.cards_off_the_table.get_db')
    def test_game_not_found(self, mock_get_db, mock_db, mock_room):
        """Test: Juego no encontrado - 404"""
        mock_get_db.return_value.__enter__ = Mock(return_value=mock_db)
        mock_get_db.return_value.__exit__ = Mock(return_value=None)
        
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            mock_room,  # Room found
            None        # Game not found
        ]
        
        response = client.post(
            "/game/1/cards_off_the_table",
            json={"user_id": 200},
            headers={"HTTP_USER_ID": "100"}
        )
        
        assert response.status_code == 404
        assert response.json()["detail"] == "game_not_found"

    @patch('app.routes.cards_off_the_table.get_db')
    def test_not_player_turn(self, mock_get_db, mock_db, mock_room, mock_game):
        """Test: No es el turno del jugador - 403"""
        mock_get_db.return_value.__enter__ = Mock(return_value=mock_db)
        mock_get_db.return_value.__exit__ = Mock(return_value=None)
        
        mock_game.player_turn_id = 999  # Different player
        
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            mock_room,
            mock_game
        ]
        
        response = client.post(
            "/game/1/cards_off_the_table",
            json={"user_id": 200},
            headers={"HTTP_USER_ID": "100"}
        )
        
        assert response.status_code == 403
        assert response.json()["detail"] == "not_your_turn"

    @patch('app.routes.cards_off_the_table.get_db')
    def test_victim_not_found(self, mock_get_db, mock_db, mock_room, mock_game):
        """Test: Jugador víctima no encontrado - 404"""
        mock_get_db.return_value.__enter__ = Mock(return_value=mock_db)
        mock_get_db.return_value.__exit__ = Mock(return_value=None)
        
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            mock_room,
            mock_game,
            None  # Victim not found
        ]
        
        response = client.post(
            "/game/1/cards_off_the_table",
            json={"user_id": 999},
            headers={"HTTP_USER_ID": "100"}
        )
        
        assert response.status_code == 404
        assert response.json()["detail"] == "player_not_found"

    @patch('app.routes.cards_off_the_table.get_websocket_service')
    @patch('app.routes.cards_off_the_table.actualizar_turno')
    @patch('app.routes.cards_off_the_table.robar_cartas_del_mazo')
    @patch('app.routes.cards_off_the_table.get_db')
    def test_deck_empty_no_cards_drawn(
        self, 
        mock_get_db, 
        mock_robar,
        mock_actualizar_turno,
        mock_ws_service,
        mock_db, 
        mock_room, 
        mock_game, 
        mock_victim, 
        mock_players,
        mock_card
    ):
        """Test: Mazo vacío - No se roban cartas"""
        mock_get_db.return_value.__enter__ = Mock(return_value=mock_db)
        mock_get_db.return_value.__exit__ = Mock(return_value=None)
        
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            mock_room,
            mock_game,
            mock_victim
        ]
        
        # Victim has NSF
        nsf_card = create_mock_card_in_game(13, 200, CardState.HAND, card=mock_card)
        victim_hand = [nsf_card]
        
        mock_db.query.return_value.filter.return_value.all.side_effect = [
            victim_hand,
            mock_players,
            [],
            [],
            [],
            []
        ]
        
        # Deck is empty
        mock_db.query.return_value.filter.return_value.count.side_effect = [
            0,  # deck_count_before = 0
            5,  # next_discard_pos
            0,  # deck_count_after = 0
            6,  # discard count
            0,  # player 1 card count
            0,  # player 2 card count
            0,  # final deck
            6   # final discard
        ]
        
        mock_actualizar_turno.return_value = None
        
        mock_ws = Mock()
        mock_ws.emit_to_room = AsyncMock()
        mock_ws.ws_manager.get_sids_in_game.return_value = []
        mock_ws_service.return_value = mock_ws
        
        response = client.post(
            "/game/1/cards_off_the_table",
            json={"user_id": 200},
            headers={"HTTP_USER_ID": "100"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["had_nsf"] is True
        assert data["nsf_cards_discarded"] == 1
        assert data["cards_drawn"] == 0  # No cards drawn because deck is empty
        
        # robar should NOT be called
        mock_robar.assert_not_called()

    @patch('app.routes.cards_off_the_table.procesar_ultima_carta')
    @patch('app.routes.cards_off_the_table.get_websocket_service')
    @patch('app.routes.cards_off_the_table.actualizar_turno')
    @patch('app.routes.cards_off_the_table.robar_cartas_del_mazo')
    @patch('app.routes.cards_off_the_table.get_db')
    def test_game_ends_after_last_card(
        self, 
        mock_get_db, 
        mock_robar,
        mock_actualizar_turno,
        mock_ws_service,
        mock_procesar_ultima,
        mock_db, 
        mock_room, 
        mock_game, 
        mock_victim, 
        mock_players,
        mock_card
    ):
        """Test: Se termina el mazo después de robar - Fin de juego"""
        mock_get_db.return_value.__enter__ = Mock(return_value=mock_db)
        mock_get_db.return_value.__exit__ = Mock(return_value=None)
        
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            mock_room,
            mock_game,
            mock_victim
        ]
        
        nsf_card = create_mock_card_in_game(13, 200, CardState.HAND, card=mock_card)
        victim_hand = [nsf_card]
        
        mock_db.query.return_value.filter.return_value.all.side_effect = [
            victim_hand,
            mock_players,
            [],
            []
        ]
        
        # Deck has 1 card, after drawing it becomes 0
        mock_db.query.return_value.filter.return_value.count.side_effect = [
            1,  # deck_count_before = 1
            5,  # next_discard_pos
            0,  # deck_count_after = 0 (GAME ENDS)
            6   # discard count
        ]
        
        # Mock drawn card
        last_card = create_mock_card_in_game(20, 200, CardState.HAND, card=mock_card)
        mock_robar.return_value = [last_card]
        
        mock_actualizar_turno.return_value = None
        mock_procesar_ultima.return_value = None
        
        response = client.post(
            "/game/1/cards_off_the_table",
            json={"user_id": 200},
            headers={"HTTP_USER_ID": "100"}
        )
        
        assert response.status_code == 200
        
        # procesar_ultima_carta should be called
        mock_procesar_ultima.assert_called_once()