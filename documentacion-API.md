# API: Cards on the Table - Agatha Christie

> Documento vivo para Sprint 1. Mantener sincronizado con los cambios de backend y front.

## 1. Introducción

- **Propósito**: describir la API REST y los eventos de WebSocket del juego
- **Alcance Sprint 1**: Inicio de sesión y lobby. Crear o unirse a una partida. Jugar con manos y secretos asignados. Acciones permitidas: descartar cartas y reponer del mazo. El juego termina al llegar a la última carta del mazo ("murder escapes").
- **Base URL**: http://localhost:8000
- **WebSocket base**: ws://localhost:8000

## 2. Convenciones

- **Formato**: JSON en requests y responses
- **Códigos HTTP**: usar 2xx para éxito, 4xx para errores de cliente, 5xx para servidor
- **Errores**: objeto Error con campos code, message, details
- **CORS**: orígenes permitidos según ALLOWED_ORIGINS
- **WebSocket**: header HTTP_USER_ID en el handshake; rooms con nombre game_{game_id}

## 3. Esquemas comunes

Esta sección refleja los modelos actuales del backend (SQLAlchemy) y agrega "view models" pensados para las respuestas del API.

### 3.1 Enums

- **CardType**: "EVENT" | "SECRET" | "INSTANT" | "DEVIUOS" | "DETECTIVE" | "END"
- **RoomStatus**: "WAITING" | "INGAME" | "FINISH"
- **CardState**: "DECK" | "SELECT" | "DISCARD" | "SECRET_SET" | "DETECTIVE_SET" | "HAND"

### 3.2 Entidades persistentes (DB)

**Game**
- id: integer
- player_turn_id: integer | null

**Room**
- id: integer
- name: string
- player_qty: integer
- password: string | null
- status: RoomStatus
- id_game: integer

**Player**
- id: integer
- name: string
- avatar_src: string
- birthdate: date (YYYY-MM-DD)
- id_room: integer
- is_host: boolean
- order: integer | null

**Card**
- id: integer
- name: string
- description: string
- type: CardType
- img_src: string (URL o ruta)

**CardsXGame**
- id: integer
- id_game: integer
- id_card: integer
- is_in: CardState
- position: integer
- player_id: integer | null

### 3.3 View Models (API)

**ActionResult**
- discarded: CardSummary[]  // cartas que salieron de la mano del solicitante
- drawn: CardSummary[]      // cartas tomadas del mazo regular tras el descarte

Para desacoplar la forma de persistencia del contrato público, las respuestas del API exponen objetos agregados:

**GameView**
- id: integer
- name: string
- player_qty: integer
- status: "waiting" | "in_game" | "finished"  // mapeo desde Room.status
- host_id: integer

**PlayerView**
- id: integer
- name: string
- avatar: string  // mapea avatar_src
- birthdate: string (YYYY-MM-DD)
- is_host: boolean
- order: integer | null

**CardSummary**
- id: integer
- name: string
- type: CardType
- img: string // mapea a img_src | se utiliza la imagen del canto de carta si no es visible (secretos, mazo)

**DeckView**
- remaining: integer  // cantidad de cartas en DECK

**DiscardView**
- top: CardSummary | null  // última carta visible (máximo position en DISCARD)
- count: integer           // cantidad total en DISCARD

**HandView**
- player_id: integer       // dueño de esta mano
- cards: CardSummary[]     // exactamente 6 cartas en HAND

**SecretsView**
- player_id: integer       // dueño de estos secretos
- cards: CardSummary[]     // exactamente 3 cartas en SECRET_SET visibles para su dueño

**TurnInfo**
- current_player_id: integer | null
- order: integer[]  // ids de jugadores en orden de turnos
- can_act: boolean // indica si jugador actual puede realizar acciones

**Notas:**
- El orden de turnos se define al iniciar la partida (POST /game/{room_id}/start) calculando la distancia de cada birthdate al cumpleaños de Agatha Christie; la persona más cercana va primero y el resto en orden ascendente de distancia. Antes de iniciar, order puede estar vacío o no definido.

**GameStateView**
- game: GameView
- players: PlayerView[]
- deck: DeckView
- discard: DiscardView
- hand?: HandView         // sólo para el jugador solicitante
- secrets?: SecretsView   // sólo para el jugador solicitante
- turn: TurnInfo

**Error**
- code: string  // p.ej. "validation_error", "not_found", "conflict"
- message: string
- details: object | null

### 3.4 Mapeos y decisiones

**Identidad pública de la partida**
- La entidad pública inicial es Room. POST /game crea la Room en estado WAITING con id_game = null. Cuando la partida pasa a INGAME, POST /game/{room_id}/start crea Game y setea Room.id_game = Game.id.

**Status público**
- Mapeo desde RoomStatus: WAITING → waiting, INGAME → in_game, FINISH → finished.

**Mazos y descartes**
- Se derivan de CardsXGame: is_in = DECK / DISCARD y position define el orden.
- top_discard es la carta con mayor position en DISCARD (la última descartada y visible).

**Mano y secretos del jugador**
- Mano: CardsXGame con is_in = HAND y player_id = id del jugador.
- Secretos: CardsXGame con is_in = SECRET_SET y player_id = id del jugador.

**Campos sensibles**
- Solo devolver HandView y SecretsView al propietario. El resto ve counts y top_discard.

**Host**
- El host se identifica por Player.is_host = true. En respuestas agregadas se puede derivar host_id como el id del Player host.

**Enums expuestos por el API**
- Respetan exactamente los enums de la base actual

**Unicidad**
- Room.name es único global. Además, dentro de una partida, (name + avatar_src) es único por jugador.

**Visibilidad futura**
- Se prevé agregar un flag global_visible en CardsXGame para marcar cartas visibles para todos. En este sprint se asume visibilidad por convención (HAND y SECRET_SET solo para su dueño; DISCARD top visible; DECK no visible).

### 3.5 Ejemplos

**PlayerView**
```json
{
    "id": 7,
    "name": "Ana",
    "avatar": "/assets/avatars/detective1.png",
    "birthdate": "2000-05-10",
    "is_host": true,
    "order": 1
}
```


**Presets de avatar**
- Ruta base: /assets/avatars/
- Set permitido: detective1.png … detective8.png
- Ejemplos: /assets/avatars/detective1.png, /assets/avatars/detective8.png

**GameStateView**
```json
{
    "game": {"id": 42, "name": "Mesa 1", "player_qty": 4, "status": "waiting", "host_id": 7},
    "players": [{"id": 7, "name": "Ana", "avatar": "/assets/avatars/detective1.png", "birthdate": "2000-05-10", "is_host": true, "order": 1}],
    "deck": {"remaining": 52, "top_discard": null},
    "turn": {"current_player_id": 7, "order": [7,4,5,9], "can_act": true}
}
```

## 4. Endpoints REST

### 4.1 GET /game_state/{room_id}

**Descripción**: obtener el estado agregado de la partida EN CURSO para una room dada.

**Path params**: 
- room_id: integer

**Comportamiento**
- Si Room.status = "INGAME": devuelve GameStateView
- Si Room.status = "WAITING": 409 "game_not_started"

**Responses**
- 200: GameStateView
- 404: Error (La partida no existe)
- 409: Error { code: "game_not_started", message }

**Ejemplo curl**
```bash
curl -s "http://localhost:8000/game_state/42"
```


**Errores por endpoint**
- 404 not_found: room_id inexistente
- 409 game_not_started: la room está en WAITING
- 500 server_error: error inesperado

**Ejemplo 200**
```json
{
    "game": {"id": 42, "name": "Mesa 1", "player_qty": 4, "status": "in_game", "host_id": 7},
    "players": [{"id": 7, "name": "Ana", "avatar": "/assets/avatars/detective1.png", "birthdate": "2000-05-10", "is_host": true, "order": 1}],
    "deck": {"remaining": 37},
    "discard": {"top": {"id": 101, "name": "Not So Fast", "type": "INSTANT"}, "count": 15},
    "hand": {"player_id": 7, "cards": [{"id": 12, "name": "Cards off the table", "type": "EVENT"}]},
    "secrets": {"player_id": 7, "cards": [{"id": 77, "name": "You're the murderer", "type": "SECRET"}]},
    "turn": {"current_player_id": 7, "order": [7, 9, 13, 20], "can_act": true}
}
```


**Ejemplo 409**

```json
{
    "code": "game_not_started",
    "message": "La partida aún no fue iniciada",
    "details": {"room_id": 42}
}
```


### 4.2 POST /game

**Descripción**: crea una sala (Room) en estado WAITING con nombre único y cantidad de jugadores objetivo. Crea además el Player solicitante como is_host=true en esa Room. id_game permanece null hasta iniciar la partida.

**Body**
```json
{
    "name": "Mesa 1",
    "player_qty": 4,
    "player": {
    "name": "Ana",
    "avatar": "/assets/avatars/detective1.png",
    "birthdate": "2000-05-10"
}
```

**Responses**

**201 Created**
```json
{
    "room": { "id": 42, "name": "Mesa 1", "player_qty": 4, "status": "waiting", "host_id": 7 },
    "players": [
        { "id": 7, "name": "Ana", "avatar": "/assets/avatars/detective1.png", "birthdate": "2000-05-10", "is_host": true }
    ]
}
```

- 400 validation_error
- 409 conflict (name_duplicated)

**Ejemplo curl**
```bash
curl -s -X POST "http://localhost:8000/game" \
    -H "Content-Type: application/json" \
    -d '{
    "name":"Mesa 1",
    "player_qty":4,
    "player":{"name":"Ana","avatar":"/assets/avatars/detective1.png","birthdate":"2000-05-10"}
    }' | jq .
```

**Errores por endpoint**
- 400 validation_error: name vacío o longitud inválida, player_qty fuera de 2–6, player incompleto
- 409 conflict: name_duplicated
- 500 server_error: error inesperado

### 4.3 GET /game_list

**Descripción**: lista salas en estado WAITING con cupos disponibles, ordenadas por id (desc).

**Query params opcionales**
- page: number (default 1)
- limit: number (default 20)

**Responses**

**200 OK**
```json
{
    "items": [
        { "id": 42, "name": "Mesa 1", "player_qty": 4, "players_joined": 1 },
        { "id": 41, "name": "Mesa 0", "player_qty": 2, "players_joined": 1 }
        ],
    "page": 1,
    "limit": 20
}
```

**Ejemplo curl**

```bash
curl -s "http://localhost:8000/game_list?page=1&limit=10"
```

**Errores por endpoint**
- 200 OK (lista vacía si no hay partidas). 
- Usar 500 server_error ante fallas.

### 4.4 POST /game/{room_id}/join

**Descripción**: agrega un jugador a una sala en WAITING con cupo disponible.

**Path params**: 
- room_id: integer

**Body**
```json
{
    "name": "Luis",
    "avatar": "/assets/avatars/detective2.png",
    "birthdate": "1999-03-01"
}
```

**Responses**

**200 OK**
```json
{
    "room": { "id": 42, "name": "Mesa 1", "player_qty": 4, "status": "waiting" },
    "players": [
        { "id": 7, "name": "Ana", "avatar": "/assets/avatars/detective1.png", "birthdate": "2000-05-10", "is_host": true },
        { "id": 9, "name": "Luis", "avatar": "/assets/avatars/detective2.png", "birthdate": "1999-03-01", "is_host": false }
        ]
}
```

- 404 not_found (room)
- 409 conflict (room_full | name_avatar_taken)

**Ejemplo curl**
```bash
curl -s -X POST "http://localhost:8000/game/42/join" \
    -H "Content-Type: application/json" \
    -d '{"name":"Luis","avatar":"/assets/avatars/detective2.png","birthdate":"1999-03-01"}' | jq .
```


**Errores por endpoint**
- 404 not_found: room inexistente
- 409 conflict: room_full | name_avatar_taken
- 500 server_error: error inesperado

### 4.5 POST /game/{room_id}/start

**Descripción**: iniciar la partida. Crea Game asociado y pasa Room a INGAME.

**Notas**: 
- Al iniciar: 
  - Cada jugador recibe 6 cartas de mano y 3 secretos según reglas del juego
  - Deck.remaining = total_inicial − jugadores×(6+3)
  - Discard.count = 0 y Discard.top = null
  - Turn.order definido según regla de cumpleaños y current_player_id = primer jugador
- Visibilidad: 
  - Hand y Secrets se devuelven solo al dueño
  - Otros jugadores ven counters, cartas boca abajo y discard.top
- Eventos WS emitidos: 
  - game_started { game, turn }
  - hand_updated y secrets_updated por jugador
  - deck_updated y discard counters

**Path params**: 
- room_id: integer

**Comportamiento**
- Crea Game, setea Room.id_game = Game.id
- Cambia Room.status = "INGAME"
- Inicializa mazos y manos y secretos según reglas del juego

**Responses**
- 200: estado inicial de partida en curso (GameStateView)
- 403: no es host
- 409: no cumple condiciones de inicio

**Ejemplo 200**
```json
{
    "game": {"id": 101, "name": "Mesa 1", "player_qty": 4, "status": "in_game", "host_id": 7},
    "players": [
        {"id": 7, "name": "Ana", "avatar": "/assets/avatars/detective1.png", "birthdate": "2000-05-10", "is_host": true},
        {"id": 9, "name": "Luis", "avatar": "/assets/avatars/detective2.png", "birthdate": "1999-03-01", "is_host": false},
        {"id": 13, "name": "Mia", "avatar": "/assets/avatars/detective3.png", "birthdate": "1998-08-20", "is_host": false},
        {"id": 20, "name": "Sol", "avatar": "/assets/avatars/detective4.png", "birthdate": "2001-11-02", "is_host": false}
    ],
    "deck": {"remaining": 52},
    "discard": {"top": null, "count": 0},
    "hand": {"player_id": 7, "cards": [{"id": 12, "name": "Cards off the table", "type": "EVENT"}, ...]},
    "secrets": {"player_id": 7, "cards": [{"id": 77, "name": "You're the murderer", "type": "SECRET"}, ...]},
    "turn": {"current_player_id": 7, "order": [7, 9, 13, 20], "can_act": true}
}
```

**Ejemplo curl**

```bash
curl -s -X POST "http://localhost:8000/game/42/start"
```


**Errores por endpoint**
- 403 forbidden: quien invoca no es host
- 409 conflict: no cumple condiciones de inicio (mínimo de jugadores, etc.)
- 404 not_found: room_id inexistente
- 500 server_error: error inesperado

### 4.6 POST /game/{room_id}/discard

**Descripción**: descartar N cartas de la mano y reponer desde el mazo regular, finalizando el turno.

**Path params**: 
- room_id: integer

**Body**
```json
{ "card_ids": [1, 2, 3] }
```

**Responses**

**200 OK**
```json
{
    "action": {
        "discarded": [ {"id": 12, "name": "Cards off the table", "type": "EVENT"} ],
        "drawn": [ {"id": 31, "name": "Another victim", "type": "ACTION"} ]
    },
    "hand": { "player_id": 7, "cards": [ {"id": 44, "name": "...", "type": "..."} ], ... },
    "deck": { "remaining": 36 },
    "discard": { "top": {"id": 12, "name": "Cards off the table", "type": "EVENT"}, "count": 16 }
}
```

- 400 validation_error (cartas inválidas, lista vacía)
- 403 forbidden (no es tu turno)
- 404 not_found (room)
- 409 conflict (reglas de descarte no cumplidas)

**Ejemplo curl**

```bash
curl -s -X POST "http://localhost:8000/game/42/discard" \
-H "Content-Type: application/json" \
-d '{"card_ids":[12,31]}' | jq .
```

### 4.7 POST /game/{room_id}/skip

**Descripción**: finalizar turno descartando exactamente 1 carta según regla definida y reponer desde el mazo regular.

**Path params**: 
- room_id: integer

**Body (opcional)**
```json
{ "rule": "auto" }
```

**Responses**

**200 OK**

```json
{
    "action": {
        "discarded": [ {"id": 55, "name": "...", "type": "..."} ],
        "drawn": [ {"id": 78, "name": "...", "type": "..."} ]
    },
    "hand": { "player_id": 7, "cards": [ {"id": 44, "name": "...", "type": "..."}, ... ] },
    "deck": { "remaining": 35 },
    "discard": { "top": {"id": 55, "name": "...", "type": "..."}, "count": 17 }
}
```

- 400 validation_error (si hubiera body inválido)
- 403 forbidden (no es tu turno)
- 404 not_found (room)
- 409 conflict (no se puede aplicar la regla de descarte obligatorio)

**Ejemplo curl**

```bash
curl -s -X POST "http://localhost:8000/game/42/skip" \
-H "Content-Type: application/json" \
-d '{"rule":"auto"}' | jq .
```

## 5. Eventos WebSocket

Esta sección define el contrato de eventos de WebSocket para el juego. El backend publica eventos al room de cada partida. El cliente escucha y actualiza la UI y el estado global.

### Canal y sesión
- **Canal por partida**: room "game_{room_id}"
- **Handshake**: header HTTP_USER_ID para identificar al usuario
- **Sesión**: cada conexión se asocia a un user_id; el servidor gestiona entrada y salida de rooms

### Nombres de eventos y payloads

**connected**
- Emisor: servidor a cliente recién conectado
- Payload: `{ "message": "Conectado existosamente" }`

**player_connected**
- Emisor: servidor a todos en game_{room_id}
- Payload: `{ "user_id": number, "room_id": number, "timestamp": "ISO-8601" }`

**player_disconnected**
- Emisor: servidor a todos en game_{room_id}
- Payload: `{ "user_id": number, "room_id": number, "timestamp": "ISO-8601" }`

**join_error**
- Emisor: servidor al solicitante
- Payload: `{ "message": string }`

**player_joined**
- Emisor: servidor a todos en game_{room_id}
- Uso: lobby de partida en espera
- Payload: `{ "player": PlayerView, "players_count": number }`

**player_left**
- Emisor: servidor a todos en game_{room_id}
- Uso: lobby en espera
- Payload: `{ "player_id": number, "players_count": number }`

**game_started**
- Emisor: servidor a todos en game_{room_id}
- Uso: transición de WAITING → INGAME
- Payload: `{ "game": GameView, "turn": TurnInfo }`

**game_state**
- Emisor: servidor al solicitante o broadcast cuando corresponde
- Uso: snapshot completo del estado de la partida cuando se requiere resincronizar
- Payload: GameStateView

**hand_updated**
- Emisor: servidor solo al dueño de la mano
- Uso: actualizar mano del jugador tras acciones o inicio
- Payload: `{ "player_id": number, "hand": HandView }`

**secrets_updated**
- Emisor: servidor solo al dueño
- Uso: entregar/actualizar secretos
- Payload: `{ "player_id": number, "secrets": SecretsView }`

**deck_updated**
- Emisor: servidor a todos en game_{room_id}
- Uso: contador de mazo y descarte
- Payload: `{ "remaining": number, "discard_count": number }`

**discard_updated**
- Emisor: servidor a todos en game_{room_id}
- Uso: carta superior del descarte y contador
- Payload: `{ "top": CardSummary | null, "count": number }`

**turn_updated**
- Emisor: servidor a todos en game_{room_id}
- Uso: avanzar turno, habilitar acciones
- Payload: `{ "current_player_id": number, "order": number[] }`

**action_result**
- Emisor: servidor al solicitante y, si aplica, al room con la parte visible
- Uso: feedback inmediato de /discard y /skip
- Payload (al solicitante): `{ "room_id": number, "action": ActionResult, "hand": HandView }`
- Payload (broadcast a terceros): puede omitirse "hand" y devolver solo contadores visibles; normalmente se complementa con deck_updated y discard_updated

**game_finished**
- Emisor: servidor a todos en game_{room_id}
- Uso: fin de partida por agotamiento del mazo y carta final
- Payload: `{ "winners": [{ "role": "murderer" | "accomplice" | "detective", "player_id": number }], "reason": "deck_exhausted_murderer_wins" | "one_player_left" | "other" }`

### Secuencia típica por endpoints

**POST /game/{room_id}/join**
- Emitir: player_joined

**POST /game/{room_id}/start**
- Emitir: game_started, hand_updated (por jugador), secrets_updated (por jugador), deck_updated, discard_updated

**POST /game/{room_id}/discard**
- Emitir al solicitante: action_result con ActionResult + hand
- Emitir a todos: deck_updated, discard_updated, turn_updated

**POST /game/{room_id}/skip**
- Emitir al solicitante: action_result con 1 discarded + 1 drawn + hand
- Emitir a todos: deck_updated, discard_updated, turn_updated

**Fin de partida**
- Emitir: game_finished, y opcionalmente game_state final

### Notas
- Los view models referenciados (PlayerView, GameView, HandView, SecretsView, TurnInfo, GameStateView, ActionResult) están definidos en 3.3.
- La visibilidad de información sensible debe respetarse: hand_updated y secrets_updated se envían solo a su propietario.
- El cliente debe reconectarse automáticamente y pedir resincronización con GET /game_state/{room_id} o esperar un game_state push si el backend lo emite tras reconexión.

## 6. Changelog

- **2025-09-22**: Documentación Inicial de la API, basada en los tickets generados.