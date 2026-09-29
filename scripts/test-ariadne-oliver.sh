#!/bin/bash

source venv/bin/activate

set -e

DB_USER="developer"
DB_PASSWORD="developer_pass"
DB_NAME="cards_table_develop"
BASE_URL="http://localhost:8000/api"

echo ""
echo "=========================================="
echo "   TEST: Ariadne Oliver Complete Flow"
echo "=========================================="
echo ""

echo "📋 PASO 1: Limpiando base de datos..."
mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME <<EOF
SET FOREIGN_KEY_CHECKS = 0;
DROP TABLE IF EXISTS social_disgrace_player;
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
echo "📋 PASO 5: Insertando datos de test Ariadne Oliver..."
mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME < scripts/ariadne-oliver-test-data.sql
echo "✅ Datos de test insertados"

echo ""
echo "📋 PASO 6: Consultando IDs generados..."
GAME_ID=$(mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "SELECT MAX(id) FROM game;")
ROOM_ID=$(mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "SELECT MAX(id) FROM room;")
PLAYER1_ID=$(mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "SELECT id FROM player WHERE name='AO_Player1';")
PLAYER2_ID=$(mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "SELECT id FROM player WHERE name='AO_Player2';")
PLAYER3_ID=$(mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "SELECT id FROM player WHERE name='AO_Player3';")

echo "Game ID: $GAME_ID"
echo "Room ID: $ROOM_ID"
echo "Player 1 (AO_Player1): $PLAYER1_ID - Order: 1 - TURNO ACTUAL, JUEGA ARIADNE OLIVER"
echo "Player 2 (AO_Player2): $PLAYER2_ID - Order: 2 - TIENE SET DE DETECTIVE (Parker Pyne)"
echo "Player 3 (AO_Player3): $PLAYER3_ID - Order: 3"

# Obtener carta Ariadne Oliver del Player 1
ARIADNE_CARD=$(mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT id FROM cardsXgame 
    WHERE id_game=$GAME_ID 
      AND player_id=$PLAYER1_ID 
      AND id_card=5 
      AND is_in='HAND' 
    LIMIT 1;
")

# Obtener primer secreto de Player 2 (para revelación)
PLAYER2_SECRET=$(mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT id FROM cardsXgame 
    WHERE id_game=$GAME_ID 
      AND player_id=$PLAYER2_ID 
      AND is_in='SECRET_SET' 
    ORDER BY position ASC
    LIMIT 1;
")

# Obtener el id_card del secreto para mostrarlo
SECRET_CARD_ID=$(mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT id_card FROM cardsXgame WHERE id=$PLAYER2_SECRET;
")

echo ""
echo "Carta 'Ariadne Oliver' (cardsXgame.id): $ARIADNE_CARD (player_id: $PLAYER1_ID)"
echo "Secreto a revelar (cardsXgame.id): $PLAYER2_SECRET (card_id: $SECRET_CARD_ID, player_id: $PLAYER2_ID)"

echo ""
echo "=========================================="
echo "   ESTADO INICIAL"
echo "=========================================="
echo ""

echo "🔍 MANO PLAYER 1 (6 cartas: Ariadne Oliver + 5 más):"
mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT CONCAT('  [Pos ', position, '] CardsXGame.id: ', id, ' | Card.id: ', id_card, ' (5=Ariadne Oliver)') 
    FROM cardsXgame 
    WHERE id_game=$GAME_ID 
      AND player_id=$PLAYER1_ID 
      AND is_in='HAND'
    ORDER BY position;
"

echo ""
echo "🔍 DETECTIVE SET PLAYER 2 (position 1 - Parker Pyne):"
mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT CONCAT('  CardsXGame.id: ', id, ' | Card.id: ', id_card, ' | Hidden: ', hidden, ' (7=Parker Pyne)') 
    FROM cardsXgame 
    WHERE id_game=$GAME_ID 
      AND player_id=$PLAYER2_ID 
      AND is_in='DETECTIVE_SET'
      AND position=1
    ORDER BY id;
"

echo ""
echo "🔍 SECRETOS PLAYER 2 (3 secretos, todos ocultos):"
mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT CONCAT('  [Pos ', position, '] CardsXGame.id: ', id, ' | Card.id: ', id_card, ' | Hidden: ', hidden, ' (2=Murderer)') 
    FROM cardsXgame 
    WHERE id_game=$GAME_ID 
      AND player_id=$PLAYER2_ID 
      AND is_in='SECRET_SET'
    ORDER BY position;
"

echo ""
echo "=========================================="
echo "   🎮 TEST 1: Player 1 agrega Ariadne Oliver al set de Player 2"
echo "=========================================="
echo ""
echo "📝 Explicación:"
echo "   - Player 1 (order=1) juega Ariadne Oliver"
echo "   - Objetivo: Set de Player 2 en position 1 (Parker Pyne)"
echo "   - Efecto: Player 2 deberá revelar uno de sus secretos"
echo ""

REQUEST_ADD_OLIVER="{
  \"player_id\": $PLAYER1_ID,
  \"oliver_card_id\": $ARIADNE_CARD,
  \"target_player_id\": $PLAYER2_ID,
  \"target_set_position\": 1
}"
echo "📤 Request POST /api/game/$ROOM_ID/detective/add-oliver-to-set:"
echo "$REQUEST_ADD_OLIVER" | jq '.'

RESPONSE_ADD_OLIVER=$(curl -s -X POST "$BASE_URL/game/$ROOM_ID/detective/add-oliver-to-set" \
  -H "Content-Type: application/json" \
  -d "$REQUEST_ADD_OLIVER")

echo ""
echo "📥 Response:"
echo "$RESPONSE_ADD_OLIVER" | jq '.'

ACTION_ID=$(echo "$RESPONSE_ADD_OLIVER" | jq -r '.action_id')
STATUS_ADD=$(echo "$RESPONSE_ADD_OLIVER" | jq -r '.status')
NEXT_ACTION=$(echo "$RESPONSE_ADD_OLIVER" | jq -r '.next_action')

if [ "$STATUS_ADD" != "success" ]; then
    echo "❌ ERROR: Player 1 no pudo agregar Ariadne Oliver al set"
    echo "$RESPONSE_ADD_OLIVER" | jq '.'
    exit 1
fi

if [ "$ACTION_ID" == "null" ] || [ -z "$ACTION_ID" ]; then
    echo "❌ ERROR: No se obtuvo action_id"
    exit 1
fi

echo ""
echo "✅ Ariadne Oliver agregada correctamente al set"
echo "   Action ID: $ACTION_ID"
echo "   Next Action: $NEXT_ACTION (debería ser WAIT_TARGET_REVEAL)"

echo ""
echo "🔍 MANO PLAYER 1 DESPUÉS (debería tener 5 cartas):"
HAND_P1_AFTER=$(mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT COUNT(*) FROM cardsXgame 
    WHERE id_game=$GAME_ID 
      AND player_id=$PLAYER1_ID 
      AND is_in='HAND';
")
echo "   Total: $HAND_P1_AFTER cartas"
mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT CONCAT('  [Pos ', position, '] CardsXGame.id: ', id, ' | Card.id: ', id_card) 
    FROM cardsXgame 
    WHERE id_game=$GAME_ID 
      AND player_id=$PLAYER1_ID 
      AND is_in='HAND'
    ORDER BY position;
"

echo ""
echo "🔍 DETECTIVE SET PLAYER 2 DESPUÉS (debería tener 3 cartas ahora: 2 Parker Pyne + Ariadne):"
SET_P2_AFTER=$(mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT COUNT(*) FROM cardsXgame 
    WHERE id_game=$GAME_ID 
      AND player_id=$PLAYER2_ID 
      AND is_in='DETECTIVE_SET'
      AND position=1;
")
echo "   Total: $SET_P2_AFTER cartas en position 1"
mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT CONCAT('  CardsXGame.id: ', id, ' | Card.id: ', id_card, ' | Hidden: ', hidden, ' (5=Ariadne, 7=Pyne)') 
    FROM cardsXgame 
    WHERE id_game=$GAME_ID 
      AND player_id=$PLAYER2_ID 
      AND is_in='DETECTIVE_SET'
      AND position=1
    ORDER BY id;
"

echo ""
echo "🔍 ACCIÓN CREADA (ADD_DETECTIVE, PENDING):"
mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT CONCAT(
        '  ID: ', id, 
        ' | Type: ', action_type, 
        ' | Name: ', action_name, 
        ' | Result: ', result,
        ' | Player: ', player_id,
        ' | Target: ', player_target,
        ' | Set Position: ', selected_set_id
    ) 
    FROM actions_per_turn 
    WHERE id=$ACTION_ID;
"

echo ""
echo "⏳ Esperando 2 segundos antes de revelar secreto..."
sleep 2

echo ""
echo "=========================================="
echo "   🎮 TEST 2: Player 2 revela un secreto"
echo "=========================================="
echo ""
echo "📝 Explicación:"
echo "   - Player 2 (target) debe revelar uno de sus secretos"
echo "   - Vamos a revelar el primer secreto (position 1)"
if [ "$SECRET_CARD_ID" == "2" ]; then
    echo "   - ⚠️  Es el ASESINO (id_card=2) - el juego debería terminar"
else
    echo "   - Es un secreto normal (id_card=$SECRET_CARD_ID) - el juego debería continuar"
fi
echo ""

echo "Secreto a revelar (cardsXgame.id): $PLAYER2_SECRET (card_id=$SECRET_CARD_ID)"

REQUEST_REVEAL="{
  \"action_id\": $ACTION_ID,
  \"secret_id\": $PLAYER2_SECRET,
  \"player_id\": $PLAYER2_ID
}"
echo ""
echo "📤 Request POST /api/game/$ROOM_ID/detective/oliver-reveal-secret:"
echo "$REQUEST_REVEAL" | jq '.'

RESPONSE_REVEAL=$(curl -s -X POST "$BASE_URL/game/$ROOM_ID/detective/oliver-reveal-secret" \
  -H "Content-Type: application/json" \
  -d "$REQUEST_REVEAL")

echo ""
echo "📥 Response:"
echo "$RESPONSE_REVEAL" | jq '.'

STATUS_REVEAL=$(echo "$RESPONSE_REVEAL" | jq -r '.status')
MESSAGE_REVEAL=$(echo "$RESPONSE_REVEAL" | jq -r '.message')

if [ "$STATUS_REVEAL" != "success" ]; then
    echo "❌ ERROR: Player 2 no pudo revelar el secreto"
    echo "$RESPONSE_REVEAL" | jq '.'
    exit 1
fi

echo ""
echo "✅ Secreto revelado correctamente"
echo "   Mensaje: $MESSAGE_REVEAL"

echo ""
echo "🔍 SECRETO REVELADO (hidden debería ser FALSE ahora):"
mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT CONCAT('  CardsXGame.id: ', id, ' | Card.id: ', id_card, ' | Hidden: ', hidden, ' (debería ser 0/FALSE)') 
    FROM cardsXgame 
    WHERE id=$PLAYER2_SECRET;
"

echo ""
echo "🔍 ACCIÓN PADRE (debería ser SUCCESS ahora):"
mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT CONCAT(
        '  ID: ', id, 
        ' | Type: ', action_type, 
        ' | Name: ', action_name, 
        ' | Result: ', result,
        ' (debería ser SUCCESS)'
    ) 
    FROM actions_per_turn 
    WHERE id=$ACTION_ID;
"

echo ""
echo "🔍 ACCIÓN HIJA (REVEAL_SECRET, SUCCESS):"
mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT CONCAT(
        '  ID: ', id, 
        ' | Type: ', action_type, 
        ' | Name: ', action_name, 
        ' | Result: ', result,
        ' | Player: ', player_id,
        ' | Secret Target: ', secret_target,
        ' | Parent Action: ', parent_action_id
    ) 
    FROM actions_per_turn 
    WHERE parent_action_id=$ACTION_ID;
"

echo ""
echo "🔍 TODAS LAS ACCIONES CREADAS:"
mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT CONCAT(
        '  ID: ', id, 
        ' | Type: ', action_type, 
        ' | Name: ', action_name, 
        ' | Result: ', result,
        ' | Player: ', player_id,
        ' | Parent: ', IFNULL(parent_action_id, 'NULL')
    ) 
    FROM actions_per_turn 
    WHERE id_game=$GAME_ID
    ORDER BY id;
"

echo ""
echo "⏳ Esperando 2 segundos para verificar fin de juego..."
sleep 2

echo ""
echo "=========================================="
echo "   📊 VERIFICACIÓN FINAL"
echo "=========================================="
echo ""

echo "🔍 ESTADO DEL ROOM (debería ser FINISH si el juego terminó):"
ROOM_STATUS=$(mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT status FROM room WHERE id=$ROOM_ID;
")
echo "   Room Status: $ROOM_STATUS"

echo ""
echo "🔍 SECRETOS PLAYER 2 (verificar cuál está revelado):"
mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT CONCAT('  [Pos ', position, '] CardsXGame.id: ', id, ' | Card.id: ', id_card, ' | Hidden: ', hidden, ' (2=Murderer)') 
    FROM cardsXgame 
    WHERE id_game=$GAME_ID 
      AND player_id=$PLAYER2_ID 
      AND is_in='SECRET_SET'
    ORDER BY position;
"

echo ""
echo "=========================================="
echo "   ✅ RESUMEN DE VALIDACIONES"
echo "=========================================="
echo ""

ERRORS=0

if [ "$HAND_P1_AFTER" -ne 5 ]; then
    echo "❌ Player 1 debería tener 5 cartas (jugó Ariadne Oliver), tiene: $HAND_P1_AFTER"
    ERRORS=$((ERRORS + 1))
else
    echo "✅ Player 1 tiene 5 cartas (jugó Ariadne Oliver)"
fi

if [ "$SET_P2_AFTER" -ne 3 ]; then
    echo "❌ Set de Player 2 debería tener 3 cartas (2 Pyne + Ariadne), tiene: $SET_P2_AFTER"
    ERRORS=$((ERRORS + 1))
else
    echo "✅ Set de Player 2 tiene 3 cartas (2 Pyne + Ariadne)"
fi

SECRET_HIDDEN=$(mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT hidden FROM cardsXgame WHERE id=$PLAYER2_SECRET;
")

if [ "$SECRET_HIDDEN" != "0" ]; then
    echo "❌ Secreto debería estar revelado (hidden=0), tiene: $SECRET_HIDDEN"
    ERRORS=$((ERRORS + 1))
else
    echo "✅ Secreto está revelado (hidden=0)"
fi

PARENT_RESULT=$(mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT result FROM actions_per_turn WHERE id=$ACTION_ID;
")

if [ "$PARENT_RESULT" != "SUCCESS" ]; then
    echo "❌ Acción padre debería ser SUCCESS, tiene: $PARENT_RESULT"
    ERRORS=$((ERRORS + 1))
else
    echo "✅ Acción padre es SUCCESS"
fi

CHILD_COUNT=$(mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -se "
    SELECT COUNT(*) FROM actions_per_turn WHERE parent_action_id=$ACTION_ID;
")

if [ "$CHILD_COUNT" -ne 1 ]; then
    echo "❌ Debería haber 1 acción hija (REVEAL_SECRET), hay: $CHILD_COUNT"
    ERRORS=$((ERRORS + 1))
else
    echo "✅ Hay 1 acción hija (REVEAL_SECRET)"
fi

if [ "$ROOM_STATUS" != "FINISH" ]; then
    if [ "$SECRET_CARD_ID" == "2" ]; then
        echo "❌ ERROR: Se reveló el asesino pero el juego NO terminó (room status: $ROOM_STATUS)"
        ERRORS=$((ERRORS + 1))
    else
        echo "✅ El juego NO terminó (secreto normal revelado, room status: $ROOM_STATUS)"
    fi
else
    if [ "$SECRET_CARD_ID" == "2" ]; then
        echo "✅ El juego terminó correctamente (asesino revelado, FINISH)"
    else
        echo "⚠️  WARNING: El juego terminó pero NO se reveló el asesino (room status: $ROOM_STATUS)"
    fi
fi

echo ""
if [ $ERRORS -eq 0 ]; then
    echo "=========================================="
    echo "   🎉 TEST COMPLETADO EXITOSAMENTE"
    echo "=========================================="
    echo "   ✅ Ariadne Oliver agregada al set de Player 2"
    echo "   ✅ Player 2 reveló un secreto"
    echo "   ✅ Carta movida de HAND a DETECTIVE_SET"
    echo "   ✅ Secreto revelado correctamente (hidden=0)"
    echo "   ✅ Acciones creadas correctamente (1 parent + 1 child)"
    if [ "$ROOM_STATUS" == "FINISH" ]; then
        if [ "$SECRET_CARD_ID" == "2" ]; then
            echo "   ✅ Juego terminó por revelar asesino"
        else
            echo "   ⚠️  Juego terminó (pero secreto no era asesino)"
        fi
    else
        if [ "$SECRET_CARD_ID" != "2" ]; then
            echo "   ✅ Juego continúa (secreto normal revelado)"
        fi
    fi
else
    echo "=========================================="
    echo "   ⚠️  TEST COMPLETADO CON $ERRORS ERRORES"
    echo "=========================================="
fi
echo ""
