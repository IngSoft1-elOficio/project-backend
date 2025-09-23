import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db import models, crud, database

# Configuración de la base de datos de test (usa la misma que develop)
SQLALCHEMY_DATABASE_URL = database.SQLALCHEMY_DATABASE_URL
engine = create_engine(SQLALCHEMY_DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture
def db_session():
    session = TestingSessionLocal()
    yield session
    session.close()

# Test para crear una sala
def test_create_room(db_session):
    room_data = {
        "name": "Sala Test",
        "status": "waiting"
    }
    room = crud.create_room(db_session, room_data)
    assert room.id is not None
    assert room.name == "Sala Test"
    assert room.status == "waiting"

# Test para obtener una sala por id
def test_get_room_by_id(db_session):
    room_data = {"name": "Sala Test2", "status": "waiting"}
    room = crud.create_room(db_session, room_data)
    fetched = crud.get_room_by_id(db_session, room.id)
    assert fetched is not None
    assert fetched.name == room_data["name"]

# Test para listar salas
def test_list_rooms(db_session):
    crud.create_room(db_session, {"name": "Sala1", "status": "waiting"})
    crud.create_room(db_session, {"name": "Sala2", "status": "active"})
    rooms = crud.list_rooms(db_session)
    assert len(rooms) >= 2
    waiting_rooms = crud.list_rooms(db_session, status="waiting")
    assert any(r.status == "waiting" for r in waiting_rooms)

# Test para actualizar el estado de la sala
def test_update_room_status(db_session):
    room = crud.create_room(db_session, {"name": "Sala3", "status": "waiting"})
    updated = crud.update_room_status(db_session, room.id, "active")
    assert updated.status == "active"
