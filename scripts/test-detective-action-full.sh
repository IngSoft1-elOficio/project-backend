#!/bin/bash

# ======================================================================
# Script de Testing Detective Action - Flujo Completo
# ======================================================================
# Este script ejecuta el flujo completo de 3 jugadores:
# 1. Player 1: Miss Marple (revela secreto de player 3) - 1 POST
# 2. Player 2: Parker Pyne (oculta el secreto revelado) - 1 POST
# 3. Player 3: Satterthwaite + wildcard (transfiere secreto de player 1) - 2 POSTs
#    - POST 1: Owner (Player 3) selecciona target (Player 1)
#    - POST 2: Target (Player 1) selecciona su secreto a transferir
# ======================================================================

set -e  # Exit on error

DB_USER="developer"
DB_PASSWORD="developer_pass"
DB_NAME="cards_table_develop"
BASE_URL="http://localhost:8000/api"

echo ""
echo "=========================================="
echo "   PASO 1: Limpiando base de datos..."
echo "=========================================="
echo ""

mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME <<EOF
SET FOREIGN_KEY_CHECKS = 0;
DROP TABLE IF EXISTS turn;
DROP TABLE IF EXISTS actions_per_turn;
DROP TABLE IF EXISTS cardsXgame;
DROP TABLE IF EXISTS player;
DROP TABLE IF EXISTS room;
DROP TABLE IF EXISTS game;
SET FOREIGN_KEY_CHECKS = 1;
EOF

echo "✅ Tablas eliminadas"

echo ""
echo "=========================================="
echo "   PASO 2: Recreando esquema..."
echo "=========================================="
echo ""

python3 create_db.py

echo "✅ Esquema recreado"

echo ""
echo "=========================================="
echo "   PASO 3: Insertando datos de prueba..."
echo "=========================================="
echo ""

mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME < scripts/testing-integral-d-action.sql

echo "✅ Datos insertados"

echo ""
echo "=========================================="
echo "   PASO 4: Consultando IDs generados..."
echo "=========================================="
echo ""

# Obtener los IDs reales
GAME_ID=$(mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "SELECT MAX(id) FROM game;")
ROOM_ID=$(mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "SELECT MAX(id) FROM room;")
PLAYER1_ID=$(mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "SELECT id FROM player WHERE name='t_detective1';")
PLAYER2_ID=$(mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "SELECT id FROM player WHERE name='t_detective2';")
PLAYER3_ID=$(mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "SELECT id FROM player WHERE name='t_detective3';")

echo "Game ID: $GAME_ID"
echo "Room ID: $ROOM_ID"
echo "Player 1 (t_detective1): $PLAYER1_ID"
echo "Player 2 (t_detective2): $PLAYER2_ID"
echo "Player 3 (t_detective3): $PLAYER3_ID"

echo ""
echo "=========================================="
echo "   JUGADA 1: Player 1 - Miss Marple"
echo "=========================================="
echo ""

# Obtener las cartas de Miss Marple en mano de player1
MARPLE_CARDS=$(mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT GROUP_CONCAT(id ORDER BY position SEPARATOR ',') 
    FROM cardsXgame 
    WHERE id_game=$GAME_ID 
      AND player_id=$PLAYER1_ID 
      AND id_card=6 
      AND is_in='HAND';
")

# Obtener la carta de Harley Quin (comodin) en mano de player1
WILDCARD_P1=$(mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT id 
    FROM cardsXgame 
    WHERE id_game=$GAME_ID 
      AND player_id=$PLAYER1_ID 
      AND id_card=4 
      AND is_in='HAND' 
    LIMIT 1;
")

MARPLE_ID1=$(echo $MARPLE_CARDS | cut -d',' -f1)
MARPLE_ID2=$(echo $MARPLE_CARDS | cut -d',' -f2)

echo "Cartas Miss Marple: $MARPLE_ID1, $MARPLE_ID2"
echo "Carta Harley Quin (comodin): $WILDCARD_P1"

# Construir el JSON para play-detective-set
REQUEST_JSON="{\"owner\":$PLAYER1_ID,\"setType\":\"marple\",\"cards\":[$MARPLE_ID1,$MARPLE_ID2,$WILDCARD_P1],\"hasWildcard\":true}"

echo ""
echo "POST play-detective-set:"
echo "Request: $REQUEST_JSON"

RESPONSE=$(curl -s -X POST "$BASE_URL/game/$GAME_ID/play-detective-set" \
  -H "Content-Type: application/json" \
  -H "X-User-Id: $PLAYER1_ID" \
  -d "$REQUEST_JSON")

echo "Response:"
echo "$RESPONSE" | jq '.'

# Verificar que fue exitoso
SUCCESS=$(echo "$RESPONSE" | jq -r '.success')
if [ "$SUCCESS" != "true" ]; then
    echo "❌ ERROR: play-detective-set fallo"
    exit 1
fi

echo "✅ Detective set bajado exitosamente"

# Extraer el actionId
ACTION_ID=$(echo "$RESPONSE" | jq -r '.actionId')
echo "Action ID creado: $ACTION_ID"

# Miss Marple es tipo "activo" - el OWNER selecciona el secreto de otro jugador
# Seleccionamos Player 3 para que luego Player 2 pueda ocultar ese secreto (no puede ocultar el propio)
TARGET_PLAYER=$PLAYER3_ID
echo "Target Player ID: $TARGET_PLAYER"

# Consultar un secreto del target player
SECRET_ID=$(mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT id 
    FROM cardsXgame 
    WHERE id_game=$GAME_ID 
      AND player_id=$TARGET_PLAYER 
      AND is_in='SECRET_SET' 
    LIMIT 1;
")
echo "Secret ID del target player: $SECRET_ID"

echo ""
echo "POST detective-action (Miss Marple revela secreto):"

# Construir el request para detective-action
ACTION_REQUEST="{\"actionId\":$ACTION_ID,\"executorId\":$PLAYER1_ID,\"targetPlayerId\":$TARGET_PLAYER,\"secretId\":$SECRET_ID}"

echo "Request: $ACTION_REQUEST"

ACTION_RESPONSE=$(curl -s -X POST "$BASE_URL/game/$GAME_ID/detective-action" \
  -H "Content-Type: application/json" \
  -H "X-User-Id: $PLAYER1_ID" \
  -d "$ACTION_REQUEST")

echo "Response:"
echo "$ACTION_RESPONSE" | jq '.'

# Verificar que fue exitoso
ACTION_SUCCESS=$(echo "$ACTION_RESPONSE" | jq -r '.success')
if [ "$ACTION_SUCCESS" != "true" ]; then
    echo "❌ ERROR: detective-action fallo"
    exit 1
fi

echo "✅ Detective action ejecutado exitosamente"

# Guardar el SECRET_ID revelado para el siguiente turno
REVEALED_SECRET_ID=$SECRET_ID

echo ""
echo "Secretos revelados:"
echo "$ACTION_RESPONSE" | jq -r '.effects.revealed[]? | "  Player \(.playerId): Secret \(.secretId) - \(.cardName) (pos: \(.position))"'

echo ""
echo "=========================================="
echo "   Cambio de turno: Player 1 -> Player 2"
echo "=========================================="
echo ""

# Cerrar el turno actual
mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME <<EOF
UPDATE turn SET status = 'FINISHED' WHERE id_game = $GAME_ID AND status = 'IN_PROGRESS';
INSERT INTO turn (number, id_game, player_id, status, start_time) 
VALUES (2, $GAME_ID, $PLAYER2_ID, 'IN_PROGRESS', CURRENT_TIMESTAMP);
UPDATE game SET player_turn_id = $PLAYER2_ID WHERE id = $GAME_ID;
EOF

echo "✅ Turno cambiado a Player 2"

echo ""
echo "=========================================="
echo "   JUGADA 2: Player 2 - Parker Pyne"
echo "=========================================="
echo ""

# Obtener las cartas de Parker Pyne en mano de player2
PYNE_CARDS=$(mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT GROUP_CONCAT(id ORDER BY position SEPARATOR ',') 
    FROM cardsXgame 
    WHERE id_game=$GAME_ID 
      AND player_id=$PLAYER2_ID 
      AND id_card=7 
      AND is_in='HAND';
")

PYNE_ID1=$(echo $PYNE_CARDS | cut -d',' -f1)
PYNE_ID2=$(echo $PYNE_CARDS | cut -d',' -f2)

echo "Cartas Parker Pyne: $PYNE_ID1, $PYNE_ID2"

# Construir el JSON para play-detective-set
REQUEST_JSON="{\"owner\":$PLAYER2_ID,\"setType\":\"pyne\",\"cards\":[$PYNE_ID1,$PYNE_ID2],\"hasWildcard\":false}"

echo ""
echo "POST play-detective-set:"
echo "Request: $REQUEST_JSON"

RESPONSE=$(curl -s -X POST "$BASE_URL/game/$GAME_ID/play-detective-set" \
  -H "Content-Type: application/json" \
  -H "X-User-Id: $PLAYER2_ID" \
  -d "$REQUEST_JSON")

echo "Response:"
echo "$RESPONSE" | jq '.'

# Verificar que fue exitoso
SUCCESS=$(echo "$RESPONSE" | jq -r '.success')
if [ "$SUCCESS" != "true" ]; then
    echo "❌ ERROR: play-detective-set fallo"
    exit 1
fi

echo "✅ Detective set bajado exitosamente"

# Extraer el actionId
ACTION_ID=$(echo "$RESPONSE" | jq -r '.actionId')
echo "Action ID creado: $ACTION_ID"

# Parker Pyne es "activo" - el OWNER (Player 2) selecciona un secreto revelado de cualquier jugador
# El owner ejecuta la accion y selecciona el secreto de otro jugador (Player 3) que fue revelado
VICTIM_PLAYER=$PLAYER3_ID
echo "Victim Player ID (dueno del secreto a ocultar): $VICTIM_PLAYER"

# Pyne oculta el secreto que fue revelado anteriormente (de Player 3)
echo "Secret ID a ocultar: $REVEALED_SECRET_ID"

echo ""
echo "POST detective-action (Parker Pyne oculta secreto):"

# Construir el request para detective-action
# Pyne es "activo" - el OWNER ejecuta seleccionando un secreto revelado de otro jugador
ACTION_REQUEST="{\"actionId\":$ACTION_ID,\"executorId\":$PLAYER2_ID,\"targetPlayerId\":$VICTIM_PLAYER,\"secretId\":$REVEALED_SECRET_ID}"

echo "Request: $ACTION_REQUEST"

ACTION_RESPONSE=$(curl -s -X POST "$BASE_URL/game/$GAME_ID/detective-action" \
  -H "Content-Type: application/json" \
  -H "X-User-Id: $PLAYER2_ID" \
  -d "$ACTION_REQUEST")

echo "Response:"
echo "$ACTION_RESPONSE" | jq '.'

# Verificar que fue exitoso
ACTION_SUCCESS=$(echo "$ACTION_RESPONSE" | jq -r '.success')
if [ "$ACTION_SUCCESS" != "true" ]; then
    echo "❌ ERROR: detective-action fallo"
    exit 1
fi

echo "✅ Detective action ejecutado exitosamente"

echo ""
echo "Secretos ocultados:"
echo "$ACTION_RESPONSE" | jq -r '.effects.hidden[]? | "  Player \(.playerId): Secret \(.secretId) (pos: \(.position))"'

echo ""
echo "=========================================="
echo "   Cambio de turno: Player 2 -> Player 3"
echo "=========================================="
echo ""

# Cerrar el turno actual
mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME <<EOF
UPDATE turn SET status = 'FINISHED' WHERE id_game = $GAME_ID AND status = 'IN_PROGRESS';
INSERT INTO turn (number, id_game, player_id, status, start_time) 
VALUES (3, $GAME_ID, $PLAYER3_ID, 'IN_PROGRESS', CURRENT_TIMESTAMP);
UPDATE game SET player_turn_id = $PLAYER3_ID WHERE id = $GAME_ID;
EOF

echo "✅ Turno cambiado a Player 3"

echo ""
echo "=========================================="
echo "   JUGADA 3: Player 3 - Satterthwaite"
echo "=========================================="
echo ""

# Obtener la carta de Satterthwaite en mano de player3
SATT_ID=$(mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT id 
    FROM cardsXgame 
    WHERE id_game=$GAME_ID 
      AND player_id=$PLAYER3_ID 
      AND id_card=12 
      AND is_in='HAND' 
    LIMIT 1;
")

# Obtener la carta de Harley Quin (comodin) en mano de player3
WILDCARD_P3=$(mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT id 
    FROM cardsXgame 
    WHERE id_game=$GAME_ID 
      AND player_id=$PLAYER3_ID 
      AND id_card=4 
      AND is_in='HAND' 
    LIMIT 1;
")

echo "Carta Satterthwaite: $SATT_ID"
echo "Carta Harley Quin (comodin): $WILDCARD_P3"

# Construir el JSON para play-detective-set
REQUEST_JSON="{\"owner\":$PLAYER3_ID,\"setType\":\"satterthwaite\",\"cards\":[$SATT_ID,$WILDCARD_P3],\"hasWildcard\":true}"

echo ""
echo "POST play-detective-set:"
echo "Request: $REQUEST_JSON"

RESPONSE=$(curl -s -X POST "$BASE_URL/game/$GAME_ID/play-detective-set" \
  -H "Content-Type: application/json" \
  -H "X-User-Id: $PLAYER3_ID" \
  -d "$REQUEST_JSON")

echo "Response:"
echo "$RESPONSE" | jq '.'

# Verificar que fue exitoso
SUCCESS=$(echo "$RESPONSE" | jq -r '.success')
if [ "$SUCCESS" != "true" ]; then
    echo "❌ ERROR: play-detective-set fallo"
    exit 1
fi

echo "✅ Detective set bajado exitosamente"

# Extraer el actionId
ACTION_ID=$(echo "$RESPONSE" | jq -r '.actionId')
echo "Action ID creado: $ACTION_ID"

# Satterthwaite es "pasivo" - FLUJO DE 2 POSTS:
# POST 1: El OWNER (Player 3) selecciona al TARGET (Player 1)
# POST 2: El TARGET (Player 1) selecciona su propio secreto a transferir

TARGET_PLAYER=$PLAYER1_ID
echo "Target Player ID (el que dona su secreto): $TARGET_PLAYER"

echo ""
echo "=========================================="
echo "   POST 1: Owner selecciona target"
echo "=========================================="
echo ""

# POST 1: Owner (Player 3) selecciona al target (Player 1)
STEP1_REQUEST="{\"actionId\":$ACTION_ID,\"executorId\":$PLAYER3_ID,\"targetPlayerId\":$TARGET_PLAYER}"

echo "Request: $STEP1_REQUEST"

STEP1_RESPONSE=$(curl -s -X POST "$BASE_URL/game/$GAME_ID/detective-action" \
  -H "Content-Type: application/json" \
  -H "X-User-Id: $PLAYER3_ID" \
  -d "$STEP1_REQUEST")

echo "Response:"
echo "$STEP1_RESPONSE" | jq '.'

# Verificar que fue exitoso pero incompleto
STEP1_SUCCESS=$(echo "$STEP1_RESPONSE" | jq -r '.success')
STEP1_COMPLETED=$(echo "$STEP1_RESPONSE" | jq -r '.completed')

if [ "$STEP1_SUCCESS" != "true" ]; then
    echo "❌ ERROR: detective-action step 1 fallo"
    exit 1
fi

if [ "$STEP1_COMPLETED" != "false" ]; then
    echo "❌ ERROR: Se esperaba completed=false en step 1"
    exit 1
fi

echo "✅ Step 1 exitoso: Target seleccionado"
echo ""
echo "Next Action para el target:"
echo "$STEP1_RESPONSE" | jq '.nextAction'

echo ""
echo "=========================================="
echo "   POST 2: Target selecciona su secreto"
echo "=========================================="
echo ""

# Consultar un secreto del target player para transferir
TRANSFER_SECRET_ID=$(mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT id 
    FROM cardsXgame 
    WHERE id_game=$GAME_ID 
      AND player_id=$TARGET_PLAYER 
      AND is_in='SECRET_SET' 
    LIMIT 1;
")
echo "Secret ID a transferir: $TRANSFER_SECRET_ID"

# POST 2: Target (Player 1) selecciona su propio secreto
STEP2_REQUEST="{\"actionId\":$ACTION_ID,\"executorId\":$TARGET_PLAYER,\"secretId\":$TRANSFER_SECRET_ID}"

echo "Request: $STEP2_REQUEST"

STEP2_RESPONSE=$(curl -s -X POST "$BASE_URL/game/$GAME_ID/detective-action" \
  -H "Content-Type: application/json" \
  -H "X-User-Id: $TARGET_PLAYER" \
  -d "$STEP2_REQUEST")

echo "Response:"
echo "$STEP2_RESPONSE" | jq '.'

# Verificar que fue exitoso y completo
STEP2_SUCCESS=$(echo "$STEP2_RESPONSE" | jq -r '.success')
STEP2_COMPLETED=$(echo "$STEP2_RESPONSE" | jq -r '.completed')

if [ "$STEP2_SUCCESS" != "true" ]; then
    echo "❌ ERROR: detective-action step 2 fallo"
    exit 1
fi

if [ "$STEP2_COMPLETED" != "true" ]; then
    echo "❌ ERROR: Se esperaba completed=true en step 2"
    exit 1
fi

echo "✅ Step 2 exitoso: Acción completada"

# Usar la respuesta del step 2 para mostrar efectos
ACTION_RESPONSE=$STEP2_RESPONSE

echo ""
echo "Secretos transferidos:"
echo "$ACTION_RESPONSE" | jq -r '.effects.transferred[]? | "  De player \(.fromPlayerId) a \(.toPlayerId): Secret \(.secretId) - \(.cardName) (faceDown: \(.faceDown), pos: \(.newPosition))"'

echo ""
echo "=========================================="
echo "   RESUMEN FINAL"
echo "=========================================="
echo ""

echo "✅ Jugada 1: Player 1 (Miss Marple) revelo secreto de Player 2"
echo "✅ Jugada 2: Player 2 (Parker Pyne) oculto el secreto revelado"
echo "✅ Jugada 3: Player 3 (Satterthwaite + wildcard) transfirio secreto de Player 1"

echo ""
echo "✅ TEST COMPLETADO EXITOSAMENTE"
echo ""
