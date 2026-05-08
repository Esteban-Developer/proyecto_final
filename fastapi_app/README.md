# FastAPI migration (Inferno Colombia)

Este directorio contiene la migración del ecommerce PHP a **Python + FastAPI**, reutilizando assets (`/css`, `/js`, `/img`, `/fonts`) y MySQL `threaderz_store`.

Incluye checkout asíncrono con:
- **RabbitMQ** para encolar eventos de pedido
- **Redis** para estado temporal (`PENDING`, `CONFIRMED`, `FAILED`)
- **Worker** para procesamiento en background
- **Observabilidad básica** con logs por servicio y `request_id`

## 🚀 Manual de Ejecución (¡100% Dockerizado!)

> **¡IMPORTANTE!** Ya no necesitas instalar Python ni usar XAMPP. Todo el sistema corre dentro de contenedores (API, Worker, Redis, RabbitMQ y MySQL).

### Opción 1: Usuarios de Windows (PowerShell / CMD)

Si no tienes `make` instalado, abre tu terminal en la carpeta principal del proyecto (la raíz, fuera de `fastapi_app`) y ejecuta:

```powershell
docker compose -f fastapi_app/docker-compose.yml up -d --build
```

Para ver los logs en vivo (ideal para ver el proceso de compra):
```powershell
docker compose -f fastapi_app/docker-compose.yml logs -f
```

Para apagar el sistema:
```powershell
docker compose -f fastapi_app/docker-compose.yml down
```

### Opción 2: Usuarios con `make` (Linux / Mac / Windows con Make)

Desde la carpeta principal del proyecto (la raíz):

```bash
make start     # Levanta todos los servicios
make logs      # Muestra los logs en vivo
make stop      # Detiene el sistema
```

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
