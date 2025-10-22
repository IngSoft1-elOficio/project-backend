# project-backend

# DB Setup
## Pre-requisitos
* Python 3.12+
* MySQL 8+

1. Iniciar MySQL como root
```bash
mysql -u root -p
```
2. Crear base de datos, usuario y otorgar permisos

```sql
CREATE DATABASE cards_table_develop;

CREATE USER 'developer'@'localhost' IDENTIFIED BY 'developer_pass';

GRANT ALL PRIVILEGES ON cards_table_develop.* TO 'developer'@'localhost';

FLUSH PRIVILEGES;

```

3. Testear conexión 
```bash
mysql -u developer -p cards_table_develop
```

# Setup

Create and activate a virtual environment:
```bash
   python -m venv venv
   source venv/bin/activate

   pip install -r requirements.txt
```

# Configuración del archivo .env

Crear un archivo `.env` en la raíz del proyecto con la configuración de las variables: 

```env
DATABASE_URL="mysql+pymysql://developer:developer_pass@localhost/cards_table_develop"
SECRET_KEY="developer_pass"
```


# Crear tablas y rellenar datos. 
```bash
mysql -u developer -p -e "DROP DATABASE IF EXISTS cards_table_develop; CREATE DATABASE cards_table_develop;"
python create_db.py
mysql -u developer -p cards_table_develop < scripts/carga-datos.sql 
```
## Ejecutar tests unitarios
```bash
pytest
```
o, en caso de error:
```bash
python -m pytest
```

# Run the development server

```bash
./scripts/start_dev.sh
```

# Documentación de la API

La documentación detallada de la API REST y WebSocket del proyecto se encuentra en el archivo [documentacion-API.md](documentacion-API.md). Se detalla:

- Esquemas de datos y modelos
- Endpoints REST disponibles
- Eventos WebSocket
- Ejemplos de uso