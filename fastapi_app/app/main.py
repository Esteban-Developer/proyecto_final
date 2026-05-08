from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Form, Request, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from starlette.middleware.sessions import SessionMiddleware

from .db import get_db
from .models import CartItem, Customer, Order, Product, Slider, Category, ProductCategory
from .settings import get_settings
from .utils import (
    REPO_ROOT,
    build_base_context,
    ensure_session_customer_email,
    is_logged_in,
    set_flash,
)
from .api_products import router as productos_router
from .observability import setup_logging, new_request_id, request_id_from_request, log_api
from .order_status import get_order_status, set_order_status
from .queue import enqueue_order_request, QueueConnectionError


settings = get_settings()
setup_logging()

app = FastAPI(title="Inferno Colombia - FastAPI")
app.add_middleware(SessionMiddleware, secret_key=settings.app_secret_key)


TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def _mount_static() -> None:
    # Reutiliza los assets del proyecto original (raíz del repo).
    for mount_path, folder in [
        ("/css", "css"),
        ("/js", "js"),
        ("/img", "img"),
        ("/fonts", "fonts"),
    ]:
        disk_path = REPO_ROOT / folder
        if disk_path.exists():
            app.mount(mount_path, StaticFiles(directory=str(disk_path)), name=folder)


_mount_static()
app.include_router(productos_router)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    incoming_request_id = request.headers.get("x-request-id")
    request.state.request_id = incoming_request_id.strip() if incoming_request_id else new_request_id()
    log_api(request, f"Request {request.method} {request.url.path}")
    response = await call_next(request)
    response.headers["x-request-id"] = request.state.request_id
    return response


def _redirect(url: str) -> RedirectResponse:
    return RedirectResponse(url=url, status_code=303)


def _require_login(request: Request) -> str | RedirectResponse:
    email = ensure_session_customer_email(request)
    if not is_logged_in(email):
        set_flash(request, "Debes iniciar sesión para continuar.")
        return _redirect("/login")
    return email


@app.get("/", response_class=HTMLResponse)
def home(request: Request, db: Session = Depends(get_db)) -> Any:
    ctx = build_base_context(request, db, active="Inicio")

    slides = db.query(Slider).order_by(Slider.slide_id.asc()).all()
    women_products = (
        db.query(Product).filter(Product.cat_id == 2).order_by(Product.products_id.desc()).limit(7).all()
    )
    men_products = (
        db.query(Product).filter(Product.cat_id == 1).order_by(Product.products_id.desc()).limit(7).all()
    )

    ctx.update({"slides": slides, "women_products": women_products, "men_products": men_products})
    return templates.TemplateResponse(request, "index.html", ctx)


@app.post("/search")
def search(request: Request, db: Session = Depends(get_db), search: str = Form(...)) -> Any:
    _ = ensure_session_customer_email(request)
    item = (search or "").strip()
    if not item:
        return _redirect("/shop")

    product = (
        db.query(Product)
        .filter(Product.product_title.like(f"%{item}%"))
        .order_by(Product.products_id.asc())
        .first()
    )
    if not product:
        set_flash(request, "No se encontró ningún producto con ese nombre.")
        return _redirect(request.headers.get("referer") or "/shop")
    return _redirect(f"/product/{product.products_id}")


@app.get("/shop", response_class=HTMLResponse)
def shop(
    request: Request,
    db: Session = Depends(get_db),
    page: int = 1,
    cat_id: int | None = None,
    p_cat_id: int | None = None,
) -> Any:
    ctx = build_base_context(request, db, active="Tienda")
    per_page = 6
    page = max(page, 1)
    offset = (page - 1) * per_page

    title: str | None = None
    desc: str | None = None

    q = db.query(Product).order_by(Product.products_id.desc())
    if p_cat_id is not None:
        pc = db.query(ProductCategory).filter(ProductCategory.p_cat_id == p_cat_id).first()
        if pc:
            title, desc = pc.p_cat_title, pc.p_cat_desc
        q = q.filter(Product.p_cat_id == p_cat_id)
    elif cat_id is not None:
        c = db.query(Category).filter(Category.cat_id == cat_id).first()
        if c:
            title, desc = c.cat_title, c.cat_desc
        q = q.filter(Product.cat_id == cat_id)

    total_records = q.count()
    total_pages = max((total_records + per_page - 1) // per_page, 1)
    products = q.offset(offset).limit(per_page).all()

    ctx.update(
        {
            "products": products,
            "page": page,
            "total_pages": total_pages,
            "cat_id": cat_id,
            "p_cat_id": p_cat_id,
            "filter_title": title,
            "filter_desc": desc,
        }
    )
    return templates.TemplateResponse(request, "shop.html", ctx)


@app.get("/product/{product_id}", response_class=HTMLResponse)
def product_detail(request: Request, product_id: int, db: Session = Depends(get_db)) -> Any:
    ctx = build_base_context(request, db, active="Producto")

    product = db.query(Product).filter(Product.products_id == product_id).first()
    if not product:
        set_flash(request, "Producto no encontrado.")
        return _redirect("/shop")

    pcat = db.query(ProductCategory).filter(ProductCategory.p_cat_id == product.p_cat_id).first()
    related = (
        db.query(Product)
        .filter(Product.p_cat_id == product.p_cat_id, Product.products_id != product.products_id)
        .order_by(Product.products_id.desc())
        .limit(4)
        .all()
    )

    ctx.update({"product": product, "pcat": pcat, "related_products": related})
    return templates.TemplateResponse(request, "product.html", ctx)


@app.post("/cart/add")
def cart_add(
    request: Request,
    db: Session = Depends(get_db),
    product_id: int = Form(...),
    product_qty: int = Form(1),
    size: str = Form(...),
) -> Any:
    email_or_redirect = _require_login(request)
    if isinstance(email_or_redirect, RedirectResponse):
        return email_or_redirect
    customer_email = email_or_redirect

    product = db.query(Product).filter(Product.products_id == product_id).first()
    if not product:
        set_flash(request, "Producto no encontrado.")
        return _redirect("/shop")

    qty = max(int(product_qty), 1)
    exists = (
        db.query(CartItem)
        .filter(CartItem.c_id == customer_email, CartItem.products_id == product_id)
        .first()
    )
    if exists:
        set_flash(request, "Producto ya agregado.")
        return _redirect(f"/product/{product_id}")

    item = CartItem(
        products_id=product_id,
        c_id=customer_email,
        ip_add=request.client.host if request.client else "0.0.0.0",
        qty=qty,
        size=size,
    )
    db.add(item)
    db.commit()

    set_flash(request, "Producto agregado al carrito. Continúa comprando.")
    return _redirect(f"/product/{product_id}")


@app.get("/cart", response_class=HTMLResponse)
def cart_view(request: Request, db: Session = Depends(get_db)) -> Any:
    ctx = build_base_context(request, db, active="Carrito de Compras")
    customer_email = ctx["session_customer_email"]

    if not is_logged_in(customer_email):
        set_flash(request, "Inicia sesión para ver tu carrito.")
        return _redirect("/login")

    items = (
        db.query(CartItem)
        .filter(CartItem.c_id == customer_email)
        .order_by(CartItem.date.desc())
        .all()
    )
    product_ids = [i.products_id for i in items]
    products = db.query(Product).filter(Product.products_id.in_(product_ids)).all() if product_ids else []
    product_by_id = {p.products_id: p for p in products}

    cart_rows: list[dict[str, Any]] = []
    subtotal = 0
    for i in items:
        p = product_by_id.get(i.products_id)
        if not p:
            continue
        row_total = int(p.product_price) * int(i.qty)
        subtotal += row_total
        cart_rows.append(
            {
                "product": p,
                "qty": int(i.qty),
                "size": i.size,
                "row_total": row_total,
            }
        )

    ctx.update({"cart_rows": cart_rows, "subtotal": subtotal, "total": subtotal})
    return templates.TemplateResponse(request, "cart.html", ctx)


@app.get("/cart/remove/{product_id}")
def cart_remove(request: Request, product_id: int, db: Session = Depends(get_db)) -> Any:
    email_or_redirect = _require_login(request)
    if isinstance(email_or_redirect, RedirectResponse):
        return email_or_redirect
    customer_email = email_or_redirect

    db.query(CartItem).filter(CartItem.c_id == customer_email, CartItem.products_id == product_id).delete()
    db.commit()
    return _redirect("/cart")


@app.get("/checkout", response_class=HTMLResponse)
def checkout(
    request: Request,
    db: Session = Depends(get_db),
    place: int | None = None,
    request_id: str | None = None,
) -> Any:
    ctx = build_base_context(request, db, active="Checkout")
    customer_email = ctx["session_customer_email"]

    if not is_logged_in(customer_email):
        set_flash(request, "Inicia sesion para finalizar compra.")
        return _redirect("/login")

    customer = db.query(Customer).filter(Customer.customer_email == customer_email).first()
    if not customer:
        set_flash(request, "Usuario no encontrado.")
        request.session["customer_email"] = "unset"
        return _redirect("/login")

    items = db.query(CartItem).filter(CartItem.c_id == customer_email).all()
    if place is not None:
        if not items:
            set_flash(request, "No hay articulos en el carrito.")
            return _redirect("/cart")

        current_request_id = request_id_from_request(request)
        payload = {
            "customer_email": customer_email,
            "customer_id": int(customer.customer_id),
        }
        try:
            log_api(request, "Evento de checkout enviado a RabbitMQ")
            created_request_id = enqueue_order_request(payload, request_id=current_request_id)
        except QueueConnectionError:
            log_api(request, "RabbitMQ no disponible al intentar enviar checkout")
            set_flash(request, "RabbitMQ no disponible. Intenta nuevamente en unos segundos.")
            return _redirect("/checkout")

        set_order_status(created_request_id, "PENDING")
        log_api(request, f"Estado en Redis actualizado a PENDING ({created_request_id})")
        return _redirect(f"/checkout?request_id={created_request_id}")

    product_ids = [i.products_id for i in items]
    products = db.query(Product).filter(Product.products_id.in_(product_ids)).all() if product_ids else []
    product_by_id = {p.products_id: p for p in products}

    order_lines: list[dict[str, Any]] = []
    total = 0
    for i in items:
        p = product_by_id.get(i.products_id)
        if not p:
            continue
        line_total = int(p.product_price) * int(i.qty)
        total += line_total
        order_lines.append({"name": p.product_title, "qty": int(i.qty), "line_total": line_total})

    checkout_status = None
    if request_id:
        checkout_status = get_order_status(request_id) or "PENDING"

    ctx.update(
        {
            "order_lines": order_lines,
            "subtotal": total,
            "total": total,
            "request_id": request_id,
            "checkout_status": checkout_status,
        }
    )
    return templates.TemplateResponse(request, "checkout.html", ctx)


@app.get("/checkout/status/{request_id}")
def checkout_status(request_id: str, request: Request) -> JSONResponse:
    status = get_order_status(request_id) or "NOT_FOUND"
    log_api(request, f"Consulta de estado checkout => {request_id} = {status}")
    return JSONResponse({"request_id": request_id, "status": status})


@app.get("/login", response_class=HTMLResponse)
def login_form(request: Request, db: Session = Depends(get_db)) -> Any:
    ctx = build_base_context(request, db, active="Iniciar Sesión")
    return templates.TemplateResponse(request, "login.html", ctx)


@app.post("/login")
def login_submit(
    request: Request,
    db: Session = Depends(get_db),
    correo_cliente: str = Form(...),
    clave_cliente: str = Form(...),
) -> Any:
    _ = ensure_session_customer_email(request)
    correo = (correo_cliente or "").strip()
    clave = (clave_cliente or "").strip()

    customer = (
        db.query(Customer)
        .filter(Customer.customer_email == correo, Customer.customer_pass == clave)
        .first()
    )
    if not customer:
        set_flash(request, "Usuario o contraseña incorrectos.")
        return _redirect("/login")

    request.session["customer_email"] = correo
    cart_count = db.query(CartItem).filter(CartItem.c_id == correo).count()
    if cart_count == 0:
        return _redirect("/?stat=1")
    return _redirect("/checkout")


@app.get("/logout")
def logout(request: Request) -> Any:
    request.session.clear()
    return _redirect("/login")


@app.get("/register", response_class=HTMLResponse)
def register_form(request: Request, db: Session = Depends(get_db)) -> Any:
    ctx = build_base_context(request, db, active="Registro")
    return templates.TemplateResponse(request, "register.html", ctx)


@app.post("/register")
def register_submit(
    request: Request,
    db: Session = Depends(get_db),
    name: str = Form(...),
    cemail: str = Form(...),
    password: str = Form(...),
    address: str = Form(...),
    contact: str = Form(...),
    pimage: UploadFile = File(...),
) -> Any:
    _ = ensure_session_customer_email(request)
    email = (cemail or "").strip()

    existing = db.query(Customer).filter(Customer.customer_email == email).first()
    if existing:
        set_flash(request, "Ese correo ya está registrado. Inicia sesión.")
        return _redirect("/login")

    img_dir = REPO_ROOT / "img" / "customer"
    img_dir.mkdir(parents=True, exist_ok=True)
    safe_name = os.path.basename(pimage.filename or "profile.png")
    target_path = img_dir / safe_name
    with target_path.open("wb") as f:
        f.write(pimage.file.read())

    customer = Customer(
        customer_name=name,
        customer_email=email,
        customer_pass=password,
        customer_address=address,
        customer_contact=contact,
        customer_image=safe_name,
        customer_ip=0,
    )
    db.add(customer)
    db.commit()

    request.session["customer_email"] = email
    cart_count = db.query(CartItem).filter(CartItem.c_id == email).count()
    set_flash(request, "Cuenta registrada exitosamente. Has iniciado sesión.")
    if cart_count > 0:
        return _redirect("/checkout")
    return _redirect("/")


@app.get("/account", response_class=HTMLResponse)
def account(request: Request, db: Session = Depends(get_db), orders: int | None = None, details: int | None = None) -> Any:
    ctx = build_base_context(request, db, active="Mi Cuenta")
    customer_email = ctx["session_customer_email"]
    if not is_logged_in(customer_email):
        set_flash(request, "Inicia sesión para ver tu cuenta.")
        return _redirect("/login")

    customer = db.query(Customer).filter(Customer.customer_email == customer_email).first()
    if not customer:
        set_flash(request, "Usuario no encontrado.")
        request.session["customer_email"] = "unset"
        return _redirect("/login")

    orders_list: list[Order] = []
    if orders is not None:
        orders_list = (
            db.query(Order)
            .filter(Order.c_id == int(customer.customer_id))
            .order_by(Order.date.desc())
            .all()
        )

    ctx.update({"show_orders": orders is not None, "show_details": details is not None, "orders_list": orders_list})
    return templates.TemplateResponse(request, "account.html", ctx)


@app.get("/contact", response_class=HTMLResponse)
def contact_form(request: Request, db: Session = Depends(get_db)) -> Any:
    ctx = build_base_context(request, db, active="Contacto")
    return templates.TemplateResponse(request, "contact.html", ctx)


@app.post("/contact")
def contact_submit(
    request: Request,
    db: Session = Depends(get_db),
    name: str = Form(...),
    email: str = Form(...),
    subject: str = Form(...),
    message: str = Form(...),
) -> Any:
    _ = ensure_session_customer_email(request)

    if settings.smtp_host and settings.smtp_to_email:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = settings.smtp_user or settings.smtp_to_email
        msg["To"] = settings.smtp_to_email
        msg.set_content(f"De: {name} <{email}>\n\n{message}")

        try:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
                smtp.starttls()
                if settings.smtp_user and settings.smtp_password:
                    smtp.login(settings.smtp_user, settings.smtp_password)
                smtp.send_message(msg)
        except Exception:
            set_flash(request, "No se pudo enviar el mensaje (SMTP no configurado o error).")
            return _redirect("/contact")

    set_flash(request, "¡Tu mensaje ha sido enviado exitosamente!")
    return _redirect("/contact")


@app.get("/admin/insert-product", response_class=HTMLResponse)
def admin_insert_product_form(request: Request, db: Session = Depends(get_db)) -> Any:
    ctx = build_base_context(request, db, active="Admin")
    ctx.update(
        {
            "all_categories": db.query(Category).order_by(Category.cat_id.asc()).all(),
            "all_product_categories": db.query(ProductCategory).order_by(ProductCategory.p_cat_id.asc()).all(),
        }
    )
    return templates.TemplateResponse(request, "admin_insert_product.html", ctx)


@app.post("/admin/insert-product")
def admin_insert_product_submit(
    request: Request,
    db: Session = Depends(get_db),
    product_title: str = Form(...),
    p_cat_id: int = Form(...),
    cat_id: int = Form(...),
    product_price: int = Form(...),
    product_keywords: str = Form(...),
    product_desc: str = Form(""),
    product_img1: UploadFile = File(...),
    product_img2: UploadFile = File(...),
) -> Any:
    _ = ensure_session_customer_email(request)

    img_dir = REPO_ROOT / "img" / "products"
    img_dir.mkdir(parents=True, exist_ok=True)

    img1_name = os.path.basename(product_img1.filename or "img1.png")
    img2_name = os.path.basename(product_img2.filename or "img2.png")
    (img_dir / img1_name).write_bytes(product_img1.file.read())
    (img_dir / img2_name).write_bytes(product_img2.file.read())

    prod = Product(
        p_cat_id=p_cat_id,
        cat_id=cat_id,
        product_title=product_title,
        product_img1=img1_name,
        product_img2=img2_name,
        product_price=int(product_price),
        product_keywords=product_keywords,
        product_desc=product_desc,
    )
    db.add(prod)
    db.commit()

    set_flash(request, "Producto insertado.")
    return _redirect("/admin/insert-product")

