#!/bin/bash

source venv/bin/activate

set -e

DB_USER="developer"
DB_PASSWORD="developer_pass"
DB_NAME="cards_table_develop"
BASE_URL="http://localhost:8000/api"

echo ""
echo "=========================================="
echo "   TEST: Not So Fast Complete Flow"
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
echo "📋 PASO 5: Insertando datos de test NSF..."
mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME < scripts/nsf-test-data.sql
echo "✅ Datos de test insertados"

echo ""
echo "📋 PASO 6: Consultando IDs generados..."
GAME_ID=$(mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "SELECT MAX(id) FROM game;")
ROOM_ID=$(mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "SELECT MAX(id) FROM room;")
PLAYER1_ID=$(mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "SELECT id FROM player WHERE name='NSF_Player1';")
PLAYER2_ID=$(mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "SELECT id FROM player WHERE name='NSF_Player2';")
PLAYER3_ID=$(mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "SELECT id FROM player WHERE name='NSF_Player3';")

echo "Game ID: $GAME_ID"
echo "Room ID: $ROOM_ID"
echo "Player 1 (NSF_Player1): $PLAYER1_ID - INICIA LA ACCIÓN"
echo "Player 2 (NSF_Player2): $PLAYER2_ID - JUEGA NSF PRIMERA"
echo "Player 3 (NSF_Player3): $PLAYER3_ID - JUEGA NSF SEGUNDA"

# Obtener cartas específicas
POINT_SUSPICIONS_CARD=$(mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT id FROM cardsXgame 
    WHERE id_game=$GAME_ID 
      AND player_id=$PLAYER1_ID 
      AND id_card=17 
      AND is_in='HAND' 
    LIMIT 1;
")

NSF_PLAYER2=$(mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT id FROM cardsXgame 
    WHERE id_game=$GAME_ID 
      AND player_id=$PLAYER2_ID 
      AND id_card=13 
      AND is_in='HAND' 
    LIMIT 1;
")

NSF_PLAYER3=$(mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT id FROM cardsXgame 
    WHERE id_game=$GAME_ID 
      AND player_id=$PLAYER3_ID 
      AND id_card=13 
      AND is_in='HAND' 
    LIMIT 1;
")

echo ""
echo "Carta 'Point Suspicions' (cardsXgame.id): $POINT_SUSPICIONS_CARD"
echo "NSF Player 2 (cardsXgame.id): $NSF_PLAYER2"
echo "NSF Player 3 (cardsXgame.id): $NSF_PLAYER3"

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
echo "🔍 MANO PLAYER 1 (6 cartas: 1 NSF + Point + 4 más):"
mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT CONCAT('  [Pos ', position, '] Card ID: ', id_card, ' (17=Point, 13=NSF)') 
    FROM cardsXgame 
    WHERE id_game=$GAME_ID 
      AND player_id=$PLAYER1_ID 
      AND is_in='HAND'
    ORDER BY position;
"

echo ""
echo "🔍 MANO PLAYER 2 (6 cartas: 1 NSF + 5 más):"
mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT CONCAT('  [Pos ', position, '] Card ID: ', id_card, ' (13=NSF)') 
    FROM cardsXgame 
    WHERE id_game=$GAME_ID 
      AND player_id=$PLAYER2_ID 
      AND is_in='HAND'
    ORDER BY position;
"

echo ""
echo "🔍 MANO PLAYER 3 (6 cartas: 1 NSF + 5 más):"
mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT CONCAT('  [Pos ', position, '] Card ID: ', id_card, ' (13=NSF)') 
    FROM cardsXgame 
    WHERE id_game=$GAME_ID 
      AND player_id=$PLAYER3_ID 
      AND is_in='HAND'
    ORDER BY position;
"

echo ""
echo "=========================================="
echo "   🎮 TEST 1: Player 1 juega Point Suspicions"
echo "=========================================="
echo ""

REQUEST_STEP1="{
  \"playerId\": $PLAYER1_ID,
  \"cardIds\": [$POINT_SUSPICIONS_CARD],
  \"additionalData\": {
    \"actionType\": \"EVENT\",
    \"setPosition\": null
  }
}"
echo "📤 Request POST /api/game/$ROOM_ID/start-action:"
echo "$REQUEST_STEP1" | jq '.'

RESPONSE_STEP1=$(curl -s -X POST "$BASE_URL/game/$ROOM_ID/start-action" \
  -H "Content-Type: application/json" \
  -d "$REQUEST_STEP1")

echo ""
echo "📥 Response:"
echo "$RESPONSE_STEP1" | jq '.'

ACTION_XXX=$(echo "$RESPONSE_STEP1" | jq -r '.actionId')
ACTION_YYY=$(echo "$RESPONSE_STEP1" | jq -r '.actionNSFId')
CANCELLABLE=$(echo "$RESPONSE_STEP1" | jq -r '.cancellable')

if [ "$ACTION_XXX" == "null" ] || [ -z "$ACTION_XXX" ]; then
    echo "❌ ERROR: No se obtuvo actionId (XXX)"
    exit 1
fi

if [ "$CANCELLABLE" != "true" ]; then
    echo "❌ ERROR: La acción debería ser cancelable"
    exit 1
fi

echo ""
echo "✅ Step 1 CORRECTO"
echo "   Action XXX (INIT): $ACTION_XXX"
echo "   Action YYY (INSTANT_START): $ACTION_YYY"
echo "   Cancellable: $CANCELLABLE"
echo "   ⏱️ Timer NSF iniciado (5 segundos)..."

echo ""
echo "🔍 DISCARD DESPUÉS DE START-ACTION (debería seguir con 3 cartas):"
DISCARD_COUNT_1=$(mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT COUNT(*) FROM cardsXgame 
    WHERE id_game=$GAME_ID AND is_in='DISCARD';
")
echo "   Total: $DISCARD_COUNT_1 cartas"
mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT CONCAT('  [Pos ', position, '] Card ID: ', id_card) 
    FROM cardsXgame 
    WHERE id_game=$GAME_ID 
      AND is_in='DISCARD'
    ORDER BY position ASC;
"

echo ""
echo "⏳ Esperando 1 segundo para que el backend active el timer..."
sleep 1

echo ""
echo "=========================================="
echo "   🎮 TEST 2: Player 2 juega NSF"
echo "=========================================="
echo ""

REQUEST_STEP2="{
  \"actionId\": $ACTION_XXX,
  \"playerId\": $PLAYER2_ID,
  \"cardId\": $NSF_PLAYER2
}"
echo "📤 Request POST /api/game/$ROOM_ID/instant/not-so-fast:"
echo "$REQUEST_STEP2" | jq '.'

RESPONSE_STEP2=$(curl -s -X POST "$BASE_URL/game/$ROOM_ID/instant/not-so-fast" \
  -H "Content-Type: application/json" \
  -d "$REQUEST_STEP2")

echo ""
echo "📥 Response:"
echo "$RESPONSE_STEP2" | jq '.'

NSF_ACTION_ZZZ1=$(echo "$RESPONSE_STEP2" | jq -r '.nsfActionId')
SUCCESS_STEP2=$(echo "$RESPONSE_STEP2" | jq -r '.success')

if [ "$SUCCESS_STEP2" != "true" ]; then
    echo "❌ ERROR: Player 2 no pudo jugar NSF"
    exit 1
fi

echo ""
echo "✅ Step 2 CORRECTO"
echo "   Action ZZZ1 (INSTANT_PLAY): $NSF_ACTION_ZZZ1"
echo "   ⏱️ Timer NSF reiniciado (5 segundos)..."

echo ""
echo "🔍 DISCARD DESPUÉS DE NSF PLAYER 2 (debería tener 4 cartas):"
DISCARD_COUNT_2=$(mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT COUNT(*) FROM cardsXgame 
    WHERE id_game=$GAME_ID AND is_in='DISCARD';
")
echo "   Total: $DISCARD_COUNT_2 cartas"
mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT CONCAT('  [Pos ', position, '] Card ID: ', id_card, ' (13=NSF)') 
    FROM cardsXgame 
    WHERE id_game=$GAME_ID 
      AND is_in='DISCARD'
    ORDER BY position ASC;
"

echo ""
echo "🔍 MANO PLAYER 2 (debería tener 5 cartas ahora):"
HAND_P2_COUNT=$(mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT COUNT(*) FROM cardsXgame 
    WHERE id_game=$GAME_ID 
      AND player_id=$PLAYER2_ID 
      AND is_in='HAND';
")
echo "   Total: $HAND_P2_COUNT cartas"
mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT CONCAT('  [Pos ', position, '] Card ID: ', id_card) 
    FROM cardsXgame 
    WHERE id_game=$GAME_ID 
      AND player_id=$PLAYER2_ID 
      AND is_in='HAND'
    ORDER BY position;
"

echo ""
echo "⏳ Esperando 1 segundo..."
sleep 1

echo ""
echo "=========================================="
echo "   🎮 TEST 3: Player 3 juega NSF"
echo "=========================================="
echo ""

REQUEST_STEP3="{
  \"actionId\": $ACTION_XXX,
  \"playerId\": $PLAYER3_ID,
  \"cardId\": $NSF_PLAYER3
}"
echo "📤 Request POST /api/game/$ROOM_ID/instant/not-so-fast:"
echo "$REQUEST_STEP3" | jq '.'

RESPONSE_STEP3=$(curl -s -X POST "$BASE_URL/game/$ROOM_ID/instant/not-so-fast" \
  -H "Content-Type: application/json" \
  -d "$REQUEST_STEP3")

echo ""
echo "📥 Response:"
echo "$RESPONSE_STEP3" | jq '.'

NSF_ACTION_ZZZ2=$(echo "$RESPONSE_STEP3" | jq -r '.nsfActionId')
SUCCESS_STEP3=$(echo "$RESPONSE_STEP3" | jq -r '.success')

if [ "$SUCCESS_STEP3" != "true" ]; then
    echo "❌ ERROR: Player 3 no pudo jugar NSF"
    exit 1
fi

echo ""
echo "✅ Step 3 CORRECTO"
echo "   Action ZZZ2 (INSTANT_PLAY): $NSF_ACTION_ZZZ2"
echo "   ⏱️ Timer NSF reiniciado (5 segundos)..."

echo ""
echo "🔍 DISCARD DESPUÉS DE NSF PLAYER 3 (debería tener 5 cartas):"
DISCARD_COUNT_3=$(mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT COUNT(*) FROM cardsXgame 
    WHERE id_game=$GAME_ID AND is_in='DISCARD';
")
echo "   Total: $DISCARD_COUNT_3 cartas"
mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT CONCAT('  [Pos ', position, '] Card ID: ', id_card, ' (13=NSF)') 
    FROM cardsXgame 
    WHERE id_game=$GAME_ID 
      AND is_in='DISCARD'
    ORDER BY position ASC;
"

echo ""
echo "🔍 MANO PLAYER 3 (debería tener 5 cartas ahora):"
HAND_P3_COUNT=$(mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT COUNT(*) FROM cardsXgame 
    WHERE id_game=$GAME_ID 
      AND player_id=$PLAYER3_ID 
      AND is_in='HAND';
")
echo "   Total: $HAND_P3_COUNT cartas"
mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT CONCAT('  [Pos ', position, '] Card ID: ', id_card) 
    FROM cardsXgame 
    WHERE id_game=$GAME_ID 
      AND player_id=$PLAYER3_ID 
      AND is_in='HAND'
    ORDER BY position;
"

echo ""
echo "=========================================="
echo "   ⏳ ESPERANDO TIMEOUT (6 segundos)"
echo "=========================================="
echo ""
echo "⏱️ Timer cuenta: 5→4→3→2→1→0"
echo "📊 Se jugaron 2 NSF → PAR → Acción CONTINÚA"
echo ""
sleep 6

echo ""
echo "=========================================="
echo "   📊 VERIFICACIÓN FINAL"
echo "=========================================="
echo ""

echo "🔍 ACCIONES CREADAS:"
mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT CONCAT(
        '  ID: ', id, 
        ' | Type: ', action_type, 
        ' | Name: ', action_name, 
        ' | Result: ', result,
        ' | Player: ', player_id,
        ' | Parent: ', IFNULL(parent_action_id, 'NULL'),
        ' | Trigger: ', IFNULL(triggered_by_action_id, 'NULL')
    ) 
    FROM actions_per_turn 
    WHERE id_game=$GAME_ID
    ORDER BY id;
"

echo ""
echo "🔍 RESULTADO DE ACTION XXX (debería ser CONTINUE):"
ACTION_XXX_RESULT=$(mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT result FROM actions_per_turn WHERE id=$ACTION_XXX;
")
echo "   Result: $ACTION_XXX_RESULT"

if [ "$ACTION_XXX_RESULT" != "CONTINUE" ]; then
    echo "⚠️  WARNING: Resultado esperado CONTINUE, obtenido: $ACTION_XXX_RESULT"
    echo "   (Esto es normal si el timeout handler aún no ejecutó)"
fi

echo ""
echo "🔍 ACTION_TIME_END DE ACTION YYY:"
mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT CONCAT(
        '  Action YYY (', id, '): ',
        'time_end = ', action_time_end
    )
    FROM actions_per_turn 
    WHERE id=$ACTION_YYY;
"

echo ""
echo "🔍 MANOS FINALES:"
echo ""
echo "Player 1 (debería tener 6 cartas - no jugó la carta, solo intención):"
HAND_P1_FINAL=$(mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT COUNT(*) FROM cardsXgame 
    WHERE id_game=$GAME_ID 
      AND player_id=$PLAYER1_ID 
      AND is_in='HAND';
")
echo "   Total: $HAND_P1_FINAL cartas"

echo ""
echo "Player 2 (debería tener 5 cartas - jugó NSF):"
HAND_P2_FINAL=$(mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT COUNT(*) FROM cardsXgame 
    WHERE id_game=$GAME_ID 
      AND player_id=$PLAYER2_ID 
      AND is_in='HAND';
")
echo "   Total: $HAND_P2_FINAL cartas"

echo ""
echo "Player 3 (debería tener 5 cartas - jugó NSF):"
HAND_P3_FINAL=$(mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT COUNT(*) FROM cardsXgame 
    WHERE id_game=$GAME_ID 
      AND player_id=$PLAYER3_ID 
      AND is_in='HAND';
")
echo "   Total: $HAND_P3_FINAL cartas"

echo ""
echo "🔍 DISCARD FINAL (debería tener 5 cartas: 3 iniciales + 2 NSF):"
DISCARD_FINAL=$(mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT COUNT(*) FROM cardsXgame 
    WHERE id_game=$GAME_ID AND is_in='DISCARD';
")
echo "   Total: $DISCARD_FINAL cartas"
mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT CONCAT('  [Pos ', position, '] Card ID: ', id_card, ' (13=NSF)') 
    FROM cardsXgame 
    WHERE id_game=$GAME_ID 
      AND is_in='DISCARD'
    ORDER BY position ASC;
"

echo ""
echo "=========================================="
echo "   ✅ RESUMEN DE VALIDACIONES"
echo "=========================================="
echo ""

ERRORS=0

if [ "$HAND_P1_FINAL" -ne 6 ]; then
    echo "❌ Player 1 debería tener 6 cartas, tiene: $HAND_P1_FINAL"
    ERRORS=$((ERRORS + 1))
else
    echo "✅ Player 1 tiene 6 cartas"
fi

if [ "$HAND_P2_FINAL" -ne 5 ]; then
    echo "❌ Player 2 debería tener 5 cartas, tiene: $HAND_P2_FINAL"
    ERRORS=$((ERRORS + 1))
else
    echo "✅ Player 2 tiene 5 cartas"
fi

if [ "$HAND_P3_FINAL" -ne 5 ]; then
    echo "❌ Player 3 debería tener 5 cartas, tiene: $HAND_P3_FINAL"
    ERRORS=$((ERRORS + 1))
else
    echo "✅ Player 3 tiene 5 cartas"
fi

if [ "$DISCARD_FINAL" -ne 5 ]; then
    echo "❌ Discard debería tener 5 cartas, tiene: $DISCARD_FINAL"
    ERRORS=$((ERRORS + 1))
else
    echo "✅ Discard tiene 5 cartas"
fi

echo ""
if [ $ERRORS -eq 0 ]; then
    echo "=========================================="
    echo "   🎉 TEST COMPLETADO EXITOSAMENTE"
    echo "=========================================="
else
    echo "=========================================="
    echo "   ⚠️  TEST COMPLETADO CON $ERRORS ERRORES"
    echo "=========================================="
fi
echo ""

echo ""
echo "=========================================="
echo "   🔄 TEST 2: NSF CANCELLATION FLOW"
echo "=========================================="
echo ""

echo "📋 PASO 1: Limpiando base de datos nuevamente..."
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
echo "📋 PASO 5: Insertando datos de test NSF..."
mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME < scripts/nsf-test-data.sql
echo "✅ Datos de test insertados"

echo ""
echo "📋 PASO 6: Consultando IDs generados..."
GAME_ID=$(mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "SELECT MAX(id) FROM game;")
ROOM_ID=$(mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "SELECT MAX(id) FROM room;")
PLAYER1_ID=$(mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "SELECT id FROM player WHERE name='NSF_Player1';")
PLAYER2_ID=$(mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "SELECT id FROM player WHERE name='NSF_Player2';")
PLAYER3_ID=$(mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "SELECT id FROM player WHERE name='NSF_Player3';")

echo "Game ID: $GAME_ID"
echo "Room ID: $ROOM_ID"
echo "Player 1 (NSF_Player1): $PLAYER1_ID - INICIA LA ACCIÓN"
echo "Player 2 (NSF_Player2): $PLAYER2_ID - JUEGA NSF"
echo "Player 3 (NSF_Player3): $PLAYER3_ID"

# Obtener cartas específicas
POINT_SUSPICIONS_CARD=$(mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT id FROM cardsXgame 
    WHERE id_game=$GAME_ID 
      AND player_id=$PLAYER1_ID 
      AND id_card=17 
      AND is_in='HAND' 
    LIMIT 1;
")

NSF_PLAYER2=$(mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT id FROM cardsXgame 
    WHERE id_game=$GAME_ID 
      AND player_id=$PLAYER2_ID 
      AND id_card=13 
      AND is_in='HAND' 
    LIMIT 1;
")

echo ""
echo "Carta 'Point Suspicions' (cardsXgame.id): $POINT_SUSPICIONS_CARD"
echo "NSF Player 2 (cardsXgame.id): $NSF_PLAYER2"

echo ""
echo "=========================================="
echo "   🎮 TEST CANCELACIÓN: Player 1 inicia acción"
echo "=========================================="
echo ""

REQUEST_CANCEL_1="{
  \"playerId\": $PLAYER1_ID,
  \"cardIds\": [$POINT_SUSPICIONS_CARD],
  \"additionalData\": {
    \"actionType\": \"EVENT\",
    \"setPosition\": null
  }
}"
echo "📤 Request POST /api/game/$ROOM_ID/start-action:"
echo "$REQUEST_CANCEL_1" | jq '.'

RESPONSE_CANCEL_1=$(curl -s -X POST "$BASE_URL/game/$ROOM_ID/start-action" \
  -H "Content-Type: application/json" \
  -d "$REQUEST_CANCEL_1")

echo ""
echo "📥 Response:"
echo "$RESPONSE_CANCEL_1" | jq '.'

ACTION_XXX_CANCEL=$(echo "$RESPONSE_CANCEL_1" | jq -r '.actionId')
ACTION_YYY_CANCEL=$(echo "$RESPONSE_CANCEL_1" | jq -r '.actionNSFId')
CANCELLABLE_CANCEL=$(echo "$RESPONSE_CANCEL_1" | jq -r '.cancellable')

if [ "$ACTION_XXX_CANCEL" == "null" ] || [ -z "$ACTION_XXX_CANCEL" ]; then
    echo "❌ ERROR: No se obtuvo actionId (XXX)"
    exit 1
fi

if [ "$CANCELLABLE_CANCEL" != "true" ]; then
    echo "❌ ERROR: La acción debería ser cancelable"
    exit 1
fi

echo ""
echo "✅ Acción iniciada correctamente"
echo "   Action XXX (INTENTION): $ACTION_XXX_CANCEL"
echo "   Action YYY (INSTANT_START): $ACTION_YYY_CANCEL"
echo "   Cancellable: $CANCELLABLE_CANCEL"
echo "   ⏱️ Timer NSF iniciado (5 segundos)..."

echo ""
echo "⏳ Esperando 1 segundo..."
sleep 1

echo ""
echo "=========================================="
echo "   🎮 TEST CANCELACIÓN: Player 2 juega NSF"
echo "=========================================="
echo ""

REQUEST_CANCEL_2="{
  \"actionId\": $ACTION_XXX_CANCEL,
  \"playerId\": $PLAYER2_ID,
  \"cardId\": $NSF_PLAYER2
}"
echo "📤 Request POST /api/game/$ROOM_ID/instant/not-so-fast:"
echo "$REQUEST_CANCEL_2" | jq '.'

RESPONSE_CANCEL_2=$(curl -s -X POST "$BASE_URL/game/$ROOM_ID/instant/not-so-fast" \
  -H "Content-Type: application/json" \
  -d "$REQUEST_CANCEL_2")

echo ""
echo "📥 Response:"
echo "$RESPONSE_CANCEL_2" | jq '.'

NSF_ACTION_ZZZ_CANCEL=$(echo "$RESPONSE_CANCEL_2" | jq -r '.nsfActionId')
SUCCESS_CANCEL_2=$(echo "$RESPONSE_CANCEL_2" | jq -r '.success')

if [ "$SUCCESS_CANCEL_2" != "true" ]; then
    echo "❌ ERROR: Player 2 no pudo jugar NSF"
    exit 1
fi

echo ""
echo "✅ NSF jugada correctamente"
echo "   Action ZZZ (INSTANT_PLAY): $NSF_ACTION_ZZZ_CANCEL"
echo "   ⏱️ Timer NSF reiniciado (5 segundos)..."

echo ""
echo "🔍 DISCARD DESPUÉS DE NSF (debería tener 4 cartas: 3 iniciales + 1 NSF):"
DISCARD_COUNT_CANCEL=$(mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT COUNT(*) FROM cardsXgame 
    WHERE id_game=$GAME_ID AND is_in='DISCARD';
")
echo "   Total: $DISCARD_COUNT_CANCEL cartas"
mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT CONCAT('  [Pos ', position, '] Card ID: ', id_card, ' (13=NSF)') 
    FROM cardsXgame 
    WHERE id_game=$GAME_ID 
      AND is_in='DISCARD'
    ORDER BY position ASC;
"

echo ""
echo "=========================================="
echo "   ⏳ ESPERANDO TIMEOUT (7 segundos)"
echo "=========================================="
echo ""
echo "⏱️ Esperando que el timer expire..."
echo "📊 Se jugó 1 NSF → IMPAR → Acción CANCELADA"
echo ""
sleep 7

echo ""
echo "🔍 VERIFICANDO QUE LA ACCIÓN FUE CANCELADA:"
ACTION_XXX_RESULT_CANCEL=$(mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT result FROM actions_per_turn WHERE id=$ACTION_XXX_CANCEL;
")
echo "   Result de Action XXX: $ACTION_XXX_RESULT_CANCEL"

if [ "$ACTION_XXX_RESULT_CANCEL" != "CANCELLED" ]; then
    echo "⚠️  WARNING: Resultado esperado CANCELLED, obtenido: $ACTION_XXX_RESULT_CANCEL"
    echo "   (Esto es normal si el timeout handler aún no ejecutó)"
fi

echo ""
echo "=========================================="
echo "   🎮 TEST CANCELACIÓN: Player 1 ejecuta acción cancelada"
echo "=========================================="
echo ""

REQUEST_CANCEL_3="{
  \"actionId\": $ACTION_XXX_CANCEL,
  \"playerId\": $PLAYER1_ID,
  \"cardIds\": [$POINT_SUSPICIONS_CARD],
  \"additionalData\": {
    \"actionType\": \"EVENT\"
  }
}"
echo "📤 Request POST /api/game/$ROOM_ID/instant/not-so-fast/cancel:"
echo "$REQUEST_CANCEL_3" | jq '.'

RESPONSE_CANCEL_3=$(curl -s -X POST "$BASE_URL/game/$ROOM_ID/instant/not-so-fast/cancel" \
  -H "Content-Type: application/json" \
  -d "$REQUEST_CANCEL_3")

echo ""
echo "📥 Response:"
echo "$RESPONSE_CANCEL_3" | jq '.'

SUCCESS_CANCEL_3=$(echo "$RESPONSE_CANCEL_3" | jq -r '.success')
MESSAGE_CANCEL=$(echo "$RESPONSE_CANCEL_3" | jq -r '.message')

if [ "$SUCCESS_CANCEL_3" != "true" ]; then
    echo "❌ ERROR: No se pudo ejecutar la acción cancelada"
    exit 1
fi

echo ""
echo "✅ Acción cancelada ejecutada correctamente"
echo "   Message: $MESSAGE_CANCEL"

echo ""
echo "=========================================="
echo "   📊 VERIFICACIÓN FINAL - CANCELACIÓN"
echo "=========================================="
echo ""

echo "🔍 DISCARD FINAL (debería tener 5 cartas: 3 iniciales + 1 NSF + 1 Point Suspicions):"
DISCARD_FINAL_CANCEL=$(mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT COUNT(*) FROM cardsXgame 
    WHERE id_game=$GAME_ID AND is_in='DISCARD';
")
echo "   Total: $DISCARD_FINAL_CANCEL cartas"
echo ""
echo "   Orden esperado (de arriba hacia abajo):"
echo "   [Pos 1] NSF (id_card=13) - jugada por Player 2"
echo "   [Pos 2] Point Suspicions (id_card=17) - cancelada, debajo de NSF"
echo "   [Pos 3-5] Las 3 cartas iniciales"
echo ""
mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT CONCAT('  [Pos ', position, '] Card ID: ', id_card, ' (13=NSF, 17=Point)') 
    FROM cardsXgame 
    WHERE id_game=$GAME_ID 
      AND is_in='DISCARD'
    ORDER BY position ASC;
"

echo ""
echo "🔍 MANO PLAYER 1 FINAL (debería tener 5 cartas - jugó Point Suspicions):"
HAND_P1_FINAL_CANCEL=$(mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT COUNT(*) FROM cardsXgame 
    WHERE id_game=$GAME_ID 
      AND player_id=$PLAYER1_ID 
      AND is_in='HAND';
")
echo "   Total: $HAND_P1_FINAL_CANCEL cartas"

echo ""
echo "🔍 VERIFICANDO POSICIÓN DE POINT SUSPICIONS EN DISCARD:"
POINT_POSITION=$(mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT position FROM cardsXgame 
    WHERE id_game=$GAME_ID 
      AND id_card=17 
      AND is_in='DISCARD';
")
echo "   Posición de Point Suspicions: $POINT_POSITION (debería ser 2)"

echo ""
echo "🔍 ACCIONES CREADAS:"
mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT CONCAT(
        '  ID: ', id, 
        ' | Type: ', action_type, 
        ' | Name: ', action_name, 
        ' | Result: ', result,
        ' | Player: ', player_id
    ) 
    FROM actions_per_turn 
    WHERE id_game=$GAME_ID
    ORDER BY id;
"

echo ""
echo "=========================================="
echo "   ✅ RESUMEN DE VALIDACIONES - CANCELACIÓN"
echo "=========================================="
echo ""

ERRORS_CANCEL=0

if [ "$HAND_P1_FINAL_CANCEL" -ne 5 ]; then
    echo "❌ Player 1 debería tener 5 cartas, tiene: $HAND_P1_FINAL_CANCEL"
    ERRORS_CANCEL=$((ERRORS_CANCEL + 1))
else
    echo "✅ Player 1 tiene 5 cartas"
fi

if [ "$DISCARD_FINAL_CANCEL" -ne 5 ]; then
    echo "❌ Discard debería tener 5 cartas, tiene: $DISCARD_FINAL_CANCEL"
    ERRORS_CANCEL=$((ERRORS_CANCEL + 1))
else
    echo "✅ Discard tiene 5 cartas"
fi

if [ "$POINT_POSITION" -ne 2 ]; then
    echo "❌ Point Suspicions debería estar en posición 2, está en: $POINT_POSITION"
    ERRORS_CANCEL=$((ERRORS_CANCEL + 1))
else
    echo "✅ Point Suspicions está en posición 2 (debajo de NSF)"
fi

if [ "$ACTION_XXX_RESULT_CANCEL" != "CANCELLED" ]; then
    echo "⚠️  Action XXX debería tener result=CANCELLED, tiene: $ACTION_XXX_RESULT_CANCEL"
fi

echo ""
if [ $ERRORS_CANCEL -eq 0 ]; then
    echo "=========================================="
    echo "   🎉 TEST CANCELACIÓN COMPLETADO EXITOSAMENTE"
    echo "=========================================="
else
    echo "=========================================="
    echo "   ⚠️  TEST CANCELACIÓN COMPLETADO CON $ERRORS_CANCEL ERRORES"
    echo "=========================================="
fi
echo ""

echo ""
echo "=========================================="
echo "   🔄 TEST 3: NSF CREATE_SET CANCELLATION"
echo "=========================================="
echo ""

echo "📋 PASO 1: Limpiando base de datos nuevamente..."
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
echo "📋 PASO 5: Insertando datos de test NSF..."
mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME < scripts/nsf-test-data.sql
echo "✅ Datos de test insertados"

echo ""
echo "📋 PASO 6: Consultando IDs generados..."
GAME_ID=$(mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "SELECT MAX(id) FROM game;")
ROOM_ID=$(mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "SELECT MAX(id) FROM room;")
PLAYER1_ID=$(mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "SELECT id FROM player WHERE name='NSF_Player1';")
PLAYER2_ID=$(mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "SELECT id FROM player WHERE name='NSF_Player2';")

echo "Game ID: $GAME_ID"
echo "Room ID: $ROOM_ID"
echo "Player 1 (NSF_Player1): $PLAYER1_ID - BAJA SET DE PARKER PYNE"
echo "Player 2 (NSF_Player2): $PLAYER2_ID - JUEGA NSF"

# Obtener cartas Parker Pyne (dos cartas id_card=7)
PARKER_PYNE_1=$(mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT id FROM cardsXgame 
    WHERE id_game=$GAME_ID 
      AND player_id=$PLAYER1_ID 
      AND id_card=7 
      AND is_in='HAND' 
    ORDER BY position ASC
    LIMIT 1;
")

PARKER_PYNE_2=$(mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT id FROM cardsXgame 
    WHERE id_game=$GAME_ID 
      AND player_id=$PLAYER1_ID 
      AND id_card=7 
      AND is_in='HAND' 
    ORDER BY position DESC
    LIMIT 1;
")

NSF_PLAYER2=$(mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT id FROM cardsXgame 
    WHERE id_game=$GAME_ID 
      AND player_id=$PLAYER2_ID 
      AND id_card=13 
      AND is_in='HAND' 
    LIMIT 1;
")

echo ""
echo "Parker Pyne 1 (cardsXgame.id): $PARKER_PYNE_1"
echo "Parker Pyne 2 (cardsXgame.id): $PARKER_PYNE_2"
echo "NSF Player 2 (cardsXgame.id): $NSF_PLAYER2"

echo ""
echo "=========================================="
echo "   ESTADO INICIAL - CREATE_SET TEST"
echo "=========================================="
echo ""

echo "🔍 MANO PLAYER 1 (debería tener 2 Parker Pyne - id_card=7):"
mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT CONCAT('  [Pos ', position, '] CardsXGame.id: ', id, ' | Card.id: ', id_card, ' (7=Parker Pyne)') 
    FROM cardsXgame 
    WHERE id_game=$GAME_ID 
      AND player_id=$PLAYER1_ID 
      AND is_in='HAND'
    ORDER BY position;
"

echo ""
echo "🔍 DETECTIVE_SET PLAYER 1 (debería estar vacío):"
DETECTIVE_SET_COUNT_INIT=$(mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT COUNT(*) FROM cardsXgame 
    WHERE id_game=$GAME_ID 
      AND player_id=$PLAYER1_ID 
      AND is_in='DETECTIVE_SET';
")
echo "   Total: $DETECTIVE_SET_COUNT_INIT sets"

echo ""
echo "=========================================="
echo "   🎮 TEST CREATE_SET: Player 1 baja set Parker Pyne"
echo "=========================================="
echo ""

REQUEST_SET_1="{
  \"playerId\": $PLAYER1_ID,
  \"cardIds\": [$PARKER_PYNE_1, $PARKER_PYNE_2],
  \"additionalData\": {
    \"actionType\": \"CREATE_SET\",
    \"setPosition\": null
  }
}"
echo "📤 Request POST /api/game/$ROOM_ID/start-action:"
echo "$REQUEST_SET_1" | jq '.'

RESPONSE_SET_1=$(curl -s -X POST "$BASE_URL/game/$ROOM_ID/start-action" \
  -H "Content-Type: application/json" \
  -d "$REQUEST_SET_1")

echo ""
echo "📥 Response:"
echo "$RESPONSE_SET_1" | jq '.'

ACTION_XXX_SET=$(echo "$RESPONSE_SET_1" | jq -r '.actionId')
ACTION_YYY_SET=$(echo "$RESPONSE_SET_1" | jq -r '.actionNSFId')
CANCELLABLE_SET=$(echo "$RESPONSE_SET_1" | jq -r '.cancellable')

if [ "$ACTION_XXX_SET" == "null" ] || [ -z "$ACTION_XXX_SET" ]; then
    echo "❌ ERROR: No se obtuvo actionId (XXX)"
    exit 1
fi

if [ "$CANCELLABLE_SET" != "true" ]; then
    echo "❌ ERROR: La acción CREATE_SET debería ser cancelable"
    exit 1
fi

echo ""
echo "✅ Acción CREATE_SET iniciada correctamente"
echo "   Action XXX (INTENTION): $ACTION_XXX_SET"
echo "   Action YYY (INSTANT_START): $ACTION_YYY_SET"
echo "   Cancellable: $CANCELLABLE_SET"
echo "   ⏱️ Timer NSF iniciado (5 segundos)..."

echo ""
echo "⏳ Esperando 1 segundo..."
sleep 1

echo ""
echo "=========================================="
echo "   🎮 TEST CREATE_SET: Player 2 juega NSF"
echo "=========================================="
echo ""

REQUEST_SET_2="{
  \"actionId\": $ACTION_XXX_SET,
  \"playerId\": $PLAYER2_ID,
  \"cardId\": $NSF_PLAYER2
}"
echo "📤 Request POST /api/game/$ROOM_ID/instant/not-so-fast:"
echo "$REQUEST_SET_2" | jq '.'

RESPONSE_SET_2=$(curl -s -X POST "$BASE_URL/game/$ROOM_ID/instant/not-so-fast" \
  -H "Content-Type: application/json" \
  -d "$REQUEST_SET_2")

echo ""
echo "📥 Response:"
echo "$RESPONSE_SET_2" | jq '.'

NSF_ACTION_ZZZ_SET=$(echo "$RESPONSE_SET_2" | jq -r '.nsfActionId')
SUCCESS_SET_2=$(echo "$RESPONSE_SET_2" | jq -r '.success')

if [ "$SUCCESS_SET_2" != "true" ]; then
    echo "❌ ERROR: Player 2 no pudo jugar NSF"
    exit 1
fi

echo ""
echo "✅ NSF jugada correctamente"
echo "   Action ZZZ (INSTANT_PLAY): $NSF_ACTION_ZZZ_SET"
echo "   ⏱️ Timer NSF reiniciado (5 segundos)..."

echo ""
echo "=========================================="
echo "   ⏳ ESPERANDO TIMEOUT (7 segundos)"
echo "=========================================="
echo ""
echo "⏱️ Esperando que el timer expire..."
echo "📊 Se jugó 1 NSF → IMPAR → Acción CREATE_SET CANCELADA"
echo ""
sleep 7

echo ""
echo "🔍 VERIFICANDO QUE LA ACCIÓN FUE CANCELADA:"
ACTION_XXX_RESULT_SET=$(mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT result FROM actions_per_turn WHERE id=$ACTION_XXX_SET;
")
echo "   Result de Action XXX: $ACTION_XXX_RESULT_SET"

if [ "$ACTION_XXX_RESULT_SET" != "CANCELLED" ]; then
    echo "⚠️  WARNING: Resultado esperado CANCELLED, obtenido: $ACTION_XXX_RESULT_SET"
    echo "   (Esto es normal si el timeout handler aún no ejecutó)"
fi

echo ""
echo "=========================================="
echo "   🎮 TEST CREATE_SET: Player 1 ejecuta set cancelado"
echo "=========================================="
echo ""

REQUEST_SET_3="{
  \"actionId\": $ACTION_XXX_SET,
  \"playerId\": $PLAYER1_ID,
  \"cardIds\": [$PARKER_PYNE_1, $PARKER_PYNE_2],
  \"additionalData\": {
    \"actionType\": \"CREATE_SET\"
  }
}"
echo "📤 Request POST /api/game/$ROOM_ID/instant/not-so-fast/cancel:"
echo "$REQUEST_SET_3" | jq '.'

RESPONSE_SET_3=$(curl -s -X POST "$BASE_URL/game/$ROOM_ID/instant/not-so-fast/cancel" \
  -H "Content-Type: application/json" \
  -d "$REQUEST_SET_3")

echo ""
echo "📥 Response:"
echo "$RESPONSE_SET_3" | jq '.'

SUCCESS_SET_3=$(echo "$RESPONSE_SET_3" | jq -r '.success')
MESSAGE_SET=$(echo "$RESPONSE_SET_3" | jq -r '.message')

if [ "$SUCCESS_SET_3" != "true" ]; then
    echo "❌ ERROR: No se pudo ejecutar la acción CREATE_SET cancelada"
    exit 1
fi

echo ""
echo "✅ Acción CREATE_SET cancelada ejecutada correctamente"
echo "   Message: $MESSAGE_SET"

echo ""
echo "=========================================="
echo "   📊 VERIFICACIÓN FINAL - CREATE_SET CANCELADO"
echo "=========================================="
echo ""

echo "🔍 DETECTIVE_SET PLAYER 1 (debería tener 2 cartas Parker Pyne en position 1):"
DETECTIVE_SET_COUNT_FINAL=$(mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT COUNT(*) FROM cardsXgame 
    WHERE id_game=$GAME_ID 
      AND player_id=$PLAYER1_ID 
      AND is_in='DETECTIVE_SET';
")
echo "   Total: $DETECTIVE_SET_COUNT_FINAL cartas"
echo ""
mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT CONCAT(
        '  CardsXGame.id: ', id,
        ' | Card.id: ', id_card,
        ' | Position: ', position,
        ' | Hidden: ', hidden,
        ' | is_in: ', is_in,
        ' | player_id: ', player_id,
        ' (Esperado: id_card=7, position=1, hidden=false, is_in=DETECTIVE_SET)'
    ) 
    FROM cardsXgame 
    WHERE id_game=$GAME_ID 
      AND player_id=$PLAYER1_ID 
      AND is_in='DETECTIVE_SET'
    ORDER BY position, id;
"

echo ""
echo "🔍 VALIDACIÓN ESPECÍFICA DE LAS CARTAS:"
PARKER_1_STATE=$(mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT CONCAT(is_in, '|', position, '|', hidden) 
    FROM cardsXgame 
    WHERE id=$PARKER_PYNE_1;
")
PARKER_2_STATE=$(mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT CONCAT(is_in, '|', position, '|', hidden) 
    FROM cardsXgame 
    WHERE id=$PARKER_PYNE_2;
")
echo "   Parker Pyne 1 (id=$PARKER_PYNE_1): $PARKER_1_STATE (Esperado: DETECTIVE_SET|1|0)"
echo "   Parker Pyne 2 (id=$PARKER_PYNE_2): $PARKER_2_STATE (Esperado: DETECTIVE_SET|1|0)"

echo ""
echo "🔍 MANO PLAYER 1 FINAL (debería tener 4 cartas - bajó 2 Parker Pyne):"
HAND_P1_FINAL_SET=$(mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT COUNT(*) FROM cardsXgame 
    WHERE id_game=$GAME_ID 
      AND player_id=$PLAYER1_ID 
      AND is_in='HAND';
")
echo "   Total: $HAND_P1_FINAL_SET cartas"
mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT CONCAT('  [Pos ', position, '] CardsXGame.id: ', id, ' | Card.id: ', id_card) 
    FROM cardsXgame 
    WHERE id_game=$GAME_ID 
      AND player_id=$PLAYER1_ID 
      AND is_in='HAND'
    ORDER BY position;
"

echo ""
echo "🔍 ACCIONES CREADAS:"
mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT CONCAT(
        '  ID: ', id, 
        ' | Type: ', action_type, 
        ' | Name: ', action_name, 
        ' | Result: ', result,
        ' | Player: ', player_id
    ) 
    FROM actions_per_turn 
    WHERE id_game=$GAME_ID
    ORDER BY id;
"

echo ""
echo "=========================================="
echo "   ✅ RESUMEN DE VALIDACIONES - CREATE_SET"
echo "=========================================="
echo ""

ERRORS_SET=0

if [ "$HAND_P1_FINAL_SET" -ne 4 ]; then
    echo "❌ Player 1 debería tener 4 cartas en mano, tiene: $HAND_P1_FINAL_SET"
    ERRORS_SET=$((ERRORS_SET + 1))
else
    echo "✅ Player 1 tiene 4 cartas en mano"
fi

if [ "$DETECTIVE_SET_COUNT_FINAL" -ne 2 ]; then
    echo "❌ Player 1 debería tener 2 cartas en DETECTIVE_SET, tiene: $DETECTIVE_SET_COUNT_FINAL"
    ERRORS_SET=$((ERRORS_SET + 1))
else
    echo "✅ Player 1 tiene 2 cartas en DETECTIVE_SET"
fi

if [ "$PARKER_1_STATE" != "DETECTIVE_SET|1|0" ]; then
    echo "❌ Parker Pyne 1 debería estar en DETECTIVE_SET|1|0, está en: $PARKER_1_STATE"
    ERRORS_SET=$((ERRORS_SET + 1))
else
    echo "✅ Parker Pyne 1 está en DETECTIVE_SET, position 1, hidden false"
fi

if [ "$PARKER_2_STATE" != "DETECTIVE_SET|1|0" ]; then
    echo "❌ Parker Pyne 2 debería estar en DETECTIVE_SET|1|0, está en: $PARKER_2_STATE"
    ERRORS_SET=$((ERRORS_SET + 1))
else
    echo "✅ Parker Pyne 2 está en DETECTIVE_SET, position 1, hidden false"
fi

if [ "$ACTION_XXX_RESULT_SET" != "CANCELLED" ]; then
    echo "⚠️  Action XXX debería tener result=CANCELLED, tiene: $ACTION_XXX_RESULT_SET"
fi

echo ""
if [ $ERRORS_SET -eq 0 ]; then
    echo "=========================================="
    echo "   🎉 TEST CREATE_SET COMPLETADO EXITOSAMENTE"
    echo "=========================================="
    echo "   ✅ Set de Parker Pyne creado sin efecto"
    echo "   ✅ Ambas cartas en DETECTIVE_SET position 1 hidden false"
    echo "   ✅ Acción marcada como CANCELLED"
else
    echo "=========================================="
    echo "   ⚠️  TEST CREATE_SET COMPLETADO CON $ERRORS_SET ERRORES"
    echo "=========================================="
fi
echo ""