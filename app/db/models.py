from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Enum,
    UniqueConstraint,
    text
)
from sqlalchemy.orm import relationship
from .database import Base
import enum


# ========================
# ENUMS
# ========================

class CardType(str, enum.Enum):
    EVENT = "EVENT"
    SECRET = "SECRET"
    INSTANT = "INSTANT"
    DEVIUOS = "DEVIUOS"
    DETECTIVE = "DETECTIVE"
    END = "END"


class RoomStatus(str, enum.Enum):
    WAITING = "WAITING"
    INGAME = "INGAME"
    FINISH = "FINISH"


class CardState(str, enum.Enum):
    DECK = "DECK"
    DRAFT = "DRAFT"
    DISCARD = "DISCARD"
    SECRET_SET = "SECRET_SET"
    DETECTIVE_SET = "DETECTIVE_SET"
    HAND = "HAND"
    REMOVED = "REMOVED"  # Para cartas removidas del juego


class TurnStatus(str, enum.Enum):
    IN_PROGRESS = "IN_PROGRESS"
    FINISHED = "FINISHED"


class ActionType(str, enum.Enum):
    EVENT_CARD = "EVENT_CARD"
    DETECTIVE_SET = "DETECTIVE_SET"
    ADD_DETECTIVE = "ADD_DETECTIVE"
    DISCARD = "DISCARD"
    DRAW = "DRAW"
    INSTANT = "INSTANT"
    REVEAL_SECRET = "REVEAL_SECRET"
    HIDE_SECRET = "HIDE_SECRET"
    VOTE = "VOTE"
    CARD_EXCHANGE = "CARD_EXCHANGE"
    MOVE_CARD = "MOVE_CARD"
    STEAL_SET = "STEAL_SET"


class ActionResult(str, enum.Enum):
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


class Direction(str, enum.Enum):
    LEFT = "LEFT"
    RIGHT = "RIGHT"


class SourcePile(str, enum.Enum):
    DRAFT_PILE = "DRAFT_PILE"
    DRAW_PILE = "DRAW_PILE"
    DISCARD_PILE = "DISCARD_PILE"


# ========================
# TABLES
# ========================

class Game(Base):
    __tablename__ = "game"
    
    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    player_turn_id = Column(Integer, ForeignKey("player.id"))

    rooms = relationship("Room", back_populates="game")
    cards = relationship("CardsXGame", back_populates="game")
    current_player = relationship("Player", foreign_keys=[player_turn_id])
    turns = relationship("Turn", back_populates="game")


class Card(Base):
    __tablename__ = "card"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    name = Column(String(200), nullable=False)
    description = Column(String(500), nullable=False)
    type = Column(Enum(CardType), nullable=False)
    img_src = Column(String(500), nullable=False)
    qty = Column(Integer, nullable=False, default=0)

    games = relationship("CardsXGame", back_populates="card")


class Room(Base):
    __tablename__ = "room"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    name = Column(String(200), nullable=False)
    players_min = Column(Integer, nullable=False, default=2)
    players_max = Column(Integer, nullable=False, default=6)
    password = Column(String(500))
    status = Column(Enum(RoomStatus), nullable=False)
    id_game = Column(Integer, ForeignKey("game.id"))

    game = relationship("Game", back_populates="rooms")
    players = relationship("Player", back_populates="room")


class Player(Base):
    __tablename__ = "player"
    __table_args__ = (
        UniqueConstraint("name", "avatar_src", name="uq_player_name_avatar"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    name = Column(String(200), nullable=False)
    avatar_src = Column(String(500), nullable=False)
    birthdate = Column(Date, nullable=False)
    id_room = Column(Integer, ForeignKey("room.id"))
    is_host = Column(Boolean, default=False)
    order = Column(Integer)

    room = relationship("Room", back_populates="players")
    cards = relationship("CardsXGame", back_populates="player")
    turns = relationship("Turn", back_populates="player")


class CardsXGame(Base):
    __tablename__ = "cardsXgame"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    id_game = Column(Integer, ForeignKey("game.id"), nullable=False)
    id_card = Column(Integer, ForeignKey("card.id"), nullable=False)
    is_in = Column(Enum(CardState), nullable=False)
    position = Column(Integer, nullable=False)
    player_id = Column(Integer, ForeignKey("player.id"))
    hidden = Column(Boolean, nullable=False, default=True)

    game = relationship("Game", back_populates="cards")
    card = relationship("Card", back_populates="games")
    player = relationship("Player", back_populates="cards")


class Turn(Base):
    __tablename__ = "turn"
    
    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    number = Column(Integer, nullable=False)
    id_game = Column(Integer, ForeignKey("game.id"), nullable=False)
    player_id = Column(Integer, ForeignKey("player.id"), nullable=False)
    status = Column(Enum(TurnStatus), nullable=False, default=TurnStatus.IN_PROGRESS)
    start_time = Column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    
    game = relationship("Game", back_populates="turns")
    player = relationship("Player", back_populates="turns")
    actions = relationship("ActionsPerTurn", back_populates="turn")


class ActionsPerTurn(Base):
    __tablename__ = "actions_per_turn"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    id_game = Column(Integer, ForeignKey("game.id"), nullable=False)
    turn_id = Column(Integer, ForeignKey("turn.id"))
    player_id = Column(Integer, ForeignKey("player.id"), nullable=False)
    action_time = Column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    action_name = Column(String(40))
    action_type = Column(Enum(ActionType))
    result = Column(Enum(ActionResult), default=ActionResult.PENDING)
    
    # Relaciones entre acciones
    parent_action_id = Column(Integer, ForeignKey("actions_per_turn.id"))
    triggered_by_action_id = Column(Integer, ForeignKey("actions_per_turn.id"))
    
    # Relaciones con jugadores
    player_source = Column(Integer, ForeignKey("player.id"))
    player_target = Column(Integer, ForeignKey("player.id"))
    
    # Contexto de cartas
    secret_target = Column(Integer, ForeignKey("cardsXgame.id"))
    selected_card_id = Column(Integer, ForeignKey("cardsXgame.id"))
    card_given_id = Column(Integer, ForeignKey("cardsXgame.id"))
    card_received_id = Column(Integer, ForeignKey("cardsXgame.id"))
    
    # Contexto de acción
    direction = Column(Enum(Direction))
    source_pile = Column(Enum(SourcePile))
    position_card = Column(Integer)
    selected_set_id = Column(Integer)
    to_be_hidden = Column(Boolean)
    
    # Relaciones
    game = relationship("Game")
    turn = relationship("Turn", back_populates="actions")
    player = relationship("Player", foreign_keys=[player_id])
    source = relationship("Player", foreign_keys=[player_source])
    target = relationship("Player", foreign_keys=[player_target])
    secret = relationship("CardsXGame", foreign_keys=[secret_target])
    selected_card = relationship("CardsXGame", foreign_keys=[selected_card_id])
    card_given = relationship("CardsXGame", foreign_keys=[card_given_id])
    card_received = relationship("CardsXGame", foreign_keys=[card_received_id])
    parent_action = relationship("ActionsPerTurn", remote_side=[id], foreign_keys=[parent_action_id])
    triggered_by = relationship("ActionsPerTurn", remote_side=[id], foreign_keys=[triggered_by_action_id])