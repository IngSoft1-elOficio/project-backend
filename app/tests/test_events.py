import pytest
from unittest.mock import Mock, patch, MagicMock
from app.db.events import (
    _events_enabled,
    _should_check_social_disgrace,
    register_events,
    after_update_cards_x_game,
    after_insert_cards_x_game,
    after_delete_cards_x_game
)
from app.db.models import CardsXGame, CardState


class TestEventsEnabled:
    """Tests para _events_enabled()"""
    
    def test_events_enabled_by_default(self):
        """Por defecto, los eventos están habilitados"""
        with patch.dict('os.environ', {}, clear=True):
            assert _events_enabled() is True
    
    def test_events_disabled_when_env_var_true(self):
        """Eventos deshabilitados cuando DISABLE_DB_EVENTS=true"""
        with patch.dict('os.environ', {'DISABLE_DB_EVENTS': 'true'}):
            assert _events_enabled() is False
    
    def test_events_disabled_case_insensitive(self):
        """DISABLE_DB_EVENTS es case-insensitive"""
        with patch.dict('os.environ', {'DISABLE_DB_EVENTS': 'TRUE'}):
            assert _events_enabled() is False
        
        with patch.dict('os.environ', {'DISABLE_DB_EVENTS': 'True'}):
            assert _events_enabled() is False
    
    def test_events_enabled_when_env_var_false(self):
        """Eventos habilitados cuando DISABLE_DB_EVENTS=false"""
        with patch.dict('os.environ', {'DISABLE_DB_EVENTS': 'false'}):
            assert _events_enabled() is True
    
    def test_events_enabled_with_invalid_value(self):
        """Eventos habilitados con valor inválido"""
        with patch.dict('os.environ', {'DISABLE_DB_EVENTS': 'invalid'}):
            assert _events_enabled() is True


class TestShouldCheckSocialDisgrace:
    """Tests para _should_check_social_disgrace()"""
    
    def test_should_check_when_secret_with_player(self):
        """Debe verificar cuando es un secreto con player_id"""
        target = Mock(spec=CardsXGame)
        target.is_in = CardState.SECRET_SET
        target.player_id = 123
        
        assert _should_check_social_disgrace(target) is True
    
    def test_should_not_check_when_not_secret(self):
        """NO debe verificar cuando no es un secreto"""
        target = Mock(spec=CardsXGame)
        target.is_in = CardState.HAND
        target.player_id = 123
        
        assert _should_check_social_disgrace(target) is False
    
    def test_should_not_check_when_no_player(self):
        """NO debe verificar cuando no tiene player_id"""
        target = Mock(spec=CardsXGame)
        target.is_in = CardState.SECRET_SET
        target.player_id = None
        
        assert _should_check_social_disgrace(target) is False
    
    def test_should_not_check_discard(self):
        """NO debe verificar cartas descartadas"""
        target = Mock(spec=CardsXGame)
        target.is_in = CardState.DISCARD
        target.player_id = 123
        
        assert _should_check_social_disgrace(target) is False
    
    def test_should_not_check_detective_set(self):
        """NO debe verificar sets de detective"""
        target = Mock(spec=CardsXGame)
        target.is_in = CardState.DETECTIVE_SET
        target.player_id = 123
        
        assert _should_check_social_disgrace(target) is False


class TestRegisterEvents:
    """Tests para register_events()"""
    
    def test_register_events_prints_message(self, capsys):
        """register_events() imprime mensaje de confirmación"""
        register_events()
        
        captured = capsys.readouterr()
        assert "Social disgrace event listeners registered" in captured.out


class TestAfterUpdateListener:
    """Tests para after_update_cards_x_game()"""
    
    @patch('app.db.events._events_enabled')
    @patch('app.db.events._handle_social_disgrace_check')
    def test_listener_disabled_when_events_disabled(
        self, 
        mock_handle, 
        mock_enabled
    ):
        """Listener no hace nada cuando eventos están deshabilitados"""
        mock_enabled.return_value = False
        
        target = Mock(spec=CardsXGame)
        target.id_game = 1
        target.id_card = 1
        target.hidden = False
        
        after_update_cards_x_game(None, None, target)
        
        # NO debe llamar a _handle_social_disgrace_check
        mock_handle.assert_not_called()
    
    @patch('app.db.events._events_enabled')
    @patch('app.db.events._handle_social_disgrace_check')
    def test_listener_calls_handle_when_enabled(
        self, 
        mock_handle, 
        mock_enabled
    ):
        """Listener llama a _handle cuando eventos están habilitados"""
        mock_enabled.return_value = True
        
        target = Mock(spec=CardsXGame)
        target.id_game = 1
        target.id_card = 1
        target.hidden = False
        target.is_in = CardState.SECRET_SET
        target.player_id = 123
        
        after_update_cards_x_game(None, None, target)
        
        # Debe llamar a _handle_social_disgrace_check
        mock_handle.assert_called_once_with(target)


class TestAfterInsertListener:
    """Tests para after_insert_cards_x_game()"""
    
    @patch('app.db.events._events_enabled')
    @patch('app.db.events._handle_social_disgrace_check')
    def test_insert_listener_disabled_when_events_disabled(
        self, 
        mock_handle, 
        mock_enabled
    ):
        """Insert listener no hace nada cuando eventos están deshabilitados"""
        mock_enabled.return_value = False
        
        target = Mock(spec=CardsXGame)
        
        after_insert_cards_x_game(None, None, target)
        
        mock_handle.assert_not_called()
    
    @patch('app.db.events._events_enabled')
    @patch('app.db.events._handle_social_disgrace_check')
    def test_insert_listener_calls_handle_when_enabled(
        self, 
        mock_handle, 
        mock_enabled
    ):
        """Insert listener llama a _handle cuando eventos están habilitados"""
        mock_enabled.return_value = True
        
        target = Mock(spec=CardsXGame)
        target.id_game = 1
        target.player_id = 123
        target.is_in = CardState.SECRET_SET
        target.hidden = False
        
        after_insert_cards_x_game(None, None, target)
        
        mock_handle.assert_called_once_with(target)


class TestAfterDeleteListener:
    """Tests para after_delete_cards_x_game()"""
    
    @patch('app.db.events._events_enabled')
    def test_delete_listener_disabled_when_events_disabled(self, mock_enabled):
        """Delete listener no hace nada cuando eventos están deshabilitados"""
        mock_enabled.return_value = False
        
        target = Mock(spec=CardsXGame)
        
        # No debe lanzar excepción
        after_delete_cards_x_game(None, None, target)
    
    @patch('app.db.events._events_enabled')
    @patch('app.db.events._should_check_social_disgrace')
    def test_delete_listener_skips_non_secrets(
        self, 
        mock_should_check, 
        mock_enabled
    ):
        """Delete listener no procesa cartas que no son secretos"""
        mock_enabled.return_value = True
        mock_should_check.return_value = False
        
        target = Mock(spec=CardsXGame)
        target.is_in = CardState.HAND
        target.player_id = None
        
        # No debe lanzar excepción
        after_delete_cards_x_game(None, None, target)


class TestHandleSocialDisgraceCheck:
    """Tests para _handle_social_disgrace_check()"""
    
    @patch('app.db.events._events_enabled')
    def test_handle_returns_early_when_disabled(self, mock_enabled):
        """_handle retorna inmediatamente cuando eventos deshabilitados"""
        from app.db.events import _handle_social_disgrace_check
        
        mock_enabled.return_value = False
        
        target = Mock(spec=CardsXGame)
        target.is_in = CardState.SECRET_SET
        target.player_id = 123
        
        # No debe lanzar excepción
        _handle_social_disgrace_check(target)
    
    @patch('app.db.events._events_enabled')
    @patch('app.db.events._should_check_social_disgrace')
    def test_handle_skips_non_secrets(
        self, 
        mock_should_check, 
        mock_enabled
    ):
        """_handle no procesa cartas que no son secretos"""
        from app.db.events import _handle_social_disgrace_check
        
        mock_enabled.return_value = True
        mock_should_check.return_value = False
        
        target = Mock(spec=CardsXGame)
        
        # No debe lanzar excepción
        _handle_social_disgrace_check(target)