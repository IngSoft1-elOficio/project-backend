"""
Tests para NotSoFastService - Métodos relacionados con cancelación de acciones NSF

Métodos testeados:
- cancel_nsf_action
- _cancel_create_set
- _cancel_event
- _cancel_add_to_set
"""
import pytest
from datetime import date, datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from fastapi import HTTPException

from app.db import models, crud
from app.db.models import CardState, ActionType, ActionName, ActionResult
from app.services.not_so_fast_service import NotSoFastService
from app.db.database import Base


# Configuración de BD en memoria para tests
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    
    # Cargar cartas necesarias para los tests
    _load_cards(db)
    
    yield db
    db.close()
    Base.metadata.drop_all(bind=engine)


def _load_cards(db: Session):
    """Carga las cartas necesarias para los tests"""
    cards = [
        # ID 4 - Harley Quinn
        models.Card(id=4, name="Harley Quin Wildcard", description="Wildcard", type="DETECTIVE", img_src="/cards/detective_quin.png", qty=4),
        # ID 5 - Ariadne Oliver
        models.Card(id=5, name="Adriane Oliver", description="Add to any existing set", type="DETECTIVE", img_src="/cards/detective_oliver.png", qty=3),
        # ID 6 - Miss Marple  
        models.Card(id=6, name="Miss Marple", description="Choose a player", type="DETECTIVE", img_src="/cards/detective_marple.png", qty=3),
        # ID 7 - Parker Pyne
        models.Card(id=7, name="Parker Pyne", description="Flip face-up card down", type="DETECTIVE", img_src="/cards/detective_pyne.png", qty=3),
        # ID 8 - Tommy Beresford
        models.Card(id=8, name="Tommy Beresford", description="Choose a player", type="DETECTIVE", img_src="/cards/detective_tommyberesford.png", qty=2),
        # ID 9 - Eileen Brent
        models.Card(id=9, name='Lady Eileen "Bundle" Brent', description="Return to hand if cancelled", type="DETECTIVE", img_src="/cards/detective_brent.png", qty=3),
        # ID 10 - Tuppence Beresford
        models.Card(id=10, name="Tuppence Beresford", description="Choose a player", type="DETECTIVE", img_src="/cards/detective_tuppenceberesford.png", qty=2),
        # ID 11 - Hercule Poirot
        models.Card(id=11, name="Hercule Poirot", description="Choose a player", type="DETECTIVE", img_src="/cards/detective_poirot.png", qty=3),
        # ID 13 - Not So Fast
        models.Card(id=13, name="Not so fast", description="Cancel an action", type="INSTANT", img_src="/cards/instant_notsofast.png", qty=10),
        # ID 17 - Point your suspicions (un evento cualquiera)
        models.Card(id=17, name="Point your suspicions", description="All players point", type="EVENT", img_src="/cards/event_pointsuspicions.png", qty=3),
    ]
    db.add_all(cards)
    db.commit()
import pytest
from sqlalchemy.orm import Session
from datetime import datetime, date
from fastapi import HTTPException

from app.db import crud, models
from app.db.models import CardState, ActionType, ActionName, ActionResult
from app.services.not_so_fast_service import NotSoFastService


@pytest.fixture
def setup_nsf_cancel_service_test(db: Session):
    """
    Fixture completa para testear el servicio de cancelación NSF.
    """
    # Crear juego
    game = models.Game(player_turn_id=None)
    db.add(game)
    db.flush()
    
    # Crear room
    room = models.Room(
        name="NSF Service Test",
        players_min=2,
        players_max=6,
        status=models.RoomStatus.INGAME,
        id_game=game.id
    )
    db.add(room)
    db.flush()
    
    # Crear jugadores
    player1 = models.Player(
        name="ServicePlayer1",
        avatar_src="/avatars/sp1.jpg",
        birthdate=date(1990, 1, 1),
        id_room=room.id,
        is_host=True,
        order=1
    )
    player2 = models.Player(
        name="ServicePlayer2",
        avatar_src="/avatars/sp2.jpg",
        birthdate=date(1990, 2, 2),
        id_room=room.id,
        is_host=False,
        order=2
    )
    db.add_all([player1, player2])
    db.flush()
    
    game.player_turn_id = player1.id
    db.flush()
    
    # Crear turn
    turn = models.Turn(
        number=1,
        id_game=game.id,
        player_id=player1.id,
        status=models.TurnStatus.IN_PROGRESS,
        start_time=datetime.now()
    )
    db.add(turn)
    db.flush()
    
    # Crear cartas para diferentes tests
    # Parker Pyne x2 (para CREATE_SET)
    card_pyne1 = models.CardsXGame(
        id_game=game.id,
        id_card=7,
        is_in=CardState.HAND,
        position=1,
        player_id=player1.id,
        hidden=True
    )
    card_pyne2 = models.CardsXGame(
        id_game=game.id,
        id_card=7,
        is_in=CardState.HAND,
        position=2,
        player_id=player1.id,
        hidden=True
    )
    
    # Eileen Brent x2 (para CREATE_SET especial)
    card_eileen1 = models.CardsXGame(
        id_game=game.id,
        id_card=9,
        is_in=CardState.HAND,
        position=3,
        player_id=player1.id,
        hidden=True
    )
    card_eileen2 = models.CardsXGame(
        id_game=game.id,
        id_card=9,
        is_in=CardState.HAND,
        position=4,
        player_id=player1.id,
        hidden=True
    )
    
    # Point Suspicions (para EVENT)
    card_event = models.CardsXGame(
        id_game=game.id,
        id_card=17,
        is_in=CardState.HAND,
        position=5,
        player_id=player1.id,
        hidden=True
    )
    
    # Ariadne Oliver (para ADD_TO_SET especial)
    card_oliver = models.CardsXGame(
        id_game=game.id,
        id_card=5,
        is_in=CardState.HAND,
        position=6,
        player_id=player1.id,
        hidden=True
    )
    
    # Miss Marple (para ADD_TO_SET normal)
    card_marple = models.CardsXGame(
        id_game=game.id,
        id_card=6,
        is_in=CardState.HAND,
        position=7,
        player_id=player1.id,
        hidden=True
    )
    
    # Set existente de Poirot de player2 (para ADD_TO_SET de Oliver)
    card_poirot1 = models.CardsXGame(
        id_game=game.id,
        id_card=11,
        is_in=CardState.DETECTIVE_SET,
        position=1,
        player_id=player2.id,
        hidden=False
    )
    card_poirot2 = models.CardsXGame(
        id_game=game.id,
        id_card=11,
        is_in=CardState.DETECTIVE_SET,
        position=1,
        player_id=player2.id,
        hidden=False
    )
    
    # Discard inicial
    discard1 = models.CardsXGame(
        id_game=game.id,
        id_card=1,
        is_in=CardState.DISCARD,
        position=1,
        player_id=None,
        hidden=False
    )
    discard2 = models.CardsXGame(
        id_game=game.id,
        id_card=2,
        is_in=CardState.DISCARD,
        position=2,
        player_id=None,
        hidden=False
    )
    
    db.add_all([
        card_pyne1, card_pyne2, card_eileen1, card_eileen2,
        card_event, card_oliver, card_marple,
        card_poirot1, card_poirot2,
        discard1, discard2
    ])
    db.commit()
    
    return {
        "game": game,
        "room": room,
        "player1": player1,
        "player2": player2,
        "turn": turn,
        "card_pyne1": card_pyne1,
        "card_pyne2": card_pyne2,
        "card_eileen1": card_eileen1,
        "card_eileen2": card_eileen2,
        "card_event": card_event,
        "card_oliver": card_oliver,
        "card_marple": card_marple,
        "card_poirot1": card_poirot1,
        "card_poirot2": card_poirot2,
    }


def create_cancelled_action(db: Session, game_id: int, player_id: int, action_type_name: str):
    """
    Helper para crear una acción CANCELLED con todo el contexto NSF
    
    Crea:
    - action_xxx: La acción original (result=CANCELLED)
    - action_yyy: NSF_START
    - action_zzz: INSTANT_PLAY (NSF jugado)
    - NSF card en discard en position 1
    
    Returns:
        tuple: (action_xxx_id, action_yyy_id, action_zzz_id)
    """
    # XXX: Acción original que fue cancelada
    action_xxx = models.ActionsPerTurn(
        id_game=game_id,
        player_id=player_id,
        action_type=ActionType.INIT,
        action_name=ActionName.DRAFT_PHASE,
        result=ActionResult.CANCELLED,
        action_time=datetime.now(),
        action_time_end=None,
        parent_action_id=None,
        triggered_by_action_id=None
    )
    db.add(action_xxx)
    db.flush()
    
    # YYY: NSF_START - Inicio de la ventana NSF (usa el mismo player_id del XXX)
    action_yyy = models.ActionsPerTurn(
        id_game=game_id,
        player_id=player_id,  # Mismo jugador que la acción original
        action_type=ActionType.INSTANT,
        action_name=ActionName.INSTANT_START,  # Debe ser INSTANT_START
        result=ActionResult.PENDING,
        action_time=datetime.now(),
        action_time_end=None,
        parent_action_id=None,
        triggered_by_action_id=action_xxx.id
    )
    db.add(action_yyy)
    db.flush()
    
    # ZZZ: INSTANT_PLAY - Jugada de NSF
    action_zzz = models.ActionsPerTurn(
        id_game=game_id,
        player_id=player_id,
        action_type=ActionType.INSTANT,
        action_name=ActionName.DRAFT_PHASE,
        result=ActionResult.PENDING,
        action_time=datetime.now(),
        action_time_end=None,
        parent_action_id=action_yyy.id,
        triggered_by_action_id=action_xxx.id
    )
    db.add(action_zzz)
    
    # NSF card en discard (position 1)
    nsf_card = models.CardsXGame(
        id_game=game_id,
        id_card=13,
        is_in=CardState.DISCARD,
        position=1,
        player_id=None,
        hidden=False
    )
    db.add(nsf_card)
    
    db.commit()
    
    return action_xxx.id, action_yyy.id, action_zzz.id


class TestCancelNSFAction:
    """Tests para cancel_nsf_action()"""
    
    def test_cancel_nsf_action_validates_room_exists(self, db: Session, setup_nsf_cancel_service_test):
        """Debe lanzar error si el room no existe"""
        data = setup_nsf_cancel_service_test
        
        service = NotSoFastService(db)
        
        with pytest.raises(HTTPException) as exc_info:
            service.cancel_nsf_action(
                room_id=99999,  # Room inexistente
                action_id=1,
                player_id=data["player1"].id,
                card_ids=[data["card_pyne1"].id],
                additional_data={"actionType": "CREATE_SET"}
            )
        
        assert exc_info.value.status_code == 404
        assert "Room not found" in str(exc_info.value.detail)
    
    def test_cancel_nsf_action_validates_player_exists(self, db: Session, setup_nsf_cancel_service_test):
        """Debe lanzar error si el jugador no existe"""
        data = setup_nsf_cancel_service_test
        
        service = NotSoFastService(db)
        
        with pytest.raises(HTTPException) as exc_info:
            service.cancel_nsf_action(
                room_id=data["room"].id,
                action_id=1,
                player_id=99999,  # Player inexistente
                card_ids=[data["card_pyne1"].id],
                additional_data={"actionType": "CREATE_SET"}
            )
        
        assert exc_info.value.status_code == 404
        assert "Player not found" in str(exc_info.value.detail)
    
    def test_cancel_nsf_action_validates_action_exists(self, db: Session, setup_nsf_cancel_service_test):
        """Debe lanzar error si la acción no existe"""
        data = setup_nsf_cancel_service_test
        
        service = NotSoFastService(db)
        
        with pytest.raises(HTTPException) as exc_info:
            service.cancel_nsf_action(
                room_id=data["room"].id,
                action_id=99999,  # Acción inexistente
                player_id=data["player1"].id,
                card_ids=[data["card_pyne1"].id],
                additional_data={"actionType": "CREATE_SET"}
            )
        
        assert exc_info.value.status_code == 404
        assert "Action not found" in str(exc_info.value.detail)
    
    def test_cancel_nsf_action_validates_action_is_cancelled(self, db: Session, setup_nsf_cancel_service_test):
        """Debe lanzar error si la acción no está CANCELLED"""
        data = setup_nsf_cancel_service_test
        game_id = data["game"].id
        player1 = data["player1"]
        
        # Crear acción con result=CONTINUE (no cancelada)
        action = models.ActionsPerTurn(
            id_game=game_id,
            player_id=player1.id,
            action_type=ActionType.INIT,
            action_name=ActionName.DRAFT_PHASE,
            result=ActionResult.CONTINUE,  # No está cancelada
            action_time=datetime.now(),
            action_time_end=None,
            parent_action_id=None,
            triggered_by_action_id=None
        )
        db.add(action)
        db.commit()
        
        service = NotSoFastService(db)
        
        with pytest.raises(HTTPException) as exc_info:
            service.cancel_nsf_action(
                room_id=data["room"].id,
                action_id=action.id,
                player_id=player1.id,
                card_ids=[data["card_pyne1"].id],
                additional_data={"actionType": "CREATE_SET"}
            )
        
        assert exc_info.value.status_code == 400
        assert "cancelled" in str(exc_info.value.detail).lower()


class TestCancelCreateSet:
    """Tests para _cancel_create_set()"""
    
    def test_cancel_create_set_normal(self, db: Session, setup_nsf_cancel_service_test):
        """Debe crear set sin efecto cuando no tiene Eileen Brent"""
        data = setup_nsf_cancel_service_test
        game_id = data["game"].id
        player1 = data["player1"]
        room_id = data["room"].id
        
        # Crear acción cancelada
        action_id, _, _ = create_cancelled_action(db, game_id, player1.id, "CREATE_SET")
        
        service = NotSoFastService(db)
        
        message = service.cancel_nsf_action(
            room_id=room_id,
            action_id=action_id,
            player_id=player1.id,
            card_ids=[data["card_pyne1"].id, data["card_pyne2"].id],
            additional_data={"actionType": "CREATE_SET"}
        )
        
        db.commit()
        
        # Verificar mensaje
        assert "ServicePlayer1" in message
        assert "bajar set de detective" in message
        assert "Parker Pyne" in message
        assert "creado pero efecto no realizado" in message
        
        # Verificar que las cartas están en DETECTIVE_SET
        card1 = crud.get_card_xgame_by_id(db, data["card_pyne1"].id)
        card2 = crud.get_card_xgame_by_id(db, data["card_pyne2"].id)
        
        assert card1.is_in == CardState.DETECTIVE_SET
        assert card1.position == 1
        assert card1.hidden is False
        
        assert card2.is_in == CardState.DETECTIVE_SET
        assert card2.position == 1
        assert card2.hidden is False
    
    def test_cancel_create_set_with_eileen(self, db: Session, setup_nsf_cancel_service_test):
        """Debe dejar cartas en HAND cuando el set contiene Eileen Brent"""
        data = setup_nsf_cancel_service_test
        game_id = data["game"].id
        player1 = data["player1"]
        room_id = data["room"].id
        
        # Crear acción cancelada
        action_id, _, _ = create_cancelled_action(db, game_id, player1.id, "CREATE_SET")
        
        service = NotSoFastService(db)
        
        message = service.cancel_nsf_action(
            room_id=room_id,
            action_id=action_id,
            player_id=player1.id,
            card_ids=[data["card_eileen1"].id, data["card_eileen2"].id],
            additional_data={"actionType": "CREATE_SET"}
        )
        
        db.commit()
        
        # Verificar mensaje
        assert "ServicePlayer1" in message
        assert "bajar set de detective" in message
        assert "Eileen vuelve a la mano" in message
        
        # Verificar que las cartas siguen en HAND
        card1 = crud.get_card_xgame_by_id(db, data["card_eileen1"].id)
        card2 = crud.get_card_xgame_by_id(db, data["card_eileen2"].id)
        
        assert card1.is_in == CardState.HAND
        assert card2.is_in == CardState.HAND


class TestCancelEvent:
    """Tests para _cancel_event()"""
    
    def test_cancel_event_places_card_below_nsf(self, db: Session, setup_nsf_cancel_service_test):
        """Debe colocar la carta evento debajo de las NSF en el discard"""
        data = setup_nsf_cancel_service_test
        game_id = data["game"].id
        player1 = data["player1"]
        room_id = data["room"].id
        
        # Crear acción cancelada (ya tiene 1 NSF en discard en posición 1)
        action_id, _, _ = create_cancelled_action(db, game_id, player1.id, "EVENT")
        
        service = NotSoFastService(db)
        
        message = service.cancel_nsf_action(
            room_id=room_id,
            action_id=action_id,
            player_id=player1.id,
            card_ids=[data["card_event"].id],
            additional_data={"actionType": "EVENT"}
        )
        
        db.commit()
        
        # Verificar mensaje
        assert "ServicePlayer1" in message
        assert "carta evento" in message
        assert "Point" in message  # Point Suspicions
        assert "mazo de descarte" in message
        
        # Verificar que la carta está en DISCARD en posición 2 (debajo de NSF que está en pos 1)
        card = crud.get_card_xgame_by_id(db, data["card_event"].id)
        
        assert card.is_in == CardState.DISCARD
        assert card.position == 2  # NSF en 1, Point en 2
        assert card.player_id is None
        assert card.hidden is False


class TestCancelAddToSet:
    """Tests para _cancel_add_to_set()"""
    
    def test_cancel_add_to_set_normal(self, db: Session, setup_nsf_cancel_service_test):
        """Debe agregar carta normal a set propio sin efecto"""
        data = setup_nsf_cancel_service_test
        game_id = data["game"].id
        player1 = data["player1"]
        room_id = data["room"].id
        
        # Crear set existente de Parker Pyne
        crud.update_single_card_state(db, data["card_pyne1"].id, CardState.DETECTIVE_SET, 1, player1.id, False)
        crud.update_single_card_state(db, data["card_pyne2"].id, CardState.DETECTIVE_SET, 1, player1.id, False)
        db.commit()
        
        # Crear acción cancelada
        action_id, _, _ = create_cancelled_action(db, game_id, player1.id, "ADD_TO_SET")
        
        service = NotSoFastService(db)
        
        message = service.cancel_nsf_action(
            room_id=room_id,
            action_id=action_id,
            player_id=player1.id,
            card_ids=[data["card_marple"].id],  # Agregar Miss Marple
            additional_data={
                "actionType": "ADD_TO_SET",
                "setPosition": 1
            }
        )
        
        db.commit()
        
        # Verificar mensaje
        assert "ServicePlayer1" in message
        assert "agregar carta a set" in message
        assert "ampliado pero efecto no realizado" in message
        
        # Verificar que la carta está en el set
        card = crud.get_card_xgame_by_id(db, data["card_marple"].id)
        
        assert card.is_in == CardState.DETECTIVE_SET
        assert card.position == 1
        assert card.player_id == player1.id
        assert card.hidden is False
    
    def test_cancel_add_to_set_with_eileen(self, db: Session, setup_nsf_cancel_service_test):
        """Debe dejar Eileen en HAND cuando se intenta agregar a set"""
        data = setup_nsf_cancel_service_test
        game_id = data["game"].id
        player1 = data["player1"]
        room_id = data["room"].id
        
        # Crear set existente
        crud.update_single_card_state(db, data["card_pyne1"].id, CardState.DETECTIVE_SET, 1, player1.id, False)
        db.commit()
        
        # Crear acción cancelada
        action_id, _, _ = create_cancelled_action(db, game_id, player1.id, "ADD_TO_SET")
        
        service = NotSoFastService(db)
        
        message = service.cancel_nsf_action(
            room_id=room_id,
            action_id=action_id,
            player_id=player1.id,
            card_ids=[data["card_eileen1"].id],  # Agregar Eileen
            additional_data={
                "actionType": "ADD_TO_SET",
                "setPosition": 1
            }
        )
        
        db.commit()
        
        # Verificar mensaje
        assert "ServicePlayer1" in message
        assert "agregar carta a set" in message
        assert "Eileen vuelve a la mano" in message
        
        # Verificar que Eileen sigue en HAND
        card = crud.get_card_xgame_by_id(db, data["card_eileen1"].id)
        
        assert card.is_in == CardState.HAND
    
    def test_cancel_add_to_set_with_oliver_to_other_set(self, db: Session, setup_nsf_cancel_service_test):
        """Debe agregar Ariadne Oliver al set de otro jugador sin efecto"""
        data = setup_nsf_cancel_service_test
        game_id = data["game"].id
        player1 = data["player1"]
        player2 = data["player2"]
        room_id = data["room"].id
        
        # player2 ya tiene set de Poirot en position 1
        
        # Crear acción cancelada
        action_id, _, _ = create_cancelled_action(db, game_id, player1.id, "ADD_TO_SET")
        
        service = NotSoFastService(db)
        
        message = service.cancel_nsf_action(
            room_id=room_id,
            action_id=action_id,
            player_id=player1.id,
            card_ids=[data["card_oliver"].id],  # Agregar Oliver
            additional_data={
                "actionType": "ADD_TO_SET",
                "setPosition": 1,
                "player_target": player2.id  # Set de player2
            }
        )
        
        db.commit()
        
        # Verificar mensaje
        assert "ServicePlayer1" in message
        assert "agregar carta a set" in message
        assert "Oliver agregada a set" in message
        assert "Hercule Poirot" in message  # Nombre del set
        assert "ServicePlayer2" in message  # Dueño del set
        assert "no se realiza su efecto" in message
        
        # Verificar que Oliver está en el set de player2
        card = crud.get_card_xgame_by_id(db, data["card_oliver"].id)
        
        assert card.is_in == CardState.DETECTIVE_SET
        assert card.position == 1
        assert card.player_id == player2.id  # Ahora pertenece a player2
        assert card.hidden is False
