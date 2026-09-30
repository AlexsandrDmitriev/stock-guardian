# Stock Guardian

Готовый портфельный проект на Python: асинхронный сервис «Stock Guardian».
Отслеживает цены акций в реальном времени, рассылает push-уведомления при достижении триггеров
и предоставляет REST + WebSocket API для фронтенда.

## Оглавление

- [Архитектура](#архитектура)
- [Стек](#технологический-стек)
- [Структура проекта](#структура-проекта)
- [Модель сигнала](#модель-сигнала)
- [API](#api)
- [WebSocket](#websocket)
- [Фронтенд](#фронтенд)
- [Локальная разработка](#локальная-разработка)
- [Деплой на Render](#деплой-на-render)
- [Тестирование](#тестирование)
- [CI/CD](#cicd)
- [Расширения](#идеи-для-расширения)

## Архитектура

```
┌──────────┐      WebSocket    ┌────────┐
│  Client  │◀──────────────────│ FastAPI│
└──────────┘                  └────┬───┘
          REST /alerts             │
                                    ▼
                       ┌────────────────────┐
                       │ Redis (Pub/Sub)    │
                       └──────┬─────────────┘
                              ▼
                    ┌────────────────────┐
                    │ worker (Celery)    │
                    │  ▸ fetch quotes    │
                    │  ▸ evaluate rules  │
                    └──────┬─────────────┘
                           ▼
                    ┌──────────────┐
                    │ PostgreSQL   │
                    └──────────────┘
```

**Data flow:**

1. **Client** (браузер) подключается к WebSocket `/ws/{user_id}` и подписывается на Redis Pub/Sub канал `user_id`
2. **Client** создаёт сигнал через `POST /alerts` → сигнал сохраняется в Redis Hash
3. **Celery worker** (запускается Beat-ом каждые 30с или cron в Render) вызывает `check_alerts()`:
   - Загружает активные сигналы из Redis
   - Получает котировки (stub: `fetch_batch_prices`)
   - Для каждого сигнала проверяет: `price >= target_price` (above) или `price <= target_price` (below)
4. При срабатывании: worker публикует JSON в Redis Pub/Sub канал `user_id`, сигнал деактивируется
5. **FastAPI** получает сообщение из Pub/Sub и отправляет его клиенту через WebSocket в реальном времени

## Технологический стек

| Компонент       | Причина выбора                                      |
|-----------------|-----------------------------------------------------|
| FastAPI         | Высокопроизводительный ASGI-фреймворк               |
| WebSockets      | Мгновенные пуши без long-polling                    |
| PostgreSQL      | Надёжное хранилище сигналов и пользователей           |
| Redis           | Хранилище сигналов (Hash) + Pub/Sub для уведомлений |
| Celery          | Фоновая задача проверки срабатывания сигналов       |
| Redis (Key Val) | Брокер сообщений для Celery (broke + result backend)|
| Docker Compose  | Единое окружение для dev/prod                       |
| GitHub Actions  | Автоматическое тестирование и линтинг               |
| Pydantic/Mypy   | Статическая валидация схем и типов                  |

## Структура проекта

```
stock_guardian/
 ├── app/
 │   ├── api/
 │   │   ├── alerts.py     # REST endpoints: POST/GET/DELETE /alerts
 │   │   └── ws.py         # WebSocket /ws/{user_id}
 │   ├── core/
 │   │   ├── config.py     # Pydantic Settings (env vars)
 │   │   └── models.py     # Pydantic Alert model
 │   ├── services/
 │   │   └── alert_service.py  # Бизнес-логика (Redis storage)
 │   ├── workers/
 │   │   └── quotes.py     # Celery задача check_alerts + Beat schedule
 │   ├── static/           # Frontend assets
 │   │   ├── index.html
 │   │   ├── styles.css
 │   │   └── app.js
 │   └── main.py           # FastAPI app entry point
 ├── tests/
 │   ├── conftest.py       # Pytest fixtures (mock Redis)
 │   └── test_api.py       # Integration tests
 ├── scripts/
 │   └── e2e_test.py       # End-to-end WebSocket test
 ├── .github/workflows/
 │   └── ci.yml            # GitHub Actions CI
 ├── Dockerfile
 ├── docker-compose.yml
 ├── render.yaml           # Render IaC blueprint
 ├── pyproject.toml
 ├── requirements.txt
 └── README.md
```

## Модель сигнала

```python
# app/core/models.py
from pydantic import BaseModel, Field
from uuid import UUID, uuid4

class Alert(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    symbol: str          # Тикер: "NVDA", "AAPL"
    target_price: float  # Целевая цена
    direction: str       # "above" | "below"
    user_id: UUID        # ID пользователя (WebSocket канал)
```

## API

### POST /alerts

Создать сигнал alerts

**Body:**
```json
{
  "symbol": "NVDA",
  "target_price": 1000,
  "direction": "above",
  "user_id": "12345678-1234-5678-1234-567812345678"
}
```

**Response 201:**
```json
{
  "id": "958c0b0f-ba51-4d9a-8128-3f416bd4867d",
  "symbol": "NVDA",
  "target_price": 1000,
  "direction": "above",
  "user_id": "12345678-1234-5678-1234-567812345678"
}
```

### GET /alerts

Получить все активные сигналы

**Response 200:**
```json
[
  {"id": "...", "symbol": "NVDA", "target_price": 1000, "direction": "above", "user_id": "..."}
]
```

### DELETE /alerts/{alert_id}

Деактивировать сигнал

**Response 204**

### GET /health

Проверка состояния

**Response 200:**
```json
{"status": "ok"}
```

## WebSocket

### ws://host/ws/{user_id}

Подписывается на Redis Pub/Sub канал `user_id` и отправляет сообщения клиенту в реальном времени.

**Формат уведомления:**
```json
{"symbol": "NVDA", "price": 1000.0}
```

## Фронтенд

Статичный SPA на vanilla JS, раздаётся FastAPI на корневом пути `/`.

**Функции:**
- Список активных сигналов (GET /alerts)
- Создание сигнала через форму (POST /alerts)
- Удаление сигнала (DELETE /alerts/{id})
- Подписка на WebSocket для Live Notifications
- Индикатор статуса WebSocket соединения

## Локальная разработка

### Требования
- Docker Desktop
- Python 3.12+ (для запуска тестов локально)

### Запуск

```bash
git clone <repo-url>
cd stock-guardian

docker compose up -d --build
```

### Доступные эндпоинты

| URL                          | Описание                  |
|------------------------------|---------------------------|
| http://localhost:8080/        | Фронтенд SPA              |
| http://localhost:8080/docs    | Swagger UI                |
| http://localhost:8080/alerts  | REST API сигналов         |
| http://localhost:8080/ws/…    | WebSocket для уведомлений |
| http://localhost:8080/health  | Health check              |

### Демонстрация работы

1. Откройте http://localhost:8080 в браузере
2. Создайте сигнал: symbol=`NVDA`, target_price=`1000`, direction=`above`,
   user_id=`12345678-1234-5678-1234-567812345678`
3. Через 30 секунд worker проверит цены и, при срабатывании,
   уведомление `NVDA hit 1000` появится в секции "Live Notifications"
   в реальном времени через WebSocket

## Деплой на Render

### Автоматический деплой (Blueprint)

1. Закоммитьте `render.yaml` в корень репозитория
2. Откройте [Render Dashboard](https://dashboard.render.com) → **New > Blueprint**
3. Подключите ваш Git репозиторий (GitHub/GitLab/Bitbucket)
4. Review автоопределяемых ресурсов и нажмите **Deploy Blueprint**

Blueprint создаст:

| Сервис            | Тип       | Описание                          |
|-------------------|-----------|-----------------------------------|
| stock-guardian-api | web       | FastAPI API + фронтенд            |
| stock-guardian-worker | worker  | Celery worker для обработки сигналов |
| stock-guardian-cron | cron      | Periodic task (каждую минуту)     |
| stock-guardian-redis | keyvalue | Redis для Pub/Sub и Celery broker|
| stock-guardian-db | database  | PostgreSQL                        |

5. После деплоя:
   - Фронтенд доступен по публичному URL вашего web сервиса
   - API документация: `https://<your-service>.onrender.com/docs`
   - Health check: `https://<your-service>.onrender.com/health`

### Ручной деплой (альтернатива)

Если не хотите использовать Blueprint:

1. Создайте **Web Service** с:
   - Runtime: Docker
   - Build Command: `docker build -t stock-guardian .`
   - Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
2. Создайте **Background Worker** с тем же образом и командой:
   - `celery -A app.workers.quotes worker --loglevel=info`
3. Создайте **Redis Key Value** и **Postgres Database** в Render
4. Добавьте переменные окружения:
   - `DATABASE_URL` → из Postgres
   - `REDIS_URL` → из Redis Key Value
   - `BROKER_URL` → из Redis Key Value
   - `RESULT_BACKEND` → из Redis Key Value

### Environment Variables

| Переменная       | Описание                          | Пример                              |
|------------------|-----------------------------------|-------------------------------------|
| `DATABASE_URL`   | PostgreSQL connection string      | `postgresql://user:pass@host:5432/db`|
| `REDIS_URL`      | Redis for Pub/Sub                 | `redis://:pass@host:6379`           |
| `BROKER_URL`     | Celery broker URL                 | `redis://:pass@host:6379`           |
| `RESULT_BACKEND` | Celery result backend             | `redis://:pass@host:6379`           |
| `PORT`           | Порт для uvicorn (авто от Render) | `8000`                              |

## Тестирование

```bash
pip install -e ".[dev]"
pytest -q
```

Тесты используют mock Redis (через `unittest.mock.AsyncMock`), так что не требуют реального Redis или БД.

### End-to-End тест

```bash
pip install websockets
python scripts/e2e_test.py
```

Создаёт сигнал, запускает Celery задачу, подключается к WebSocket и проверяет уведомление в реальном времени.

## CI/CD

GitHub Actions workflow (`.github/workflows/ci.yml`):
- Запускается на push/PR в ветку `main`
- Поднимает PostgreSQL и Redis как services
- Устанавливает Python 3.12 и зависимости
- Выполняет: `ruff check`, `mypy`, `pytest -q`

## Идеи для расширения

- OAuth 2.0 + JWT для аутентификации
- gRPC Gateway для мобильных клиентов
- Prometheus + Grafana: метрики задержки и нагрузки воркеров
- Автоскейлинг worker-ов через Kubernetes HPA
- ML-модуль прогнозирования (Prophet/NeuralProphet) для «умных» сигналов
- Интеграция с реальным брокером API (Alpha Vantage, IEX, Yahoo Finance)

## Презентация проекта

1. Live-демо на Fly.io или Render с публичным URL
2. Снимок экрана WebSocket-уведомления в README
3. Итоговый отчёт Lighthouse и диаграмма архитектуры