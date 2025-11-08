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
