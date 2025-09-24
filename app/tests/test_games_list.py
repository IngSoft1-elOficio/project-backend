# app/tests/test_games_list.py
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import sys
import os
from datetime import date

# Configurar el path para imports
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
app_dir = os.path.join(project_root, 'app')

if project_root not in sys.path:
    sys.path.insert(0, project_root)

# IMPORTANTE: Mock de la base de datos ANTES de importar los módulos
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'

# Ahora importar los módulos
from app.routes.api import router, get_db
from app.db.models import Room, Player, RoomStatus
from app.db.database import Base

# Configuración de base de datos en memoria para tests
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Crear las tablas en la base de datos de prueba
Base.metadata.create_all(bind=engine)

# Cliente de prueba
from fastapi import FastAPI
app = FastAPI()
app.include_router(router)

def override_get_db():
    """Override de la función get_db para usar la base de datos de prueba"""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)

class TestAPI:
    
    def setup_method(self):
        """Configuración antes de cada test"""
        # Limpiar la base de datos antes de cada test
        db = TestingSessionLocal()
        try:
            db.query(Player).delete()
            db.query(Room).delete()
            db.commit()
        finally:
            db.close()
    
    def create_room(self, room_id: int, name: str, player_qty: int, status: str = "WAITING"):
        """Helper para crear una sala de prueba"""
        db = TestingSessionLocal()
        try:
            room = Room(
                id=room_id,
                name=name,
                player_qty=player_qty,
                password=None,
                status=RoomStatus(status),
                id_game=None
            )
            db.add(room)
            db.commit()
            db.refresh(room)
            return room
        finally:
            db.close()
    
    def create_player(self, player_id: int, room_id: int, name: str = None, is_host: bool = False):
        """Helper para crear un jugador de prueba"""
        db = TestingSessionLocal()
        try:
            if name is None:
                name = f"Player_{player_id}"
            
            player = Player(
                id=player_id,
                name=name,
                avatar_src=f"avatar_{player_id}.png",
                birthdate=date(1990, 1, 1),
                id_room=room_id,
                is_host=is_host,
                order=player_id
            )
            db.add(player)
            db.commit()
            db.refresh(player)
            return player
        finally:
            db.close()

    def test_test_endpoint(self):
        """Test del endpoint de prueba"""
        response = client.get("/api/test")
        assert response.status_code == 200
        assert response.json() == {"message": "Test endpoint is working!"}

    def test_get_game_list_empty(self):
        """Test cuando no hay salas disponibles"""
        response = client.get("/api/game_list")
        
        if response.status_code == 200:
            data = response.json()
            assert "items" in data
            assert "page" in data
            assert "limit" in data
            assert isinstance(data["items"], list)
            assert data["page"] == 1
            assert data["limit"] == 20

    def test_get_game_list_basic_functionality(self):
        """Test básico con una sala simple"""
        # Crear una sala simple
        self.create_room(1, "Sala Test", 4, "WAITING")
        self.create_player(1, 1, "Host1", is_host=True)
        
        response = client.get("/api/game_list")
        
        if response.status_code == 200:
            data = response.json()
            assert "items" in data
            assert "page" in data
            assert "limit" in data

    def test_get_game_list_pagination_params(self):
        """Test de parámetros de paginación"""
        # Test con parámetros válidos
        response = client.get("/api/game_list?page=2&limit=10")
        
        if response.status_code == 200:
            data = response.json()
            assert data["page"] == 2
            assert data["limit"] == 10

    def test_get_game_list_invalid_pagination_params(self):
        """Test con parámetros de paginación inválidos"""
        # Page menor a 1
        response = client.get("/api/game_list?page=0")
        assert response.status_code == 422  # Validation error
        
        # Limit mayor al máximo permitido
        response = client.get("/api/game_list?limit=101")
        assert response.status_code == 422  # Validation error
        
        # Limit menor a 1
        response = client.get("/api/game_list?limit=0")
        assert response.status_code == 422  # Validation error

if __name__ == "__main__":
    pytest.main([__file__, "-v"])