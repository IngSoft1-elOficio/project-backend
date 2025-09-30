import pytest
import os

@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Configura variables de entorno mínimas para evitar errores de importación"""
    os.environ["DATABASE_URL"] = "sqlite:///:memory:"
    os.environ.setdefault("SECRET_KEY", "test-secret-key-123")
    
    yield