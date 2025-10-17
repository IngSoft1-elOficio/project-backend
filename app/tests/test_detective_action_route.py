# app/tests/test_detective_action_route.py
import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import models
from app.db.database import Base
from app.schemas.detective_action_schema import (
    DetectiveActionRequest,
    DetectiveActionResponse,
    EffectsSummary,
    RevealedSecret
)

# Configuración de BD en memoria para tests
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    yield db
    db.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def setup_full_game(db):
    """Fixture completo con juego, jugadores, turno, cartas y acción pendiente"""
    # Crear juego
    game = models.Game()
    db.add(game)
    db.commit()
    db.refresh(game)
    
    # Crear room
    room = models.Room(
        name="Test Room",
        status="INGAME",
        id_game=game.id,
        players_min=2,
        players_max=4
    )
    db.add(room)
    db.commit()
    db.refresh(room)
    
    # Crear jugadores
    player1 = models.Player(
        name="Ana",
        avatar_src="avatar1.png",
        birthdate=date(2000, 5, 10),
        id_room=room.id,
        is_host=True
    )
    player2 = models.Player(
        name="Luis",
        avatar_src="avatar2.png",
        birthdate=date(1999, 3, 1),
        id_room=room.id,
        is_host=False
    )
    db.add_all([player1, player2])
    db.commit()
    db.refresh(player1)
    db.refresh(player2)
    
    # Crear turno activo
    turn = models.Turn(
        number=1,
        id_game=game.id,
        player_id=player1.id,
        status=models.TurnStatus.IN_PROGRESS
    )
    db.add(turn)
    db.commit()
    db.refresh(turn)
    
    # Crear cartas
    poirot = models.Card(
        name="Hercule Poirot",
        description="Detective",
        type="DETECTIVE",
        img_src="/assets/cards/poirot.png",
        qty=3
    )
    murderer = models.Card(
        name="You are the Murderer!!",
        description="Secret",
        type="SECRET",
        img_src="/assets/cards/murderer.png",
        qty=1
    )
    db.add_all([poirot, murderer])
    db.commit()
    db.refresh(poirot)
    db.refresh(murderer)
    
    # Crear set de detective bajado
    poirot_entry = models.CardsXGame(
        id_game=game.id,
        id_card=poirot.id,
        is_in=models.CardState.DETECTIVE_SET,
        position=1,
        player_id=player1.id,
        hidden=False
    )
    db.add(poirot_entry)
    db.commit()
    
    # Crear secreto oculto del player2
    secret = models.CardsXGame(
        id_game=game.id,
        id_card=murderer.id,
        is_in=models.CardState.SECRET_SET,
        position=1,
        player_id=player2.id,
        hidden=True
    )
    db.add(secret)
    db.commit()
    db.refresh(secret)
    
    # Crear acción PENDING
    action = models.ActionsPerTurn(
        id_game=game.id,
        turn_id=turn.id,
        player_id=player1.id,
        action_name="play_Poirot_set",
        action_type=models.ActionType.DETECTIVE_SET,
        result=models.ActionResult.PENDING
    )
    db.add(action)
    db.commit()
    db.refresh(action)
    
    return {
        "game": game,
        "room": room,
        "player1": player1,
        "player2": player2,
        "turn": turn,
        "poirot": poirot,
        "murderer": murderer,
        "secret": secret,
        "action": action
    }


class TestDetectiveActionRoute:
    """Tests para el endpoint POST /api/game/{room_id}/detective-action"""
    
    @pytest.mark.asyncio
    @patch('app.routes.detective_action.get_websocket_service')
    @patch('app.routes.detective_action.build_complete_game_state')
    async def test_execute_detective_action_success(
        self,
        mock_build_state,
        mock_ws_service,
        setup_full_game,
        db
    ):
        """Test exitoso de ejecución de acción de detective"""
        from app.routes.detective_action import execute_detective_action
        
        data = setup_full_game
        
        # Mock WebSocket
        mock_ws = Mock()
        mock_ws.notificar_detective_action_complete = AsyncMock()
        mock_ws.notificar_estado_partida = AsyncMock()
        mock_ws_service.return_value = mock_ws
        
        # Mock game state
        mock_build_state.return_value = {"jugadores": []}
        
        # Crear request
        request = DetectiveActionRequest(
            actionId=data["action"].id,
            executorId=data["player1"].id,
            targetPlayerId=data["player2"].id,
            secretId=data["secret"].id
        )
        
        # Ejecutar
        response = await execute_detective_action(
            room_id=data["room"].id,
            request=request,
            db=db
        )
        
        # Verificar response
        assert response.success is True
        assert response.completed is True
        assert len(response.effects.revealed) == 1
        
        # Verificar que se llamó a WebSocket
        mock_ws.notificar_detective_action_complete.assert_called_once()
        mock_ws.notificar_estado_partida.assert_called_once()
        
        # Verificar que el secreto fue revelado en BD
        db.refresh(data["secret"])
        assert data["secret"].hidden is False
    
    @pytest.mark.asyncio
    async def test_room_not_found(self, db):
        """Test cuando la room no existe"""
        from app.routes.detective_action import execute_detective_action
        from fastapi import HTTPException
        
        request = DetectiveActionRequest(
            actionId=1,
            executorId=1,
            targetPlayerId=2,
            secretId=1
        )
        
        with pytest.raises(HTTPException) as exc_info:
            await execute_detective_action(room_id=9999, request=request, db=db)
        
        assert exc_info.value.status_code == 404
        assert "Room not found" in str(exc_info.value.detail)
    
    @pytest.mark.asyncio
    async def test_game_not_started(self, db):
        """Test cuando el juego no ha iniciado"""
        from app.routes.detective_action import execute_detective_action
        from fastapi import HTTPException
        
        # Crear room sin juego
        room = models.Room(
            name="Test Room",
            status="WAITING",
            id_game=None,  # Sin juego
            players_min=2,
            players_max=4
        )
        db.add(room)
        db.commit()
        db.refresh(room)
        
        request = DetectiveActionRequest(
            actionId=1,
            executorId=1,
            targetPlayerId=2,
            secretId=1
        )
        
        with pytest.raises(HTTPException) as exc_info:
            await execute_detective_action(room_id=room.id, request=request, db=db)
        
        assert exc_info.value.status_code == 409
        assert "Game not started" in str(exc_info.value.detail)
    
    @pytest.mark.asyncio
    @patch('app.routes.detective_action.get_websocket_service')
    @patch('app.routes.detective_action.build_complete_game_state')
    async def test_service_http_exception_is_reraised(
        self,
        mock_build_state,
        mock_ws_service,
        setup_full_game,
        db
    ):
        """Test que las HTTPException del service se re-lanzan"""
        from app.routes.detective_action import execute_detective_action
        from fastapi import HTTPException
        
        data = setup_full_game
        
        # Mock WebSocket
        mock_ws = Mock()
        mock_ws_service.return_value = mock_ws
        
        # Request con acción que no existe
        request = DetectiveActionRequest(
            actionId=9999,  # No existe
            executorId=data["player1"].id,
            targetPlayerId=data["player2"].id,
            secretId=data["secret"].id
        )
        
        with pytest.raises(HTTPException) as exc_info:
            await execute_detective_action(
                room_id=data["room"].id,
                request=request,
                db=db
            )
        
        assert exc_info.value.status_code == 404
        assert "Action not found" in str(exc_info.value.detail)
    
    @pytest.mark.asyncio
    @patch('app.routes.detective_action.get_websocket_service')
    @patch('app.routes.detective_action.build_complete_game_state')
    @patch('app.routes.detective_action.DetectiveActionService')
    async def test_unexpected_exception_returns_500(
        self,
        mock_service_class,
        mock_build_state,
        mock_ws_service,
        setup_full_game,
        db
    ):
        """Test que excepciones inesperadas retornan 500"""
        from app.routes.detective_action import execute_detective_action
        from fastapi import HTTPException
        
        data = setup_full_game
        
        # Mock service que lanza excepción genérica
        mock_service = Mock()
        mock_service.execute_detective_action.side_effect = ValueError("Database error")
        mock_service_class.return_value = mock_service
        
        request = DetectiveActionRequest(
            actionId=data["action"].id,
            executorId=data["player1"].id,
            targetPlayerId=data["player2"].id,
            secretId=data["secret"].id
        )
        
        with pytest.raises(HTTPException) as exc_info:
            await execute_detective_action(
                room_id=data["room"].id,
                request=request,
                db=db
            )
        
        assert exc_info.value.status_code == 500
        assert "Internal server error" in str(exc_info.value.detail)
    
    @pytest.mark.asyncio
    @patch('app.routes.detective_action.get_websocket_service')
    @patch('app.routes.detective_action.build_complete_game_state')
    async def test_build_game_state_exception_is_handled(
        self,
        mock_build_state,
        mock_ws_service,
        setup_full_game,
        db
    ):
        """Test que errores en build_game_state no rompen el flow"""
        from app.routes.detective_action import execute_detective_action
        
        data = setup_full_game
        
        # Mock WebSocket
        mock_ws = Mock()
        mock_ws.notificar_detective_action_complete = AsyncMock()
        mock_ws.notificar_estado_partida = AsyncMock()
        mock_ws_service.return_value = mock_ws
        
        # Mock build_game_state que falla
        mock_build_state.side_effect = Exception("Database connection lost")
        
        request = DetectiveActionRequest(
            actionId=data["action"].id,
            executorId=data["player1"].id,
            targetPlayerId=data["player2"].id,
            secretId=data["secret"].id
        )
        
        # No debe fallar
        response = await execute_detective_action(
            room_id=data["room"].id,
            request=request,
            db=db
        )
        
        # Verificar que el response es exitoso
        assert response.success is True
        
        # Verificar que se llamó a WebSocket con game_state vacío
        call_args = mock_ws.notificar_estado_partida.call_args
        assert call_args[1]["game_state"] == {}
    
    @pytest.mark.asyncio
    @patch('app.routes.detective_action.get_websocket_service')
    @patch('app.routes.detective_action.build_complete_game_state')
    async def test_websocket_exception_does_not_break_response(
        self,
        mock_build_state,
        mock_ws_service,
        setup_full_game,
        db
    ):
        """Test que errores en WebSocket no rompen el response"""
        from app.routes.detective_action import execute_detective_action
        
        data = setup_full_game
        
        # Mock WebSocket que falla
        mock_ws = Mock()
        mock_ws.notificar_detective_action_complete = AsyncMock(
            side_effect=Exception("WebSocket connection lost")
        )
        mock_ws_service.return_value = mock_ws
        
        # Mock game state
        mock_build_state.return_value = {"jugadores": []}
        
        request = DetectiveActionRequest(
            actionId=data["action"].id,
            executorId=data["player1"].id,
            targetPlayerId=data["player2"].id,
            secretId=data["secret"].id
        )
        
        # No debe fallar
        response = await execute_detective_action(
            room_id=data["room"].id,
            request=request,
            db=db
        )
        
        # Verificar que el response es exitoso a pesar del error de WS
        assert response.success is True
        assert response.completed is True
    
    @pytest.mark.asyncio
    async def test_get_db_generator(self):
        """Test que get_db funciona correctamente"""
        from app.routes.detective_action import get_db
        
        # Ejecutar el generador
        gen = get_db()
        db = next(gen)
        
        # Verificar que retorna una sesión
        assert db is not None
        
        # Cerrar el generador (simula el finally)
        try:
            next(gen)
        except StopIteration:
            pass
    
    @pytest.mark.asyncio
    @patch('app.routes.detective_action.get_websocket_service')
    @patch('app.routes.detective_action.build_complete_game_state')
    async def test_response_structure(
        self,
        mock_build_state,
        mock_ws_service,
        setup_full_game,
        db
    ):
        """Test que el response tiene la estructura correcta"""
        from app.routes.detective_action import execute_detective_action
        
        data = setup_full_game
        
        # Mock WebSocket
        mock_ws = Mock()
        mock_ws.notificar_detective_action_complete = AsyncMock()
        mock_ws.notificar_estado_partida = AsyncMock()
        mock_ws_service.return_value = mock_ws
        
        # Mock game state
        mock_build_state.return_value = {"jugadores": []}
        
        request = DetectiveActionRequest(
            actionId=data["action"].id,
            executorId=data["player1"].id,
            targetPlayerId=data["player2"].id,
            secretId=data["secret"].id
        )
        
        response = await execute_detective_action(
            room_id=data["room"].id,
            request=request,
            db=db
        )
        
        # Verificar estructura
        assert hasattr(response, 'success')
        assert hasattr(response, 'completed')
        assert hasattr(response, 'nextAction')
        assert hasattr(response, 'effects')
        
        # Verificar tipos
        assert isinstance(response.success, bool)
        assert isinstance(response.completed, bool)
        assert isinstance(response.effects, EffectsSummary)
        
        # Verificar effects
        assert hasattr(response.effects, 'revealed')
        assert hasattr(response.effects, 'hidden')
        assert hasattr(response.effects, 'transferred')
        assert isinstance(response.effects.revealed, list)
        
        # Verificar revealed secret
        if len(response.effects.revealed) > 0:
            revealed = response.effects.revealed[0]
            assert isinstance(revealed, RevealedSecret)
            assert hasattr(revealed, 'playerId')
            assert hasattr(revealed, 'secretId')
            assert hasattr(revealed, 'cardId')
            assert hasattr(revealed, 'cardName')
            assert hasattr(revealed, 'imgSrc')
            assert hasattr(revealed, 'position')
