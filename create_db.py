from app.db.database import engine, Base
import app.db.models 

Base.metadata.create_all(bind=engine)
print("Tablas creadas automáticamente en la base de datos.")