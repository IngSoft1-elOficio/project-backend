"""
Tests para las nuevas funciones del CRUD agregadas para el flujo de NSF cancel

Funciones testeadas:
- get_card_xgame_by_id
- increment_discard_positions_from
- update_single_card_state
- get_detective_set_cards_by_position
- check_set_contains_card
- get_player_name
- get_card_name
- get_detective_set_name
"""
import pytest
from datetime import date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.db import models, crud
from app.db.models import CardState
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
        # Cartas genericas para discard/deck
        models.Card(id=1, name="Generic Card 1", description="Test card", type="SECRET", img_src="/cards/generic1.png", qty=1),
        models.Card(id=2, name="Generic Card 2", description="Test card", type="SECRET", img_src="/cards/generic2.png", qty=1),
    ]
    db.add_all(cards)
    db.commit()
import pytest
from sqlalchemy.orm import Session
from datetime import datetime, date

from app.db import crud, models
from app.db.models import CardState, CardType


@pytest.fixture
def setup_nsf_cancel_game(db: Session):
    """
    Fixture que crea un juego con jugadores y cartas para testear cancelación NSF.
    """
    # Crear juego
    game = models.Game(player_turn_id=None)
    db.add(game)
    db.flush()
    
    # Crear room
    room = models.Room(
        name="NSF Test Room",
        players_min=2,
        players_max=6,
        status=models.RoomStatus.INGAME,
        id_game=game.id
    )
    db.add(room)
    db.flush()
    
    # Crear jugadores
    player1 = models.Player(
        name="TestPlayer1",
        avatar_src="/avatars/p1.jpg",
        birthdate=date(1990, 1, 1),
        id_room=room.id,
        is_host=True,
        order=1
    )
    player2 = models.Player(
        name="TestPlayer2",
        avatar_src="/avatars/p2.jpg",
        birthdate=date(1990, 2, 2),
        id_room=room.id,
        is_host=False,
        order=2
    )
    db.add_all([player1, player2])
    db.flush()
    
    # Actualizar player_turn_id
    game.player_turn_id = player1.id
    db.flush()
    
    # Crear cartas en mano de player1
    card1 = models.CardsXGame(
        id_game=game.id,
        id_card=7,  # Parker Pyne
        is_in=CardState.HAND,
        position=1,
        player_id=player1.id,
        hidden=True
    )
    card2 = models.CardsXGame(
        id_game=game.id,
        id_card=7,  # Parker Pyne
        is_in=CardState.HAND,
        position=2,
        player_id=player1.id,
        hidden=True
    )
    card3 = models.CardsXGame(
        id_game=game.id,
        id_card=17,  # Point Suspicions
        is_in=CardState.HAND,
        position=3,
        player_id=player1.id,
        hidden=True
    )
    card4 = models.CardsXGame(
        id_game=game.id,
        id_card=9,  # Eileen Brent
        is_in=CardState.HAND,
        position=4,
        player_id=player1.id,
        hidden=True
    )
    
    # Cartas en discard
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
    discard3 = models.CardsXGame(
        id_game=game.id,
        id_card=13,  # NSF
        is_in=CardState.DISCARD,
        position=3,
        player_id=None,
        hidden=False
    )
    
    db.add_all([card1, card2, card3, card4, discard1, discard2, discard3])
    db.commit()
    
    return {
        "game": game,
        "room": room,
        "player1": player1,
        "player2": player2,
        "cards": [card1, card2, card3, card4],
        "discard": [discard1, discard2, discard3]
    }


class TestGetCardXGameById:
    """Tests para crud.get_card_xgame_by_id()"""
    
    def test_get_existing_card(self, db: Session, setup_nsf_cancel_game):
        """Debe retornar una carta existente"""
        data = setup_nsf_cancel_game
        card = data["cards"][0]
        
        result = crud.get_card_xgame_by_id(db, card.id)
        
        assert result is not None
        assert result.id == card.id
        assert result.id_card == 7  # Parker Pyne
        assert result.is_in == CardState.HAND
        assert result.player_id == data["player1"].id
    
    def test_get_nonexistent_card(self, db: Session):
        """Debe retornar None para carta inexistente"""
        result = crud.get_card_xgame_by_id(db, 99999)
        
        assert result is None


class TestIncrementDiscardPositionsFrom:
    """Tests para crud.increment_discard_positions_from()"""
    
    def test_increment_positions_from_middle(self, db: Session, setup_nsf_cancel_game):
        """Debe incrementar posiciones desde una posición específica"""
        data = setup_nsf_cancel_game
        game_id = data["game"].id
        
        # Estado inicial: discard tiene [1, 2, 3]
        # Incrementar desde posición 2
        crud.increment_discard_positions_from(db, game_id, 2)
        db.commit()
        
        # Verificar resultados
        discard_cards = db.query(models.CardsXGame).filter(
            models.CardsXGame.id_game == game_id,
            models.CardsXGame.is_in == CardState.DISCARD
        ).order_by(models.CardsXGame.position).all()
        
        assert discard_cards[0].position == 1  # No cambió
        assert discard_cards[1].position == 3  # 2 → 3
        assert discard_cards[2].position == 4  # 3 → 4
    
    def test_increment_from_position_1(self, db: Session, setup_nsf_cancel_game):
        """Debe incrementar todas las posiciones cuando from_position=1"""
        data = setup_nsf_cancel_game
        game_id = data["game"].id
        
        crud.increment_discard_positions_from(db, game_id, 1)
        db.commit()
        
        discard_cards = db.query(models.CardsXGame).filter(
            models.CardsXGame.id_game == game_id,
            models.CardsXGame.is_in == CardState.DISCARD
        ).order_by(models.CardsXGame.position).all()
        
        assert discard_cards[0].position == 2  # 1 → 2
        assert discard_cards[1].position == 3  # 2 → 3
        assert discard_cards[2].position == 4  # 3 → 4
    
    def test_increment_does_not_affect_other_states(self, db: Session, setup_nsf_cancel_game):
        """No debe afectar cartas que no están en DISCARD"""
        data = setup_nsf_cancel_game
        game_id = data["game"].id
        
        # Guardar estado original de cartas en HAND
        hand_cards_before = db.query(models.CardsXGame).filter(
            models.CardsXGame.id_game == game_id,
            models.CardsXGame.is_in == CardState.HAND
        ).all()
        
        positions_before = sorted([c.position for c in hand_cards_before])
        
        # Incrementar discard
        crud.increment_discard_positions_from(db, game_id, 1)
        db.commit()
        
        # Verificar que cartas en HAND no cambiaron
        hand_cards_after = db.query(models.CardsXGame).filter(
            models.CardsXGame.id_game == game_id,
            models.CardsXGame.is_in == CardState.HAND
        ).all()
        
        positions_after = sorted([c.position for c in hand_cards_after])
        
        assert positions_before == positions_after


class TestUpdateSingleCardState:
    """Tests para crud.update_single_card_state()"""
    
    def test_update_card_to_discard(self, db: Session, setup_nsf_cancel_game):
        """Debe actualizar una carta de HAND a DISCARD"""
        data = setup_nsf_cancel_game
        card = data["cards"][0]
        
        result = crud.update_single_card_state(
            db=db,
            card_xgame_id=card.id,
            new_state=CardState.DISCARD,
            new_position=10,
            player_id=None,
            hidden=False
        )
        
        assert result is not None
        
        db.commit()
        
        updated_card = crud.get_card_xgame_by_id(db, card.id)
        
        assert updated_card.is_in == CardState.DISCARD
        assert updated_card.position == 10
        assert updated_card.player_id is None
        assert updated_card.hidden is False
    
    def test_update_card_to_detective_set(self, db: Session, setup_nsf_cancel_game):
        """Debe actualizar una carta de HAND a DETECTIVE_SET"""
        data = setup_nsf_cancel_game
        card = data["cards"][0]
        player1 = data["player1"]
        
        result = crud.update_single_card_state(
            db=db,
            card_xgame_id=card.id,
            new_state=CardState.DETECTIVE_SET,
            new_position=1,
            player_id=player1.id,
            hidden=False
        )
        
        assert result is not None
        
        db.commit()
        
        updated_card = crud.get_card_xgame_by_id(db, card.id)
        
        assert updated_card.is_in == CardState.DETECTIVE_SET
        assert updated_card.position == 1
        assert updated_card.player_id == player1.id
        assert updated_card.hidden is False
    
    def test_update_nonexistent_card(self, db: Session):
        """Debe retornar None si la carta no existe"""
        result = crud.update_single_card_state(
            db=db,
            card_xgame_id=99999,
            new_state=CardState.DISCARD,
            new_position=1,
            player_id=None,
            hidden=False
        )
        
        assert result is None


class TestGetDetectiveSetCardsByPosition:
    """Tests para crud.get_detective_set_cards_by_position()"""
    
    def test_get_detective_set_cards(self, db: Session, setup_nsf_cancel_game):
        """Debe retornar todas las cartas de un set específico"""
        data = setup_nsf_cancel_game
        game_id = data["game"].id
        player1 = data["player1"]
        
        # Crear un set de detectives
        card1 = data["cards"][0]
        card2 = data["cards"][1]
        
        crud.update_single_card_state(db, card1.id, CardState.DETECTIVE_SET, 1, player1.id, False)
        crud.update_single_card_state(db, card2.id, CardState.DETECTIVE_SET, 1, player1.id, False)
        db.commit()
        
        # Obtener cartas del set
        set_cards = crud.get_detective_set_cards_by_position(db, game_id, player1.id, 1)
        
        assert len(set_cards) == 2
        assert all(c.is_in == CardState.DETECTIVE_SET for c in set_cards)
        assert all(c.position == 1 for c in set_cards)
        assert all(c.player_id == player1.id for c in set_cards)
    
    def test_get_nonexistent_set(self, db: Session, setup_nsf_cancel_game):
        """Debe retornar lista vacía si el set no existe"""
        data = setup_nsf_cancel_game
        game_id = data["game"].id
        player1 = data["player1"]
        
        set_cards = crud.get_detective_set_cards_by_position(db, game_id, player1.id, 99)
        
        assert len(set_cards) == 0
    
    def test_get_set_multiple_positions(self, db: Session, setup_nsf_cancel_game):
        """Debe distinguir entre sets en diferentes posiciones"""
        data = setup_nsf_cancel_game
        game_id = data["game"].id
        player1 = data["player1"]
        
        # Crear dos sets diferentes
        card1 = data["cards"][0]
        card2 = data["cards"][1]
        
        crud.update_single_card_state(db, card1.id, CardState.DETECTIVE_SET, 1, player1.id, False)
        crud.update_single_card_state(db, card2.id, CardState.DETECTIVE_SET, 2, player1.id, False)
        db.commit()
        
        # Obtener set position 1
        set1_cards = crud.get_detective_set_cards_by_position(db, game_id, player1.id, 1)
        assert len(set1_cards) == 1
        assert set1_cards[0].id == card1.id
        
        # Obtener set position 2
        set2_cards = crud.get_detective_set_cards_by_position(db, game_id, player1.id, 2)
        assert len(set2_cards) == 1
        assert set2_cards[0].id == card2.id


class TestCheckSetContainsCard:
    """Tests para crud.check_set_contains_card()"""
    
    def test_set_contains_specific_card(self, db: Session, setup_nsf_cancel_game):
        """Debe retornar True si el set contiene la carta específica (Eileen Brent)"""
        data = setup_nsf_cancel_game
        
        # Usar la carta Eileen Brent que ya existe
        card_eileen = data["cards"][3]  # id_card=9
        card_pyne = data["cards"][0]    # id_card=7
        
        card_ids = [card_eileen.id, card_pyne.id]
        
        result = crud.check_set_contains_card(db, card_ids, 9)  # Buscar Eileen (id=9)
        
        assert result is True
    
    def test_set_does_not_contain_card(self, db: Session, setup_nsf_cancel_game):
        """Debe retornar False si el set no contiene la carta"""
        data = setup_nsf_cancel_game
        
        # Set solo con Parker Pyne (id=7)
        card1 = data["cards"][0]
        card2 = data["cards"][1]
        
        card_ids = [card1.id, card2.id]
        
        result = crud.check_set_contains_card(db, card_ids, 9)  # Buscar Eileen (id=9)
        
        assert result is False
    
    def test_empty_card_list(self, db: Session):
        """Debe retornar False si la lista de cartas está vacía"""
        result = crud.check_set_contains_card(db, [], 9)
        
        assert result is False


class TestGetPlayerName:
    """Tests para crud.get_player_name()"""
    
    def test_get_existing_player_name(self, db: Session, setup_nsf_cancel_game):
        """Debe retornar el nombre de un jugador existente"""
        data = setup_nsf_cancel_game
        player1 = data["player1"]
        
        result = crud.get_player_name(db, player1.id)
        
        assert result == "TestPlayer1"
    
    def test_get_nonexistent_player_name(self, db: Session):
        """Debe retornar 'Unknown Player' si el jugador no existe"""
        result = crud.get_player_name(db, 99999)
        
        assert result == "Unknown Player"


class TestGetCardName:
    """Tests para crud.get_card_name()"""
    
    def test_get_existing_card_name(self, db: Session):
        """Debe retornar el nombre de una carta existente"""
        # Parker Pyne tiene id=7
        result = crud.get_card_name(db, 7)
        
        assert result == "Parker Pyne"
    
    def test_get_nsf_card_name(self, db: Session):
        """Debe retornar el nombre de la carta NSF"""
        result = crud.get_card_name(db, 13)
        
        assert result == "Not so fast"
    
    def test_get_nonexistent_card_name(self, db: Session):
        """Debe retornar 'Unknown Card' si la carta no existe"""
        result = crud.get_card_name(db, 99999)
        
        assert result == "Unknown Card"


class TestGetDetectiveSetName:
    """Tests para crud.get_detective_set_name()"""
    
    def test_get_parker_pyne_set_name(self, db: Session, setup_nsf_cancel_game):
        """Debe retornar 'Parker Pyne' para un set de Parker Pyne"""
        data = setup_nsf_cancel_game
        
        # Set de 2 Parker Pyne
        card1 = data["cards"][0]  # id_card=7
        card2 = data["cards"][1]  # id_card=7
        
        card_ids = [card1.id, card2.id]
        
        result = crud.get_detective_set_name(db, card_ids)
        
        assert result == "Parker Pyne"
    
    def test_get_set_name_with_wildcard(self, db: Session, setup_nsf_cancel_game):
        """Debe ignorar Harley Quinn y retornar el nombre del detective"""
        data = setup_nsf_cancel_game
        game_id = data["game"].id
        player1 = data["player1"]
        
        # Crear set con Poirot + Harley Quinn
        card_poirot = models.CardsXGame(
            id_game=game_id,
            id_card=11,  # Hercule Poirot
            is_in=CardState.HAND,
            position=5,
            player_id=player1.id,
            hidden=True
        )
        card_harley = models.CardsXGame(
            id_game=game_id,
            id_card=4,  # Harley Quinn
            is_in=CardState.HAND,
            position=6,
            player_id=player1.id,
            hidden=True
        )
        db.add_all([card_poirot, card_harley])
        db.commit()
        
        card_ids = [card_poirot.id, card_harley.id]
        
        result = crud.get_detective_set_name(db, card_ids)
        
        assert result == "Hercule Poirot"
    
    def test_get_tommy_set_name(self, db: Session, setup_nsf_cancel_game):
        """Debe retornar 'Hermanos Beresford' para set con Tommy"""
        data = setup_nsf_cancel_game
        game_id = data["game"].id
        player1 = data["player1"]
        
        # Crear set solo con Tommy
        card_tommy = models.CardsXGame(
            id_game=game_id,
            id_card=8,  # Tommy Beresford
            is_in=CardState.HAND,
            position=5,
            player_id=player1.id,
            hidden=True
        )
        db.add(card_tommy)
        db.commit()
        
        card_ids = [card_tommy.id, card_tommy.id]  # Simular 2 Tommys
        
        result = crud.get_detective_set_name(db, card_ids)
        
        assert result == "Hermanos Beresford"
    
    def test_get_tuppence_set_name(self, db: Session, setup_nsf_cancel_game):
        """Debe retornar 'Hermanos Beresford' para set con Tuppence"""
        data = setup_nsf_cancel_game
        game_id = data["game"].id
        player1 = data["player1"]
        
        # Crear set solo con Tuppence
        card_tuppence = models.CardsXGame(
            id_game=game_id,
            id_card=10,  # Tuppence Beresford
            is_in=CardState.HAND,
            position=5,
            player_id=player1.id,
            hidden=True
        )
        db.add(card_tuppence)
        db.commit()
        
        card_ids = [card_tuppence.id]
        
        result = crud.get_detective_set_name(db, card_ids)
        
        assert result == "Hermanos Beresford"
    
    def test_get_unknown_detective_for_empty_list(self, db: Session):
        """Debe retornar 'Unknown Detective' si la lista está vacía"""
        result = crud.get_detective_set_name(db, [])
        
        assert result == "Unknown Detective"
