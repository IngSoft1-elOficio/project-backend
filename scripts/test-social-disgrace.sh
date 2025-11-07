#!/bin/bash

# ==============================
# Test de Integración: Social Disgrace
# ==============================
# Este script testea el flujo completo de entrar y salir de desgracia social
#
# Flujo:
# 1. Carga datos iniciales (jugador con 2 secretos ya revelados)
# 2. Jugador 1 baja Miss Marple y revela el último secreto del jugador 3
#    → Jugador 3 entra en DESGRACIA SOCIAL
# 3. Verificar que el jugador 3 está en la tabla social_disgrace_player
# 4. Jugador 2 baja Parker Pyne y oculta un secreto del jugador 3
#    → Jugador 3 sale de DESGRACIA SOCIAL
# 5. Verificar que el jugador 3 ya NO está en la tabla social_disgrace_player

set -e  # Exit on error

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuración de la base de datos
DB_USER="developer"
DB_PASSWORD="developer_pass"
DB_NAME="cards_table_develop"

# URL base de la API
BASE_URL="http://localhost:8000/api"

echo -e "${BLUE}==============================${NC}"
echo -e "${BLUE}TEST DE INTEGRACIÓN: SOCIAL DISGRACE${NC}"
echo -e "${BLUE}==============================${NC}\n"

# ==============================
# PASO 1: Limpiando base de datos
# ==============================
echo -e "${YELLOW}📋 PASO 1: Limpiando base de datos...${NC}"
mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME <<EOF
SET FOREIGN_KEY_CHECKS = 0;
DROP TABLE IF EXISTS social_disgrace_player;
DROP TABLE IF EXISTS turn;
DROP TABLE IF EXISTS actions_per_turn;
DROP TABLE IF EXISTS cardsXgame;
DROP TABLE IF EXISTS player;
DROP TABLE IF EXISTS room;
DROP TABLE IF EXISTS game;
SET FOREIGN_KEY_CHECKS = 1;
EOF
echo -e "${GREEN}✅ Tablas eliminadas${NC}"

echo ""
echo -e "${YELLOW}📋 PASO 2: Recreando esquema...${NC}"
python3 create_db.py
echo -e "${GREEN}✅ Esquema recreado${NC}"

echo ""
# ==============================
# PASO 3: Cargar datos de prueba
# ==============================
echo -e "${YELLOW}📊 PASO 3: Cargando datos de prueba en la base de datos...${NC}"
mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME < scripts/testing-social-disgrace.sql

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Datos cargados exitosamente${NC}\n"
else
    echo -e "${RED}❌ Error al cargar datos${NC}"
    exit 1
fi

# Obtener los IDs creados
GAME_ID=$(mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "SELECT MAX(id) FROM game;")
ROOM_ID=$(mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "SELECT MAX(id) FROM room;")
PLAYER1_ID=$(mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "SELECT id FROM player WHERE name='t_disgrace1' ORDER BY id DESC LIMIT 1;")
PLAYER2_ID=$(mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "SELECT id FROM player WHERE name='t_disgrace2' ORDER BY id DESC LIMIT 1;")
PLAYER3_ID=$(mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "SELECT id FROM player WHERE name='t_disgrace3' ORDER BY id DESC LIMIT 1;")

echo -e "${BLUE}IDs generados:${NC}"
echo -e "  Game ID: ${GREEN}$GAME_ID${NC}"
echo -e "  Room ID: ${GREEN}$ROOM_ID${NC}"
echo -e "  Player 1 (t_disgrace1): ${GREEN}$PLAYER1_ID${NC}"
echo -e "  Player 2 (t_disgrace2): ${GREEN}$PLAYER2_ID${NC}"
echo -e "  Player 3 (t_disgrace3): ${GREEN}$PLAYER3_ID${NC} (tiene 2 secretos revelados)"
echo ""

# ==============================
# PASO 4: Obtener IDs de cartas en mano de Player 1 (Miss Marple)
# ==============================
echo -e "${YELLOW}📋 PASO 4: Obteniendo cartas de Miss Marple en mano de Player 1...${NC}"

# Obtener 2 cartas Miss Marple (id_card = 6)
MARPLE_ONLY=$(mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
SELECT GROUP_CONCAT(cxg.id ORDER BY cxg.position SEPARATOR ',')
FROM cardsXgame cxg
WHERE cxg.id_game = $GAME_ID 
  AND cxg.player_id = $PLAYER1_ID
  AND cxg.is_in = 'HAND'
  AND cxg.id_card = 6
LIMIT 2;
")

# Obtener 1 Harley Quin (comodín, id_card = 4)
WILDCARD=$(mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
SELECT cxg.id
FROM cardsXgame cxg
WHERE cxg.id_game = $GAME_ID 
  AND cxg.player_id = $PLAYER1_ID
  AND cxg.is_in = 'HAND'
  AND cxg.id_card = 4
LIMIT 1;
")

IFS=',' read -ra MARPLE_IDS <<< "$MARPLE_ONLY"
MARPLE1_ID=${MARPLE_IDS[0]}
MARPLE2_ID=${MARPLE_IDS[1]}

echo -e "${GREEN}✅ Cartas obtenidas:${NC}"
echo -e "   Miss Marple: $MARPLE1_ID, $MARPLE2_ID"
echo -e "   Harley Quin (comodín): $WILDCARD"
echo ""

# ==============================
# PASO 5: Obtener ID del secreto oculto de Player 3 (posición 1)
# ==============================
echo -e "${YELLOW}🔍 PASO 5: Obteniendo ID del último secreto oculto de Player 3...${NC}"

SECRET_ID=$(mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
SELECT cxg.id
FROM cardsXgame cxg
WHERE cxg.id_game = $GAME_ID 
  AND cxg.player_id = $PLAYER3_ID
  AND cxg.is_in = 'SECRET_SET'
  AND cxg.hidden = TRUE
LIMIT 1;
")

echo -e "${GREEN}✅ Secreto a revelar: CardsXGame ID = $SECRET_ID${NC}\n"

# ==============================
# PASO 6: Player 1 baja el set de Miss Marple
# ==============================
echo -e "${YELLOW}🎭 PASO 6a: Player 1 baja el set de Miss Marple...${NC}"

PLAY_SET_REQUEST="{\"owner\":$PLAYER1_ID,\"setType\":\"marple\",\"cards\":[$MARPLE1_ID,$MARPLE2_ID,$WILDCARD],\"hasWildcard\":true}"
echo "Request: $PLAY_SET_REQUEST"

PLAY_SET_RESPONSE=$(curl -s -X POST "$BASE_URL/game/$GAME_ID/play-detective-set" \
  -H "Content-Type: application/json" \
  -H "X-User-Id: $PLAYER1_ID" \
  -d "$PLAY_SET_REQUEST")

echo "$PLAY_SET_RESPONSE" | jq '.'

if echo "$PLAY_SET_RESPONSE" | jq -e '.success' > /dev/null 2>&1; then
    ACTION_ID=$(echo "$PLAY_SET_RESPONSE" | jq -r '.actionId')
    echo -e "${GREEN}✅ Set bajado exitosamente - Action ID: $ACTION_ID${NC}\n"
else
    echo -e "${RED}❌ Error al bajar el set${NC}"
    echo "$PLAY_SET_RESPONSE"
    exit 1
fi

# ==============================
# PASO 6b: Player 1 ejecuta la acción (revela secreto)
# ==============================
echo -e "${YELLOW}🎭 PASO 6b: Player 1 ejecuta Miss Marple (revela secreto de Player 3)...${NC}"

ACTION_REQUEST="{\"actionId\":$ACTION_ID,\"executorId\":$PLAYER1_ID,\"targetPlayerId\":$PLAYER3_ID,\"secretId\":$SECRET_ID}"
echo "Request: $ACTION_REQUEST"

ACTION_RESPONSE=$(curl -s -X POST "$BASE_URL/game/$GAME_ID/detective-action" \
  -H "Content-Type: application/json" \
  -H "X-User-Id: $PLAYER1_ID" \
  -d "$ACTION_REQUEST")

echo "$ACTION_RESPONSE" | jq '.'

if echo "$ACTION_RESPONSE" | jq -e '.success' > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Miss Marple ejecutada exitosamente${NC}"
    echo -e "${GREEN}✅ Secreto revelado de Player 3${NC}\n"
else
    echo -e "${RED}❌ Error al ejecutar Miss Marple${NC}"
    echo "$ACTION_RESPONSE"
    exit 1
fi

# ==============================
# PASO 7: Verificar que Player 3 está en DESGRACIA SOCIAL
# ==============================
echo -e "${YELLOW}🔍 PASO 7: Verificando si Player 3 entró en desgracia social...${NC}"

sleep 1  # Dar tiempo a que se procese el evento

DISGRACE_CHECK=$(mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
SELECT COUNT(*) 
FROM social_disgrace_player 
WHERE id_game = $GAME_ID AND player_id = $PLAYER3_ID;
")

if [ "$DISGRACE_CHECK" -eq "1" ]; then
    echo -e "${GREEN}✅ ¡Player 3 (t_disgrace3) está en DESGRACIA SOCIAL!${NC}"
    
    # Mostrar detalles
    mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT 
        sdp.id AS 'ID',
        sdp.id_game AS 'Game',
        sdp.player_id AS 'Player',
        p.name AS 'Nombre',
        sdp.entered_at AS 'Entró en desgracia'
    FROM social_disgrace_player sdp
    JOIN player p ON sdp.player_id = p.id
    WHERE sdp.id_game = $GAME_ID AND sdp.player_id = $PLAYER3_ID;
    "
    echo ""
else
    echo -e "${RED}❌ Player 3 NO está en desgracia social (esperado: sí)${NC}"
    exit 1
fi

# ==============================
# PASO 8: Cambiar turno a Player 2
# ==============================
echo -e "${YELLOW}🔄 PASO 8: Cambiando turno a Player 2...${NC}"

# Actualizar el turno en la base de datos
mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME <<EOF
-- Finalizar turno actual de Player 1
UPDATE turn 
SET status = 'FINISHED'
WHERE id_game = $GAME_ID AND player_id = $PLAYER1_ID AND status = 'IN_PROGRESS';

-- Crear nuevo turno para Player 2
INSERT INTO turn (number, id_game, player_id, status, start_time) 
VALUES (2, $GAME_ID, $PLAYER2_ID, 'IN_PROGRESS', CURRENT_TIMESTAMP);

-- Actualizar player_turn_id en game
UPDATE game 
SET player_turn_id = $PLAYER2_ID 
WHERE id = $GAME_ID;
EOF

echo -e "${GREEN}✅ Turno actualizado: ahora es el turno de Player 2${NC}\n"

# ==============================
# PASO 9: Obtener IDs de cartas en mano de Player 2 (Parker Pyne)
# ==============================
echo -e "${YELLOW}📋 PASO 9: Obteniendo cartas de Parker Pyne en mano de Player 2...${NC}"

# Obtener 2 cartas Parker Pyne (id_card = 7)
PYNE_ONLY=$(mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
SELECT GROUP_CONCAT(cxg.id ORDER BY cxg.position SEPARATOR ',')
FROM cardsXgame cxg
WHERE cxg.id_game = $GAME_ID 
  AND cxg.player_id = $PLAYER2_ID
  AND cxg.is_in = 'HAND'
  AND cxg.id_card = 7
LIMIT 2;
")

# Obtener 1 Harley Quin (comodín, id_card = 4)
WILDCARD2=$(mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
SELECT cxg.id
FROM cardsXgame cxg
WHERE cxg.id_game = $GAME_ID 
  AND cxg.player_id = $PLAYER2_ID
  AND cxg.is_in = 'HAND'
  AND cxg.id_card = 4
LIMIT 1;
")

IFS=',' read -ra PYNE_IDS <<< "$PYNE_ONLY"
PYNE1_ID=${PYNE_IDS[0]}
PYNE2_ID=${PYNE_IDS[1]}

echo -e "${GREEN}✅ Cartas obtenidas:${NC}"
echo -e "   Parker Pyne: $PYNE1_ID, $PYNE2_ID"
echo -e "   Harley Quin (comodín): $WILDCARD2"
echo ""

# ==============================
# PASO 10: Obtener ID de un secreto REVELADO de Player 3
# ==============================
echo -e "${YELLOW}🔍 PASO 10: Obteniendo ID de un secreto revelado de Player 3...${NC}"

REVEALED_SECRET_ID=$(mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
SELECT cxg.id
FROM cardsXgame cxg
WHERE cxg.id_game = $GAME_ID 
  AND cxg.player_id = $PLAYER3_ID
  AND cxg.is_in = 'SECRET_SET'
  AND cxg.hidden = FALSE
LIMIT 1;
")

echo -e "${GREEN}✅ Secreto a ocultar: CardsXGame ID = $REVEALED_SECRET_ID${NC}\n"

# ==============================
# PASO 11a: Player 2 baja el set de Parker Pyne
# ==============================
echo -e "${YELLOW}🎭 PASO 11a: Player 2 baja el set de Parker Pyne...${NC}"

PLAY_SET_REQUEST2="{\"owner\":$PLAYER2_ID,\"setType\":\"pyne\",\"cards\":[$PYNE1_ID,$PYNE2_ID,$WILDCARD2],\"hasWildcard\":true}"
echo "Request: $PLAY_SET_REQUEST2"

PLAY_SET_RESPONSE2=$(curl -s -X POST "$BASE_URL/game/$GAME_ID/play-detective-set" \
  -H "Content-Type: application/json" \
  -H "X-User-Id: $PLAYER2_ID" \
  -d "$PLAY_SET_REQUEST2")

echo "$PLAY_SET_RESPONSE2" | jq '.'

if echo "$PLAY_SET_RESPONSE2" | jq -e '.success' > /dev/null 2>&1; then
    ACTION_ID2=$(echo "$PLAY_SET_RESPONSE2" | jq -r '.actionId')
    echo -e "${GREEN}✅ Set bajado exitosamente - Action ID: $ACTION_ID2${NC}\n"
else
    echo -e "${RED}❌ Error al bajar el set${NC}"
    echo "$PLAY_SET_RESPONSE2"
    exit 1
fi

# ==============================
# PASO 11b: Player 2 ejecuta la acción (oculta secreto)
# ==============================
echo -e "${YELLOW}🎭 PASO 11b: Player 2 ejecuta Parker Pyne (oculta secreto de Player 3)...${NC}"

ACTION_REQUEST2="{\"actionId\":$ACTION_ID2,\"executorId\":$PLAYER2_ID,\"targetPlayerId\":$PLAYER3_ID,\"secretId\":$REVEALED_SECRET_ID}"
echo "Request: $ACTION_REQUEST2"

ACTION_RESPONSE2=$(curl -s -X POST "$BASE_URL/game/$GAME_ID/detective-action" \
  -H "Content-Type: application/json" \
  -H "X-User-Id: $PLAYER2_ID" \
  -d "$ACTION_REQUEST2")

echo "$ACTION_RESPONSE2" | jq '.'

if echo "$ACTION_RESPONSE2" | jq -e '.success' > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Parker Pyne ejecutado exitosamente${NC}"
    echo -e "${GREEN}✅ Secreto ocultado de Player 3${NC}\n"
else
    echo -e "${RED}❌ Error al ejecutar Parker Pyne${NC}"
    echo "$ACTION_RESPONSE2"
    exit 1
fi

# ==============================
# PASO 12: Verificar que Player 3 salió de DESGRACIA SOCIAL
# ==============================
echo -e "${YELLOW}🔍 PASO 12: Verificando si Player 3 salió de desgracia social...${NC}"

sleep 1  # Dar tiempo a que se procese el evento

DISGRACE_CHECK2=$(mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
SELECT COUNT(*) 
FROM social_disgrace_player 
WHERE id_game = $GAME_ID AND player_id = $PLAYER3_ID;
")

if [ "$DISGRACE_CHECK2" -eq "0" ]; then
    echo -e "${GREEN}✅ ¡Player 3 (t_disgrace3) salió de DESGRACIA SOCIAL!${NC}"
    echo -e "${GREEN}✅ La tabla social_disgrace_player ya NO contiene al jugador${NC}\n"
else
    echo -e "${RED}❌ Player 3 sigue en desgracia social (esperado: no)${NC}"
    
    # Mostrar contenido actual
    echo -e "${YELLOW}Contenido actual de social_disgrace_player:${NC}"
    mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT * FROM social_disgrace_player WHERE id_game = $GAME_ID;
    "
    exit 1
fi

# ==============================
# RESUMEN FINAL
# ==============================
echo -e "${BLUE}==============================${NC}"
echo -e "${BLUE}📊 RESUMEN DEL TEST${NC}"
echo -e "${BLUE}==============================${NC}"
echo -e "${GREEN}✅ Player 3 entró en desgracia social al revelar su último secreto${NC}"
echo -e "${GREEN}✅ Player 3 salió de desgracia social al ocultar un secreto${NC}"
echo -e "${GREEN}✅ Sistema de desgracia social funcionando correctamente${NC}"
echo -e "${BLUE}==============================${NC}\n"

echo -e "${GREEN}🎉 TEST DE INTEGRACIÓN COMPLETADO EXITOSAMENTE${NC}\n"
