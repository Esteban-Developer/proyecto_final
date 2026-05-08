# FastAPI migration (Inferno Colombia)

Este directorio contiene la migración del ecommerce PHP a **Python + FastAPI**, reutilizando assets (`/css`, `/js`, `/img`, `/fonts`) y MySQL `threaderz_store`.

Incluye checkout asíncrono con:
- **RabbitMQ** para encolar eventos de pedido
- **Redis** para estado temporal (`PENDING`, `CONFIRMED`, `FAILED`)
- **Worker** para procesamiento en background
- **Observabilidad básica** con logs por servicio y `request_id`

## Requisitos

- Python 3.10+
- MySQL (XAMPP)
- Docker Desktop
- Base de datos importada desde `store.sql`

## Configuración

1. Copia `.env.example` a `.env`.
2. Ajusta credenciales de MySQL.
3. Si quieres demo visible de estado `PENDING`, usa `ORDER_PROCESSING_DELAY_SECONDS=40`.

## Instalación local

```bash
cd fastapi_app
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
```

## Levantar infraestructura (Redis + RabbitMQ)

```bash
cd fastapi_app
docker compose up -d
```

- RabbitMQ Management: http://localhost:15672
- Usuario/clave: `guest` / `guest`

## Ejecutar API y Worker (modo local)

Terminal A:

```bash
cd fastapi_app
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Terminal B:

```bash
cd fastapi_app
python -m app.worker
```

## Ejecutar todo con Docker Compose

```bash
cd fastapi_app
docker compose up --build
```

Servicios incluidos:
- `api`
- `worker`
- `redis`
- `rabbitmq`

## Flujo de checkout asíncrono

1. Usuario confirma pedido en `/checkout?place=1`.
2. API genera/propaga `request_id`.
3. API envía evento a RabbitMQ (`orders.create`).
4. API marca estado `PENDING` en Redis.
5. Worker consume evento, crea orden en MySQL y limpia carrito.
6. Worker actualiza estado a `CONFIRMED` o `FAILED`.
7. Cliente consulta `GET /checkout/status/{request_id}`.

## Observabilidad implementada

- Logs por servicio:
  - `[API][request_id] ...`
  - `[WORKER][request_id] ...`
- `request_id` viaja entre API -> RabbitMQ -> Worker -> Redis
- Header de respuesta: `x-request-id`

## Endpoints clave

- `GET /checkout/status/{request_id}`
- `POST /productos`
- `GET /productos`
- `GET /productos/{id}`

## Notas

- Autenticación por cookie de sesión (`customer_email`).
- Contraseñas siguen como en el proyecto original (texto plano en DB).
- Si RabbitMQ o Redis caen, checkout asíncrono reporta error controlado en API.
