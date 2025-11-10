#!/bin/bash

source venv/bin/activate

set -e

DB_USER="developer"
DB_PASSWORD="developer_pass"
DB_NAME="cards_table_develop"
BASE_URL="http://localhost:8000/api"

echo ""
echo "=========================================="
echo "   TEST: Dead Card Folly Complete Flow"
echo "=========================================="
echo ""

echo "📋 PASO 1: Limpiando base de datos..."
mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME <<EOF
SET FOREIGN_KEY_CHECKS = 0;
DROP TABLE IF EXISTS turn;
DROP TABLE IF EXISTS actions_per_turn;
DROP TABLE IF EXISTS cardsXgame;
DROP TABLE IF EXISTS player;
DROP TABLE IF EXISTS room;
DROP TABLE IF EXISTS game;
DROP TABLE IF EXISTS card;
SET FOREIGN_KEY_CHECKS = 1;
EOF
echo "✅ Tablas eliminadas"

echo ""
echo "📋 PASO 2: Recreando esquema..."
python3 create_db.py
echo "✅ Esquema recreado"

echo ""
echo "📋 PASO 3: Cargando datos base (cartas)..."
mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME < scripts/carga-datos.sql
echo "✅ Cartas cargadas"

echo ""
echo "📋 PASO 4: Limpiando datos de juego de carga-datos.sql..."
mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME <<EOF
SET FOREIGN_KEY_CHECKS = 0;
TRUNCATE TABLE cardsXgame;
TRUNCATE TABLE turn;
TRUNCATE TABLE actions_per_turn;
TRUNCATE TABLE player;
TRUNCATE TABLE room;
TRUNCATE TABLE game;
SET FOREIGN_KEY_CHECKS = 1;
EOF
echo "✅ Datos de juego limpiados (solo quedan las cartas)"

echo ""
echo "📋 PASO 5: Insertando datos de test Dead Card Folly..."
mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME < scripts/dcf-test-data.sql
echo "✅ Datos de test insertados"

echo ""
echo "📋 PASO 6: Consultando IDs generados..."
GAME_ID=$(mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "SELECT MAX(id) FROM game;")
ROOM_ID=$(mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "SELECT MAX(id) FROM room;")
PLAYER1_ID=$(mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "SELECT id FROM player WHERE name='DCF_Player1';")
PLAYER2_ID=$(mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "SELECT id FROM player WHERE name='DCF_Player2';")
PLAYER3_ID=$(mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "SELECT id FROM player WHERE name='DCF_Player3';")

echo "Game ID: $GAME_ID"
echo "Room ID: $ROOM_ID"
echo "Player 1 (DCF_Player1): $PLAYER1_ID - Order: 1"
echo "Player 2 (DCF_Player2): $PLAYER2_ID - Order: 2 - TURNO ACTUAL, JUEGA DEAD CARD FOLLY"
echo "Player 3 (DCF_Player3): $PLAYER3_ID - Order: 3"

# Obtener carta Dead Card Folly del Player 2
DCF_CARD=$(mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT id FROM cardsXgame 
    WHERE id_game=$GAME_ID 
      AND player_id=$PLAYER2_ID 
      AND id_card=18 
      AND is_in='HAND' 
    LIMIT 1;
")

echo ""
echo "Carta 'Dead Card Folly' (cardsXgame.id): $DCF_CARD (player_id: $PLAYER2_ID)"

echo ""
echo "=========================================="
echo "   ESTADO INICIAL"
echo "=========================================="
echo ""

echo "🔍 DISCARD INICIAL (3 cartas):"
mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT CONCAT('  [Pos ', position, '] Card ID: ', id_card, ' | Hidden: ', hidden) 
    FROM cardsXgame 
    WHERE id_game=$GAME_ID 
      AND is_in='DISCARD'
    ORDER BY position ASC;
"

echo ""
echo "🔍 MANO PLAYER 1 (6 cartas):"
mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT CONCAT('  [Pos ', position, '] CardsXGame.id: ', id, ' | Card.id: ', id_card) 
    FROM cardsXgame 
    WHERE id_game=$GAME_ID 
      AND player_id=$PLAYER1_ID 
      AND is_in='HAND'
    ORDER BY position;
"

echo ""
echo "🔍 MANO PLAYER 2 (6 cartas: Dead Card Folly + 5 más):"
mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT CONCAT('  [Pos ', position, '] CardsXGame.id: ', id, ' | Card.id: ', id_card, ' (18=Dead Card Folly)') 
    FROM cardsXgame 
    WHERE id_game=$GAME_ID 
      AND player_id=$PLAYER2_ID 
      AND is_in='HAND'
    ORDER BY position;
"

echo ""
echo "🔍 MANO PLAYER 3 (6 cartas):"
mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT CONCAT('  [Pos ', position, '] CardsXGame.id: ', id, ' | Card.id: ', id_card) 
    FROM cardsXgame 
    WHERE id_game=$GAME_ID 
      AND player_id=$PLAYER3_ID 
      AND is_in='HAND'
    ORDER BY position;
"

echo ""
echo "=========================================="
echo "   🎮 TEST 1: Player 2 juega Dead Card Folly (LEFT)"
echo "=========================================="
echo ""
echo "📝 Explicación:"
echo "   - Player 2 (order=2) juega Dead Card Folly con dirección LEFT"
echo "   - LEFT = rotación en sentido DESCENDENTE (2→1→3→2)"
echo "   - Cada jugador seleccionará una carta para dar a su vecino izquierdo"
echo ""

REQUEST_PLAY="{
  \"player_id\": $PLAYER2_ID,
  \"card_id\": $DCF_CARD,
  \"direction\": \"LEFT\"
}"
echo "📤 Request POST /api/game/$ROOM_ID/event/dead-card-folly/play:"
echo "$REQUEST_PLAY" | jq '.'

RESPONSE_PLAY=$(curl -s -X POST "$BASE_URL/game/$ROOM_ID/event/dead-card-folly/play" \
  -H "Content-Type: application/json" \
  -d "$REQUEST_PLAY")

echo ""
echo "📥 Response:"
echo "$RESPONSE_PLAY" | jq '.'

ACTION_PARENT=$(echo "$RESPONSE_PLAY" | jq -r '.action_id')
SUCCESS_PLAY=$(echo "$RESPONSE_PLAY" | jq -r '.success')

if [ "$SUCCESS_PLAY" != "true" ]; then
    echo "❌ ERROR: Player 2 no pudo jugar Dead Card Folly"
    exit 1
fi

if [ "$ACTION_PARENT" == "null" ] || [ -z "$ACTION_PARENT" ]; then
    echo "❌ ERROR: No se obtuvo action_id (parent action)"
    exit 1
fi

echo ""
echo "✅ Dead Card Folly jugada correctamente"
echo "   Action Parent ID: $ACTION_PARENT"
echo "   Dirección: LEFT (rotación descendente)"

echo ""
echo "🔍 DISCARD DESPUÉS DE JUGAR (debería tener 4 cartas: 3 iniciales + Dead Card Folly):"
DISCARD_COUNT_PLAY=$(mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT COUNT(*) FROM cardsXgame 
    WHERE id_game=$GAME_ID AND is_in='DISCARD';
")
echo "   Total: $DISCARD_COUNT_PLAY cartas"
mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT CONCAT('  [Pos ', position, '] Card ID: ', id_card, ' (18=Dead Card Folly)') 
    FROM cardsXgame 
    WHERE id_game=$GAME_ID 
      AND is_in='DISCARD'
    ORDER BY position ASC;
"

echo ""
echo "🔍 MANO PLAYER 2 DESPUÉS DE JUGAR (debería tener 5 cartas):"
HAND_P2_AFTER_PLAY=$(mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT COUNT(*) FROM cardsXgame 
    WHERE id_game=$GAME_ID 
      AND player_id=$PLAYER2_ID 
      AND is_in='HAND';
")
echo "   Total: $HAND_P2_AFTER_PLAY cartas"
mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT CONCAT('  [Pos ', position, '] CardsXGame.id: ', id, ' | Card.id: ', id_card) 
    FROM cardsXgame 
    WHERE id_game=$GAME_ID 
      AND player_id=$PLAYER2_ID 
      AND is_in='HAND'
    ORDER BY position;
"

echo ""
echo "🔍 ACCIÓN PARENT CREADA:"
mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT CONCAT(
        '  ID: ', id, 
        ' | Type: ', action_type, 
        ' | Name: ', action_name, 
        ' | Result: ', result,
        ' | Player: ', player_id,
        ' | Direction: ', IFNULL(direction, 'NULL')
    ) 
    FROM actions_per_turn 
    WHERE id=$ACTION_PARENT;
"

echo ""
echo "🔍 ACTIONS_PER_TURN DESPUÉS DE PLAY (debería haber 1 acción parent):"
mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT CONCAT(
        '  ID: ', id, 
        ' | Type: ', action_type, 
        ' | Name: ', action_name, 
        ' | Result: ', result,
        ' | Player: ', player_id,
        ' | Parent: ', IFNULL(parent_action_id, 'NULL'),
        ' | Direction: ', IFNULL(direction, 'NULL'),
        ' | Card Given: ', IFNULL(card_given_id, 'NULL'),
        ' | Card Received: ', IFNULL(card_received_id, 'NULL')
    ) 
    FROM actions_per_turn 
    WHERE id_game=$GAME_ID
    ORDER BY id;
"

echo ""
echo "⏳ Esperando 1 segundo antes de selecciones..."
sleep 1

echo ""
echo "=========================================="
echo "   🎮 TEST 2: Player 1 selecciona carta"
echo "=========================================="
echo ""
echo "📝 Player 1 (order=1) seleccionará una carta para dar a Player 3 (su vecino izquierdo en LEFT)"
echo ""

# Obtener primera carta de Player 1 para selección
CARD_P1_SELECT=$(mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT id FROM cardsXgame 
    WHERE id_game=$GAME_ID 
      AND player_id=$PLAYER1_ID 
      AND is_in='HAND' 
    ORDER BY position ASC
    LIMIT 1;
")

# Guardar el id_card ANTES de la selección (para verificación posterior)
CARD_P1_CARD_ID_ORIGINAL=$(mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "SELECT id_card FROM cardsXgame WHERE id=$CARD_P1_SELECT;")

echo "Carta seleccionada por Player 1 (cardsXgame.id): $CARD_P1_SELECT (card_id original: $CARD_P1_CARD_ID_ORIGINAL)"

REQUEST_SELECT_P1="{
  \"action_id\": $ACTION_PARENT,
  \"card_id\": $CARD_P1_SELECT,
  \"player_id\": $PLAYER1_ID
}"
echo ""
echo "📤 Request POST /api/game/$ROOM_ID/event/dead-card-folly/select-card:"
echo "$REQUEST_SELECT_P1" | jq '.'

RESPONSE_SELECT_P1=$(curl -s -X POST "$BASE_URL/game/$ROOM_ID/event/dead-card-folly/select-card" \
  -H "Content-Type: application/json" \
  -d "$REQUEST_SELECT_P1")

echo ""
echo "📥 Response:"
echo "$RESPONSE_SELECT_P1" | jq '.'

SUCCESS_P1=$(echo "$RESPONSE_SELECT_P1" | jq -r '.success')
WAITING_P1=$(echo "$RESPONSE_SELECT_P1" | jq -r '.waiting')
PENDING_P1=$(echo "$RESPONSE_SELECT_P1" | jq -r '.pending_count')

if [ "$SUCCESS_P1" != "true" ]; then
    echo "❌ ERROR: Player 1 no pudo seleccionar carta"
    exit 1
fi

echo ""
echo "✅ Player 1 seleccionó carta"
echo "   Esperando más jugadores: $WAITING_P1"
echo "   Selecciones pendientes: $PENDING_P1"

echo ""
echo "🔍 ACTIONS_PER_TURN DESPUÉS DE SELECCIÓN P1 (debería haber 1 parent + 1 child):"
mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT CONCAT(
        '  ID: ', id, 
        ' | Type: ', action_type, 
        ' | Name: ', action_name, 
        ' | Result: ', result,
        ' | Player: ', player_id,
        ' | Parent: ', IFNULL(parent_action_id, 'NULL'),
        ' | Direction: ', IFNULL(direction, 'NULL'),
        ' | Card Given: ', IFNULL(card_given_id, 'NULL'),
        ' | Card Received: ', IFNULL(card_received_id, 'NULL')
    ) 
    FROM actions_per_turn 
    WHERE id_game=$GAME_ID
    ORDER BY id;
"

echo ""
echo "⏳ Esperando 1 segundo..."
sleep 1

echo ""
echo "=========================================="
echo "   🎮 TEST 3: Player 2 selecciona carta"
echo "=========================================="
echo ""
echo "📝 Player 2 (order=2) seleccionará una carta para dar a Player 1 (su vecino izquierdo en LEFT)"
echo ""

# Obtener primera carta de Player 2 para selección
CARD_P2_SELECT=$(mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT id FROM cardsXgame 
    WHERE id_game=$GAME_ID 
      AND player_id=$PLAYER2_ID 
      AND is_in='HAND' 
    ORDER BY position ASC
    LIMIT 1;
")

# Guardar el id_card ANTES de la selección (para verificación posterior)
CARD_P2_CARD_ID_ORIGINAL=$(mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "SELECT id_card FROM cardsXgame WHERE id=$CARD_P2_SELECT;")

echo "Carta seleccionada por Player 2 (cardsXgame.id): $CARD_P2_SELECT (card_id original: $CARD_P2_CARD_ID_ORIGINAL)"

REQUEST_SELECT_P2="{
  \"action_id\": $ACTION_PARENT,
  \"card_id\": $CARD_P2_SELECT,
  \"player_id\": $PLAYER2_ID
}"
echo ""
echo "📤 Request POST /api/game/$ROOM_ID/event/dead-card-folly/select-card:"
echo "$REQUEST_SELECT_P2" | jq '.'

RESPONSE_SELECT_P2=$(curl -s -X POST "$BASE_URL/game/$ROOM_ID/event/dead-card-folly/select-card" \
  -H "Content-Type: application/json" \
  -d "$REQUEST_SELECT_P2")

echo ""
echo "📥 Response:"
echo "$RESPONSE_SELECT_P2" | jq '.'

SUCCESS_P2=$(echo "$RESPONSE_SELECT_P2" | jq -r '.success')
WAITING_P2=$(echo "$RESPONSE_SELECT_P2" | jq -r '.waiting')
PENDING_P2=$(echo "$RESPONSE_SELECT_P2" | jq -r '.pending_count')

if [ "$SUCCESS_P2" != "true" ]; then
    echo "❌ ERROR: Player 2 no pudo seleccionar carta"
    exit 1
fi

echo ""
echo "✅ Player 2 seleccionó carta"
echo "   Esperando más jugadores: $WAITING_P2"
echo "   Selecciones pendientes: $PENDING_P2"

echo ""
echo "🔍 ACTIONS_PER_TURN DESPUÉS DE SELECCIÓN P2 (debería haber 1 parent + 2 children):"
mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT CONCAT(
        '  ID: ', id, 
        ' | Type: ', action_type, 
        ' | Name: ', action_name, 
        ' | Result: ', result,
        ' | Player: ', player_id,
        ' | Parent: ', IFNULL(parent_action_id, 'NULL'),
        ' | Direction: ', IFNULL(direction, 'NULL'),
        ' | Card Given: ', IFNULL(card_given_id, 'NULL'),
        ' | Card Received: ', IFNULL(card_received_id, 'NULL')
    ) 
    FROM actions_per_turn 
    WHERE id_game=$GAME_ID
    ORDER BY id;
"

echo ""
echo "⏳ Esperando 1 segundo..."
sleep 1

echo ""
echo "=========================================="
echo "   🎮 TEST 4: Player 3 selecciona carta (FINAL)"
echo "=========================================="
echo ""
echo "📝 Player 3 (order=3) seleccionará una carta para dar a Player 2 (su vecino izquierdo en LEFT)"
echo "   Esta es la última selección, debería completarse la rotación"
echo ""

# Obtener primera carta de Player 3 para selección
CARD_P3_SELECT=$(mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT id FROM cardsXgame 
    WHERE id_game=$GAME_ID 
      AND player_id=$PLAYER3_ID 
      AND is_in='HAND' 
    ORDER BY position ASC
    LIMIT 1;
")

# Guardar el id_card ANTES de la selección (para verificación posterior)
CARD_P3_CARD_ID_ORIGINAL=$(mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "SELECT id_card FROM cardsXgame WHERE id=$CARD_P3_SELECT;")

echo "Carta seleccionada por Player 3 (cardsXgame.id): $CARD_P3_SELECT (card_id original: $CARD_P3_CARD_ID_ORIGINAL)"

REQUEST_SELECT_P3="{
  \"action_id\": $ACTION_PARENT,
  \"card_id\": $CARD_P3_SELECT,
  \"player_id\": $PLAYER3_ID
}"
echo ""
echo "📤 Request POST /api/game/$ROOM_ID/event/dead-card-folly/select-card:"
echo "$REQUEST_SELECT_P3" | jq '.'

RESPONSE_SELECT_P3=$(curl -s -X POST "$BASE_URL/game/$ROOM_ID/event/dead-card-folly/select-card" \
  -H "Content-Type: application/json" \
  -d "$REQUEST_SELECT_P3")

echo ""
echo "📥 Response:"
echo "$RESPONSE_SELECT_P3" | jq '.'

SUCCESS_P3=$(echo "$RESPONSE_SELECT_P3" | jq -r '.success')
WAITING_P3=$(echo "$RESPONSE_SELECT_P3" | jq -r '.waiting')
PENDING_P3=$(echo "$RESPONSE_SELECT_P3" | jq -r '.pending_count')

if [ "$SUCCESS_P3" != "true" ]; then
    echo "❌ ERROR: Player 3 no pudo seleccionar carta"
    exit 1
fi

echo ""
echo "✅ Player 3 seleccionó carta (última selección)"
echo "   Esperando más jugadores: $WAITING_P3 (debería ser false)"
echo "   Selecciones pendientes: $PENDING_P3 (debería ser 0)"
echo "   🔄 ROTACIÓN COMPLETADA"

echo ""
echo "🔍 ACTIONS_PER_TURN DESPUÉS DE SELECCIÓN P3 (debería haber 1 parent + 3 children, TODOS SUCCESS):"
mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT CONCAT(
        '  ID: ', id, 
        ' | Type: ', action_type, 
        ' | Name: ', action_name, 
        ' | Result: ', result,
        ' | Player: ', player_id,
        ' | Parent: ', IFNULL(parent_action_id, 'NULL'),
        ' | Direction: ', IFNULL(direction, 'NULL'),
        ' | Card Given: ', IFNULL(card_given_id, 'NULL'),
        ' | Card Received: ', IFNULL(card_received_id, 'NULL')
    ) 
    FROM actions_per_turn 
    WHERE id_game=$GAME_ID
    ORDER BY id;
"

echo ""
echo "=========================================="
echo "   📊 VERIFICACIÓN FINAL"
echo "=========================================="
echo ""

echo "🔍 ACCIONES CREADAS (1 parent + 3 children):"
mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT CONCAT(
        '  ID: ', id, 
        ' | Type: ', action_type, 
        ' | Name: ', action_name, 
        ' | Result: ', result,
        ' | Player: ', player_id,
        ' | Parent: ', IFNULL(parent_action_id, 'NULL'),
        ' | Direction: ', IFNULL(direction, 'NULL'),
        ' | Card Given: ', IFNULL(card_given_id, 'NULL'),
        ' | Card Received: ', IFNULL(card_received_id, 'NULL')
    ) 
    FROM actions_per_turn 
    WHERE id_game=$GAME_ID
    ORDER BY id;
"

echo ""
echo "🔍 RESULTADO PARENT ACTION (debería ser SUCCESS):"
PARENT_RESULT=$(mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT result FROM actions_per_turn WHERE id=$ACTION_PARENT;
")
echo "   Result: $PARENT_RESULT"

if [ "$PARENT_RESULT" != "SUCCESS" ]; then
    echo "⚠️  WARNING: Resultado esperado SUCCESS, obtenido: $PARENT_RESULT"
fi

echo ""
echo "🔍 CHILD ACTIONS (todas deberían tener result=SUCCESS y card_received_id):"
mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT CONCAT(
        '  Player ', player_id, 
        ': card_given_id=', IFNULL(card_given_id, 'NULL'),
        ' | card_received_id=', IFNULL(card_received_id, 'NULL'),
        ' | result=', result
    ) 
    FROM actions_per_turn 
    WHERE parent_action_id=$ACTION_PARENT
    ORDER BY player_id;
"

echo ""
echo "=========================================="
echo "   🎴 ESTADO DE LAS MANOS - ANTES Y DESPUÉS"
echo "=========================================="
echo ""

echo "📋 RECORDATORIO - CARTAS SELECCIONADAS:"
echo "   Player 1 dio: cardsXgame.id=$CARD_P1_SELECT (a Player 3)"
echo "   Player 2 dio: cardsXgame.id=$CARD_P2_SELECT (a Player 1)"
echo "   Player 3 dio: cardsXgame.id=$CARD_P3_SELECT (a Player 2)"
echo ""

echo "📋 CARD_IDs ORIGINALES (ANTES del swap):"
echo "   Player 1 dio: card_id=$CARD_P1_CARD_ID_ORIGINAL"
echo "   Player 2 dio: card_id=$CARD_P2_CARD_ID_ORIGINAL"
echo "   Player 3 dio: card_id=$CARD_P3_CARD_ID_ORIGINAL"
echo ""

echo "🔍 MANO PLAYER 1 FINAL (debería tener 6 cartas - solo swapeó, no descartó):"
HAND_P1_FINAL=$(mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT COUNT(*) FROM cardsXgame 
    WHERE id_game=$GAME_ID 
      AND player_id=$PLAYER1_ID 
      AND is_in='HAND';
")
echo "   Total: $HAND_P1_FINAL cartas"
echo "   📝 Esperado: NO tiene card_id=$CARD_P1_CARD_ID_ORIGINAL (la dio), SÍ tiene card_id=$CARD_P2_CARD_ID_ORIGINAL (la recibió de Player 2)"
mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT CONCAT('  [Pos ', position, '] CardsXGame.id: ', id, ' | Card.id: ', id_card) 
    FROM cardsXgame 
    WHERE id_game=$GAME_ID 
      AND player_id=$PLAYER1_ID 
      AND is_in='HAND'
    ORDER BY position;
"

echo ""
echo "🔍 MANO PLAYER 2 FINAL (debería tener 5 cartas):"
HAND_P2_FINAL=$(mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT COUNT(*) FROM cardsXgame 
    WHERE id_game=$GAME_ID 
      AND player_id=$PLAYER2_ID 
      AND is_in='HAND';
")
echo "   Total: $HAND_P2_FINAL cartas"
echo "   📝 Esperado: NO tiene card_id=$CARD_P2_CARD_ID_ORIGINAL (la dio), SÍ tiene card_id=$CARD_P3_CARD_ID_ORIGINAL (la recibió de Player 3)"
mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT CONCAT('  [Pos ', position, '] CardsXGame.id: ', id, ' | Card.id: ', id_card) 
    FROM cardsXgame 
    WHERE id_game=$GAME_ID 
      AND player_id=$PLAYER2_ID 
      AND is_in='HAND'
    ORDER BY position;
"

echo ""
echo "🔍 MANO PLAYER 3 FINAL (debería tener 6 cartas - solo swapeó, no descartó):"
HAND_P3_FINAL=$(mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT COUNT(*) FROM cardsXgame 
    WHERE id_game=$GAME_ID 
      AND player_id=$PLAYER3_ID 
      AND is_in='HAND';
")
echo "   Total: $HAND_P3_FINAL cartas"
echo "   📝 Esperado: NO tiene card_id=$CARD_P3_CARD_ID_ORIGINAL (la dio), SÍ tiene card_id=$CARD_P1_CARD_ID_ORIGINAL (la recibió de Player 1)"
mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT CONCAT('  [Pos ', position, '] CardsXGame.id: ', id, ' | Card.id: ', id_card) 
    FROM cardsXgame 
    WHERE id_game=$GAME_ID 
      AND player_id=$PLAYER3_ID 
      AND is_in='HAND'
    ORDER BY position;
"

echo ""
echo "🔍 DISCARD FINAL (debería tener 4 cartas: 3 iniciales + Dead Card Folly):"
DISCARD_FINAL=$(mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT COUNT(*) FROM cardsXgame 
    WHERE id_game=$GAME_ID AND is_in='DISCARD';
")
echo "   Total: $DISCARD_FINAL cartas"
mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT CONCAT('  [Pos ', position, '] Card ID: ', id_card, ' (18=Dead Card Folly)') 
    FROM cardsXgame 
    WHERE id_game=$GAME_ID 
      AND is_in='DISCARD'
    ORDER BY position ASC;
"

echo ""
echo "=========================================="
echo "   🔬 VERIFICACIÓN DE ROTACIÓN"
echo "=========================================="
echo ""

# Verificar que las cartas rotaron correctamente
P1_HAS_P2_CARD=$(mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT COUNT(*) FROM cardsXgame 
    WHERE id_game=$GAME_ID 
      AND player_id=$PLAYER1_ID 
      AND id_card=$CARD_P2_CARD_ID_ORIGINAL
      AND is_in='HAND';
")

P2_HAS_P3_CARD=$(mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT COUNT(*) FROM cardsXgame 
    WHERE id_game=$GAME_ID 
      AND player_id=$PLAYER2_ID 
      AND id_card=$CARD_P3_CARD_ID_ORIGINAL
      AND is_in='HAND';
")

P3_HAS_P1_CARD=$(mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT COUNT(*) FROM cardsXgame 
    WHERE id_game=$GAME_ID 
      AND player_id=$PLAYER3_ID 
      AND id_card=$CARD_P1_CARD_ID_ORIGINAL
      AND is_in='HAND';
")

echo "🔄 ROTACIÓN LEFT (2→1→3→2):"
echo "   Player 1 recibió card_id=$CARD_P2_CARD_ID_ORIGINAL de Player 2: $([ $P1_HAS_P2_CARD -eq 1 ] && echo '✅ SÍ' || echo '❌ NO')"
echo "   Player 2 recibió card_id=$CARD_P3_CARD_ID_ORIGINAL de Player 3: $([ $P2_HAS_P3_CARD -eq 1 ] && echo '✅ SÍ' || echo '❌ NO')"
echo "   Player 3 recibió card_id=$CARD_P1_CARD_ID_ORIGINAL de Player 1: $([ $P3_HAS_P1_CARD -eq 1 ] && echo '✅ SÍ' || echo '❌ NO')"

echo ""
echo "=========================================="
echo "   ✅ RESUMEN DE VALIDACIONES"
echo "=========================================="
echo ""

ERRORS=0

if [ "$HAND_P1_FINAL" -ne 6 ]; then
    echo "❌ Player 1 debería tener 6 cartas (no jugó carta, solo swapeó), tiene: $HAND_P1_FINAL"
    ERRORS=$((ERRORS + 1))
else
    echo "✅ Player 1 tiene 6 cartas (swap sin descartar)"
fi

if [ "$HAND_P2_FINAL" -ne 5 ]; then
    echo "❌ Player 2 debería tener 5 cartas (jugó Dead Card Folly), tiene: $HAND_P2_FINAL"
    ERRORS=$((ERRORS + 1))
else
    echo "✅ Player 2 tiene 5 cartas (jugó Dead Card Folly)"
fi

if [ "$HAND_P3_FINAL" -ne 6 ]; then
    echo "❌ Player 3 debería tener 6 cartas (no jugó carta, solo swapeó), tiene: $HAND_P3_FINAL"
    ERRORS=$((ERRORS + 1))
else
    echo "✅ Player 3 tiene 6 cartas (swap sin descartar)"
fi

if [ "$DISCARD_FINAL" -ne 4 ]; then
    echo "❌ Discard debería tener 4 cartas, tiene: $DISCARD_FINAL"
    ERRORS=$((ERRORS + 1))
else
    echo "✅ Discard tiene 4 cartas"
fi

if [ "$P1_HAS_P2_CARD" -ne 1 ]; then
    echo "❌ Player 1 NO recibió la carta de Player 2"
    ERRORS=$((ERRORS + 1))
else
    echo "✅ Player 1 recibió la carta de Player 2"
fi

if [ "$P2_HAS_P3_CARD" -ne 1 ]; then
    echo "❌ Player 2 NO recibió la carta de Player 3"
    ERRORS=$((ERRORS + 1))
else
    echo "✅ Player 2 recibió la carta de Player 3"
fi

if [ "$P3_HAS_P1_CARD" -ne 1 ]; then
    echo "❌ Player 3 NO recibió la carta de Player 1"
    ERRORS=$((ERRORS + 1))
else
    echo "✅ Player 3 recibió la carta de Player 1"
fi

if [ "$PARENT_RESULT" != "SUCCESS" ]; then
    echo "❌ Parent action debería tener result=SUCCESS, tiene: $PARENT_RESULT"
    ERRORS=$((ERRORS + 1))
else
    echo "✅ Parent action tiene result=SUCCESS"
fi

echo ""
if [ $ERRORS -eq 0 ]; then
    echo "=========================================="
    echo "   🎉 TEST COMPLETADO EXITOSAMENTE"
    echo "=========================================="
    echo "   ✅ Dead Card Folly jugada con dirección LEFT"
    echo "   ✅ 3 jugadores seleccionaron cartas"
    echo "   ✅ Rotación ejecutada correctamente (2→1, 3→2, 1→3)"
    echo "   ✅ Todas las manos tienen 5 cartas"
    echo "   ✅ Descarte tiene 4 cartas"
    echo "   ✅ Acciones marcadas como SUCCESS"
else
    echo "=========================================="
    echo "   ⚠️  TEST COMPLETADO CON $ERRORS ERRORES"
    echo "=========================================="
fi
echo ""
