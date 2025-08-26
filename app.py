from flask import Flask, render_template, jsonify, request, Response, redirect, url_for, session
from pathlib import Path
from functools import wraps
from werkzeug.security import check_password_hash
import json, uuid, os

app = Flask(__name__)

# ====== Сессии и админ-креды ======
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "change-me-please-very-secret")

ADMIN_USER = "Muhammad"
# Хэш пароля для "Fotimajon2021" (pbkdf2:sha256)
ADMIN_PASS_HASH = "pbkdf2:sha256:1000000$WwOv7o68tBt6SSAF$e04e8141a904cc656031c234a8e13e33b327ebd87d281659bc6c78d9c4f706ee"

def login_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if session.get("user") != ADMIN_USER:
            return redirect(url_for("login", next=request.path))
        return view_func(*args, **kwargs)
    return wrapped

# ====== Файловое хранилище ======
DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)
PRODUCTS_FILE = DATA_DIR / "products.json"

def load_products():
    if not PRODUCTS_FILE.exists():
        PRODUCTS_FILE.write_text("[]", encoding="utf-8")
    with open(PRODUCTS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_products(items):
    with open(PRODUCTS_FILE, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)

# ====== Утилиты нормализации ======
def one_line(v) -> str:
    s = f"{v or ''}"
    return " ".join(s.split()).strip()

def title_brand(slug: str) -> str:
    s = (slug or "").strip()
    return s[:1].upper() + s[1:] if s else ""

def specs_to_size(specs) -> str:
    """Преобразует specs (dict/list/str/многострочный текст) в одну строку."""
    if specs is None:
        return ""
    if isinstance(specs, str):
        return one_line(specs)
    if isinstance(specs, dict):
        parts = []
        for k, v in specs.items():
            key, val = one_line(k), one_line(v)
            if key and val:
                parts.append(f"{key}: {val}")
            elif val:
                parts.append(val)
        return "; ".join(parts)
    if isinstance(specs, list):
        return "; ".join([one_line(x) for x in specs if one_line(x)])
    return one_line(specs)

def parse_bool(v, default=True):
    if v is None or v == "":
        return default
    if isinstance(v, bool):
        return v
    s = str(v).strip().lower()
    return s in ("1", "true", "yes", "y", "on")

def parse_float(v, default=0.0):
    try:
        return float(str(v).replace(",", "."))
    except Exception:
        return float(default)

def parse_int(v, default=0):
    try:
        return int(float(str(v).replace(",", ".")))
    except Exception:
        return int(default)

def get_payload():
    """
    Принимаем и JSON, и form-data.
    Возвращаем обычный dict со строками.
    """
    data = request.get_json(silent=True) or {}
    if not data and request.form:
        data = request.form.to_dict(flat=True)
    return data

# =========================
#        Аутентификация
# =========================
@app.route("/login", methods=["GET", "POST"])
def login():
    # Если уже вошёл — сразу в админ
    if session.get("user") == ADMIN_USER:
        return redirect(url_for("products_page"))

    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        if username == ADMIN_USER and check_password_hash(ADMIN_PASS_HASH, password):
            session["user"] = ADMIN_USER
            next_url = request.args.get("next") or url_for("products_page")
            return redirect(next_url)
        # Неверные данные — показать форму снова с кодом 401
        return render_template("login.html"), 401

    # GET
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# =========================
#         Страницы
# =========================
@app.route("/")
def root_redirect():
    # Корень ведём в админ-товары
    return redirect(url_for("products_page"))

@app.route("/admin/products")
@login_required
def products_page():
    return render_template("products.html")

@app.route("/admin/orders")
@login_required
def orders_page():
    return render_template("orders.html")

@app.route("/admin/clients")
@login_required
def clients_page():
    return render_template("clients.html")

@app.route("/admin/warehouse")
@login_required
def warehouse_page():
    return render_template("warehouse.html")

@app.route("/admin/china-orders")
@login_required
def china_orders_page():
    return render_template("china_orders.html")

@app.route("/admin/stats")
@login_required
def stats_page():
    return render_template("stats.html")

@app.route("/admin/settings")
@login_required
def settings_page():
    return render_template("settings.html")

@app.route("/admin/import")
@login_required
def import_page():
    return render_template("import.html")

@app.route("/admin/scanner")
@login_required
def scanner_page():
    return render_template("scanner.html")

# --- Health ---
@app.get("/health")
def health():
    return Response("OK", content_type="text/plain; charset=utf-8")

# =========================
#            API
# =========================
# (Админ-API по желанию можно тоже закрыть декоратором login_required,
#  но здесь оставляю открытыми, чтобы не ломать текущие интеграции.)

# Все товары
@app.get("/api/products")
def api_products_all():
    return jsonify(load_products())

# Создать товар (принимает JSON ИЛИ form-data)
@app.post("/api/products")
def api_products_create():
    data = get_payload()
    tags_raw = data.get("tags") or ""
    tags = [one_line(t) for t in str(tags_raw).split(",") if one_line(t)]
    specs_text = specs_to_size(data.get("specs"))

    item = {
        "id": str(uuid.uuid4()),
        "brand": one_line((data.get("brand") or "").lower()),  # slug: samsung
        "model": one_line(data.get("model")),
        "quality": one_line(data.get("quality")),
        "price": parse_float(data.get("price"), 0),
        "currency": one_line(data.get("currency") or "TJS"),
        "vendor": one_line(data.get("vendor")),
        "photo": one_line(data.get("photo")),
        "stock": parse_int(data.get("stock"), 0),
        "type": one_line(data.get("type")),
        "tags": tags,
        "specs": specs_text,               # ВСЕГДА СТРОКА
        "active": parse_bool(data.get("active"), True),
    }
    items = load_products()
    items.append(item)
    save_products(items)
    return jsonify(item), 201

# Обновить товар (принимает JSON ИЛИ form-data)
@app.put("/api/products/<id>")
def api_products_update(id):
    data = get_payload()
    tags_raw = data.get("tags")
    specs_text = specs_to_size(data.get("specs")) if "specs" in data else None

    items = load_products()
    for p in items:
        if p.get("id") == id:
            p.update({
                "brand": one_line((data.get("brand") or p.get("brand") or "").lower()),
                "model": one_line(data.get("model") or p.get("model") or ""),
                "quality": one_line(data.get("quality") or p.get("quality") or ""),
                "price": parse_float(data.get("price"), p.get("price") or 0),
                "currency": one_line(data.get("currency") or p.get("currency") or "TJS"),
                "vendor": one_line(data.get("vendor") or p.get("vendor") or ""),
                "photo": one_line(data.get("photo") or p.get("photo") or ""),
                "stock": parse_int(data.get("stock"), p.get("stock") or 0),
                "type": one_line(data.get("type") or p.get("type") or ""),
                "tags": ([one_line(t) for t in str(tags_raw).split(",") if one_line(t)]
                         if tags_raw is not None else (p.get("tags") or [])),
                "specs": (specs_text if specs_text is not None else p.get("specs") or ""),
                "active": parse_bool(data.get("active"), p.get("active", True)),
            })
            save_products(items)
            return jsonify(p)
    return jsonify({"error": "not found"}), 404

# Удалить товар
@app.delete("/api/products/<id>")
def api_products_delete(id):
    items = load_products()
    new_items = [p for p in items if p.get("id") != id]
    if len(new_items) == len(items):
        return jsonify({"error": "not found"}), 404
    save_products(new_items)
    return jsonify({"ok": True})

# Список брендов
@app.get("/api/brands")
def api_brands():
    items = load_products()
    slugs = sorted({(p.get("brand") or "").lower() for p in items if (p.get("brand") or "").strip()})
    out = [{
        "id": s,
        "slug": s,
        "name": title_brand(s) or s.upper(),
        "active": True,
        "order": i + 1,
        "color": "#1D4ED8"
    } for i, s in enumerate(slugs)]
    return jsonify({"ok": True, "items": out})

# Товары по бренду (type отдельно, specs — только текст из админки)
@app.get("/api/products-by-brand")
def api_products_by_brand():
    brand = one_line((request.args.get("brand") or "").lower())
    q = one_line((request.args.get("q") or "").lower())
    items = load_products()
    out = []

    for p in items:
        p_brand = one_line((p.get("brand") or "").lower())
        if brand and p_brand != brand:
            continue

        if q:
            hay = " ".join([
                one_line(p.get("model")),
                one_line(p.get("quality")),
                one_line(p.get("type")),
                " ".join([one_line(t) for t in (p.get("tags") or [])]),
            ]).lower()
            if q not in hay:
                continue

        type_str  = one_line(p.get("type"))                 # IPS / OLED
        specs_str = specs_to_size(p.get("specs"))           # ← строка

        out.append({
            "id": p.get("id"),
            "brand": p_brand,
            "brandLabel": title_brand(p_brand),
            "model": one_line(p.get("model")),
            "quality": one_line(p.get("quality")),
            "price": p.get("price"),
            "currency": one_line(p.get("currency")),
            "vendor": one_line(p.get("vendor")),
            "photo": one_line(p.get("photo")),
            "type": type_str,        # отдельное поле
            "tags": p.get("tags") or [],
            "specs": specs_str,      # только ваш текст
            "size": type_str,        # для совместимости клиента
            "stock": int(p.get("stock") or 0),
            "active": bool(p.get("active", True)),
        })

    return jsonify({"ok": True, "items": out})

if __name__ == "__main__":
    # На Railway лучше не указывать debug=True
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8080)), debug=True)
