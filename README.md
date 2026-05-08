# Inferno Colombia — E-commerce Distribuido (Corte 3)

<p align="center">
  <img src="https://capsule-render.vercel.app/api?type=waving&height=220&color=0:0f172a,50:1e293b,100:334155&text=Inferno%20Colombia%20Corte%203&fontColor=ffffff&fontSize=42&animation=fadeIn&fontAlignY=38&desc=FastAPI%20%2B%20Redis%20%2B%20RabbitMQ%20%2B%20MySQL&descAlignY=58" alt="Inferno Colombia Banner" />
</p>

<p align="center">
  <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white" />
  <img alt="Python" src="https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white" />
  <img alt="MySQL" src="https://img.shields.io/badge/MySQL-4479A1?style=for-the-badge&logo=mysql&logoColor=white" />
  <img alt="Redis" src="https://img.shields.io/badge/Redis-DC382D?style=for-the-badge&logo=redis&logoColor=white" />
  <img alt="RabbitMQ" src="https://img.shields.io/badge/RabbitMQ-FF6600?style=for-the-badge&logo=rabbitmq&logoColor=white" />
  <img alt="Docker" src="https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white" />
</p>

<p align="center">
  <img src="https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExNmQ4bHhqaDd4N3NtbW0xMzN2cnNoOW5mbjM4N2F4ZWI5MHEzc2xkNyZlcD12MV9naWZzX3NlYXJjaCZjdD1n/l0HlNaQ6gWfllcjDO/giphy.gif" width="680" alt="Ecommerce Tech Gif" />
</p>

<p align="center">
  <b>Migración de e-commerce PHP a una arquitectura distribuida real con FastAPI</b>
</p>

<p align="center">
  <a href="#-instalacion-y-ejecucion"><img src="https://img.shields.io/badge/Run%20Locally-111827?style=for-the-badge&logo=rocket&logoColor=white" /></a>
  <a href="http://127.0.0.1:8000/docs"><img src="https://img.shields.io/badge/API%20Docs-0ea5e9?style=for-the-badge&logo=swagger&logoColor=white" /></a>
  <a href="http://localhost:15672"><img src="https://img.shields.io/badge/RabbitMQ%20Panel-f97316?style=for-the-badge&logo=rabbitmq&logoColor=white" /></a>
</p>

---

## ¿Qué incluye este corte?

- Front web e-commerce (Jinja2 + assets del proyecto original)
- API REST de catálogo (`/productos`)
- Checkout asíncrono real
- RabbitMQ para mensajería/cola de pedidos
- Redis como coordinador de estado de pedidos
- Worker en Python para procesamiento en segundo plano
- Observabilidad (logs por servicio + `request_id`)
- `Makefile` para demo final (`make start`)
- Pipeline CI con GitHub Actions

---

### Modelo de comunicación

1. Cliente confirma compra en FastAPI.
2. FastAPI encola evento en RabbitMQ (`orders.create`).
3. FastAPI marca estado `PENDING` en Redis.
4. Worker consume la cola y crea orden en MySQL.
5. Worker actualiza Redis a `CONFIRMED` o `FAILED`.
6. Cliente consulta `/checkout/status/{request_id}` hasta estado final.

---

## Componentes del sistema

| Componente | Rol |
|---|---|
| `fastapi_app/app/main.py` | API principal, rutas web, checkout y estado |
| `fastapi_app/app/api_products.py` | Endpoints REST de catálogo |
| `fastapi_app/app/queue.py` | Publicar/consumir mensajes en RabbitMQ |
| `fastapi_app/app/worker.py` | Procesamiento asíncrono de pedidos |
| `fastapi_app/app/order_status.py` | Lectura/escritura del estado en Redis |
| `fastapi_app/docker-compose.yml` | Levanta API, Worker, Redis y RabbitMQ |
| `Makefile` | Comandos de operación (`start`, `stop`, `logs`, etc.) |
| `.github/workflows/ci.yml` | Build y validación automática en cada push/PR |

---

##  Flujo de checkout asíncrono

```text
/checkout?place=1
   ↓
FastAPI publica mensaje a RabbitMQ
   ↓
Redis guarda order_status:{request_id}=PENDING
   ↓
Worker consume cola y procesa pedido en MySQL
   ↓
Redis -> CONFIRMED / FAILED
   ↓
Cliente consulta /checkout/status/{request_id}
```

---

## Endpoints principales

<details>
<summary><b>Web</b></summary>

- `GET /` Inicio
- `GET /shop` Tienda
- `GET /product/{product_id}` Detalle
- `GET /cart` Carrito
- `GET /checkout` Checkout
- `GET /checkout/status/{request_id}` Estado asíncrono

</details>

<details>
<summary><b>API REST</b></summary>

- `POST /productos`
- `GET /productos`
- `GET /productos/{id}`

Swagger: `http://127.0.0.1:8000/docs`

</details>

---

## Instalación y ejecución

> Ejecuta todo desde `fastapi_app/`

### 1) Preparar entorno

```powershell
cd "C:\xampp\htdocs\Ecommerce-infernocol corte 3\fastapi_app"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

### 2) Configurar variables

```powershell
copy .env.example .env
```

Ajusta en `.env`:

- `DB_HOST`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`
- `REDIS_HOST`, `REDIS_PORT`
- `RABBITMQ_HOST`, `RABBITMQ_PORT`
- (Opcional demo visual) `ORDER_PROCESSING_DELAY_SECONDS=40`

### 3) Levantar Redis + RabbitMQ

```powershell
docker compose up -d
```

RabbitMQ Panel: `http://localhost:15672` (`guest/guest`)

### 4) Ejecutar API y Worker

Terminal A:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Terminal B:

```powershell
.\.venv\Scripts\python.exe -m app.worker
```

---

## Demo rápida

1. Inicia sesión.
2. Agrega producto al carrito.
3. Ve a checkout y confirma pedido.
4. Copia `request_id`.
5. Consulta en Swagger `GET /checkout/status/{request_id}`.
6. Observa transición `PENDING` → `CONFIRMED`.

---

## Troubleshooting

- **`No module named 'app'`**: ejecuta comandos dentro de `fastapi_app/`.
- **`No module named 'redis'`**: usa `python -m pip install -r requirements.txt` con Python del `.venv`.
- **Worker “sin logs”**: es normal, está escuchando cola hasta recibir mensajes.

---

## Demo final (Makefile)

Desde la raíz del proyecto:

```bash
make start
```

Otros comandos:

```bash
make logs
make api
make worker
make stop
```

---

## CI/CD (GitHub Actions)

Pipeline en `.github/workflows/ci.yml`:
- instala dependencias de `fastapi_app`
- valida sintaxis (`compileall`)
- construye imagen Docker de la API

Se ejecuta automáticamente en push/pull request a `main`.

---

## Autores

- **Esteban Murillo Gomez**
- **Miguel Angel Villamil Echavarria**

---

<p align="center">
  <img src="https://capsule-render.vercel.app/api?type=waving&color=0:c084fc,100:7c3aed&height=120&section=footer"/>
</p>