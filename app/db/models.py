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


#Checks / Enums
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


# ------------------------
# TABLES
# ------------------------
class Game(Base):
    __tablename__ = "game"
    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    player_turn_id = Column(Integer, ForeignKey("player.id"))

    rooms = relationship("Room", back_populates="game")
    cards = relationship("CardsXGame", back_populates="game")
    current_player = relationship("Player", foreign_keys=[player_turn_id])


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
    #player_qty = Column(Integer, nullable=False)
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


class ActionsPerTurn(Base):
    __tablename__ = "actions_per_turn"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    id_game = Column(Integer, ForeignKey("game.id"), nullable=False)
    action_time = Column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    actionName = Column(String(40))
    player_id = Column(Integer, ForeignKey("player.id"), nullable=False)
    parent_action_id = Column(Integer, ForeignKey("actions_per_turn.id"))
    player_source = Column(Integer, ForeignKey("player.id"))
    player_target = Column(Integer, ForeignKey("player.id"))
    secret_target = Column(Integer, ForeignKey("cardsXgame.id"))
    to_be_hidden = Column(Boolean)

    game = relationship("Game")
    player = relationship("Player", foreign_keys=[player_id])
    source = relationship("Player", foreign_keys=[player_source])
    target = relationship("Player", foreign_keys=[player_target])
    parent_action = relationship("ActionsPerTurn", remote_side=[id])
    secret = relationship("CardsXGame")