# 🤖 MediaBot v2 — Telegram Media Request Bot

Control total de tu stack de media doméstico desde Telegram.
Integra Radarr, Sonarr, qBittorrent, Bazarr y Plex.

---

## Quick Start

### 1. Crear el bot en Telegram
Mensaje a [@BotFather](https://t.me/BotFather):
```
/newbot
```
Copiá el token que te da.

### 2. Obtener tu Telegram user ID
Mensaje a [@userinfobot](https://t.me/userinfobot) — te responde con tu ID numérico.

### 3. Configurar
```bash
cp .env.example .env
nano .env
```

M�nimo necesario:
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_ALLOWED_USERS` (tu ID numérico)
- Todos los `*_API_KEY` (cada servicio → Settings → General)
- `QBIT_PASS`

### 4. Red Docker
Si tu stack arr ya está corriendo, encontrá el nombre de la red:
```bash
docker network ls
docker inspect radarr | grep -i network
```
Actualizá `docker-compose.yml` → `networks.media_network.name` con el nombre correcto.

### 5. Arrancar
```bash
docker compose up -d
docker compose logs -f mediabot
```

---

## Comandos

### Búsqueda y adición
| Comando | Descripción |
|---|---|
| `/movie <título>` | Buscar película → tarjeta de confirmación → añadir a Radarr |
| `/series <título>` | Buscar serie → seleccionar modo de monitor → añadir a Sonarr |
| `/search <título>` | Búsqueda simultánea en Radarr + Sonarr |

### Cola y descargas
| Comando | Descripción |
|---|---|
| `/queue` | Ver cola completa con botones de acción |
| `/queue remove` | Menú para cancelar una descarga específica |
| `/queue retry` | Reintentar todas las descargas fallidas |
| `/history` | Últimas descargas de películas y series |
| `/history movies` | Solo historial de películas |
| `/history series` | Solo historial de series |

### Calidad
| Comando | Descripción |
|---|---|
| `/quality movie <título>` | Cambiar perfil de calidad de una película |
| `/quality series <título>` | Cambiar perfil de calidad de una serie |

### Monitoreo
| Comando | Descripción |
|---|---|
| `/monitor list` | Ver todas las series y su estado |
| `/monitor continue <serie>` | Activar monitoreo |
| `/monitor pause <serie>` | Pausar monitoreo |

### Estado
| Comando | Descripción |
|---|---|
| `/status` | Estado completo: descargas, colas, disco, servicios |
| `/wanted` | Películas y episodios pendientes de descarga |

### Plex
| Comando | Descripción |
|---|---|
| `/plex` | Resumen de tu biblioteca |
| `/plex <título>` | Buscar si algo ya está en Plex |

### Subtítulos
| Comando | Descripción |
|---|---|
| `/subtitles` | Ver subtítulos pendientes en Bazarr |

---

## Modos de monitor para /series

Después de elegir la serie, seleccionás cómo descargar:

| Opción | Comportamiento |
|---|---|
| 🕐 Solo nuevos | Solo episodios futuros (desde ahora) |
| 📦 Todo | Todas las temporadas completas |
| 📺 Última temporada | Solo la temporada más reciente |
| ❌ Sin descargas | Añadir a Sonarr sin descargar nada |

---

## Notificaciones automáticas

El bot te avisa por Telegram cuando:

- ⬇️ Empieza una descarga (con nombre del release)
- ✅ Se completa una descarga
- 🎉 Se importa a Plex
- ⚠️ Hay un problema de salud en Sonarr/Radarr
- 🔴 Un servicio se cae / 🟢 vuelve
- 💾 El disco está por debajo del umbral (con sugerencias de acción)
- ▶️ Alguien reproduce algo en Plex (opcional)

### Configurar webhooks

**Sonarr:** Settings → Connect → + Webhook
```
URL:    http://mediabot:8222/webhook/sonarr
M�todo: POST
Eventos: Grab, Download, Import, Health, Series Add, Series Delete
```

**Radarr:** Settings → Connect → + Webhook
```
URL:    http://mediabot:8222/webhook/radarr
M�todo: POST
Eventos: Grab, Download, Import, Health, Movie Added, Movie Delete
```

**Plex:** Settings → Webhooks
```
URL: http://mediabot:8222/webhook/plex
```

---

## Estructura del proyecto

```
mediabot/
├── bot/
│   ├── main.py               # Entry point (lifecycle PTB correcto)
│   ├── config.py             # Settings via pydantic
│   ├── auth.py               # Whitelist middleware
│   ├── handlers/
│   │   ├── movie.py          # /movie (con tarjeta de confirmación)
│   │   ├── series.py         # /series (con selección de modo)
│   │   ├── status.py         # /status + /wanted
│   │   ├── search.py         # /search
│   │   ├── queue.py          # /queue (ver, cancelar, reintentar)
│   │   ├── history.py        # /history
│   │   ├── quality.py        # /quality
│   │   ├── monitor.py        # /monitor
│   │   ├── subtitles.py      # /subtitles
│   │   ├── plex.py           # /plex
│   │   └── help.py           # /help
│   ├── services/
│   │   ├── base.py
│   │   ├── radarr.py
│   │   ├── sonarr.py
│   │   ├── qbittorrent.py
│   │   ├── bazarr.py
│   │   └── prowlarr.py
│   ├── notifications/
│   │   ├── dispatcher.py     # Rutas eventos → Telegram
│   │   ├── webhook_server.py # Servidor aiohttp
│   │   └── poller.py         # Disco + salud de servicios
│   ├── db/
│   │   └── models.py         # SQLite
│   └── utils/
│       ├── disk.py
│       └── formatters.py
├── .env.example
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```

---

## Seguridad

- Solo `TELEGRAM_ALLOWED_USERS` puede interactuar con el bot
- El volumen de media se monta read-only (`/data:ro`)
- El contenedor corre como usuario no-root
- Los secretos se cargan desde `.env` (nunca hardcodeados)

---

## Troubleshooting

**El bot no responde:**
```bash
docker compose logs mediabot
```

**No puede conectar con Sonarr/Radarr:**
```bash
# Ver redes disponibles
docker network ls
# Ver a qué red está conectado Sonarr
docker inspect sonarr | grep -A5 Networks
```
Actualizá `media_network` en `docker-compose.yml` para que coincida.

**Error de API key:**
Cada servicio: Settings → General → Security → API Key
