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


# Crear tablas
```bash
python create_db.py
```

# Run the development server

```bash
./scripts/start_dev.sh
```

