from flask import Flask, render_template, jsonify, request, Response, redirect, url_for, session, make_response
from pathlib import Path
from functools import wraps
from werkzeug.security import check_password_hash
import json, uuid, os, csv, io
from datetime import datetime

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
            wants_json = request.headers.get("X-Requested-With") == "XMLHttpRequest" \
                         or request.accept_mimetypes["application/json"] >= request.accept_mimetypes["text/html"]
            if wants_json:
                return jsonify({"error": "unauthorized"}), 401
            return redirect(url_for("login", next=request.path))
        return view_func(*args, **kwargs)
    return wrapped

# ====== Файловое хранилище ======
DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)
PRODUCTS_FILE = DATA_DIR / "products.json"
CHINA_ORDERS_FILE = DATA_DIR / "china_orders.json"

def _ensure_file(fp: Path, default_json: str = "[]"):
    if not fp.exists():
        fp.write_text(default_json, encoding="utf-8")

def load_products():
    _ensure_file(PRODUCTS_FILE, "[]")
    with open(PRODUCTS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_products(items):
    with open(PRODUCTS_FILE, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)

# --- Orders storage
def load_orders():
    _ensure_file(CHINA_ORDERS_FILE, "[]")
    with open(CHINA_ORDERS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_orders(items):
    with open(CHINA_ORDERS_FILE, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)

# ====== Утилиты нормализации ======
def one_line(v) -> str:
    s = f"{v or ''}"
    return " ".join(s.split()).strip()

def title_brand(slug: str) -> str:
    s = (slug or "").strip()
    return s[:1].upper() + s[1:] if s else ""

def specs_to_size(specs) -> str:
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
    data = request.get_json(silent=True) or {}
    if not data and request.form:
        data = request.form.to_dict(flat=True)
    return data

def calc_order_totals(order: dict):
    total = 0.0
    for it in (order.get("items") or []):
        price = parse_float(it.get("price"), 0)
        qty = parse_int(it.get("qty"), 0)
        total += price * qty
    total += parse_float(order.get("shipping_cost"), 0)
    order["total"] = round(total, 2)
    order["positions"] = len(order.get("items") or [])
    return order

# =========================
#        Аутентификация
# =========================
@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user") == ADMIN_USER:
        return redirect(url_for("products_page"))

    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        if username == ADMIN_USER and check_password_hash(ADMIN_PASS_HASH, password):
            session["user"] = ADMIN_USER
            next_url = request.args.get("next") or url_for("products_page")
            return redirect(next_url)
        return render_template("login.html"), 401

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
# --- PRODUCTS (без изменений вашего кода) ---
@app.get("/api/products")
def api_products_all():
    return jsonify(load_products())

@app.post("/api/products")
def api_products_create():
    data = get_payload()
    tags_raw = data.get("tags") or ""
    tags = [one_line(t) for t in str(tags_raw).split(",") if one_line(t)]
    specs_text = specs_to_size(data.get("specs"))

    item = {
        "id": str(uuid.uuid4()),
        "brand": one_line((data.get("brand") or "").lower()),
        "model": one_line(data.get("model")),
        "quality": one_line(data.get("quality")),
        "price": parse_float(data.get("price"), 0),
        "currency": one_line(data.get("currency") or "TJS"),
        "vendor": one_line(data.get("vendor")),
        "photo": one_line(data.get("photo")),
        "stock": parse_int(data.get("stock"), 0),
        "type": one_line(data.get("type")),
        "tags": tags,
        "specs": specs_text,
        "active": parse_bool(data.get("active"), True),
    }
    items = load_products()
    items.append(item)
    save_products(items)
    return jsonify(item), 201

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

@app.delete("/api/products/<id>")
def api_products_delete(id):
    items = load_products()
    new_items = [p for p in items if p.get("id") != id]
    if len(new_items) == len(items):
        return jsonify({"error": "not found"}), 404
    save_products(new_items)
    return jsonify({"ok": True})

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

        type_str  = one_line(p.get("type"))
        specs_str = specs_to_size(p.get("specs"))

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
            "type": type_str,
            "tags": p.get("tags") or [],
            "specs": specs_str,
            "size": type_str,
            "stock": int(p.get("stock") or 0),
            "active": bool(p.get("active", True)),
        })

    return jsonify({"ok": True, "items": out})

# --- CHINA ORDERS: полный набор функций ---
@app.get("/api/china-orders")
@login_required
def api_china_orders_list():
    """Список заказов + фильтры: q (поставщик/id), status, date_from, date_to"""
    items = load_orders()
    q = (request.args.get("q") or "").lower().strip()
    status = (request.args.get("status") or "").strip()
    date_from = request.args.get("date_from")
    date_to = request.args.get("date_to")

    def in_range(dt):
        if not dt:
            return True
        try:
            d = datetime.strptime(dt, "%Y-%m-%d").date()
        except Exception:
            return True
        ok = True
        if date_from:
            try:
                ok = ok and d >= datetime.strptime(date_from, "%Y-%m-%d").date()
            except: pass
        if date_to:
            try:
                ok = ok and d <= datetime.strptime(date_to, "%Y-%m-%d").date()
            except: pass
        return ok

    out = []
    for o in items:
        if q and (q not in (o.get("vendor","").lower()) and q not in (o.get("id","").lower())):
            continue
        if status and o.get("status") != status:
            continue
        if not in_range(o.get("date")):
            continue
        out.append(o)
    return jsonify(out)

@app.post("/api/china-orders")
@login_required
def api_china_orders_create():
    data = get_payload()
    order = {
        "id": str(uuid.uuid4()),
        "date": one_line(data.get("date")),
        "vendor": one_line(data.get("vendor")),
        "currency": one_line(data.get("currency") or "TJS"),
        "note": one_line(data.get("note")),
        "shipping_cost": parse_float(data.get("shipping_cost"), 0),
        "items": data.get("items") or [],
        "status": "New"
    }
    calc_order_totals(order)

    items = load_orders()
    items.append(order)
    save_orders(items)
    return jsonify({"ok": True, "order": order}), 201

@app.get("/api/china-orders/<oid>")
@login_required
def api_china_orders_get(oid):
    for o in load_orders():
        if o.get("id") == oid:
            return jsonify(o)
    return jsonify({"error":"not found"}), 404

@app.put("/api/china-orders/<oid>")
@login_required
def api_china_orders_update(oid):
    data = get_payload()
    items = load_orders()
    for i, o in enumerate(items):
        if o.get("id") == oid:
            o.update({
                "date": one_line(data.get("date") or o.get("date","")),
                "vendor": one_line(data.get("vendor") or o.get("vendor","")),
                "currency": one_line(data.get("currency") or o.get("currency","TJS")),
                "note": one_line(data.get("note") or o.get("note","")),
                "shipping_cost": parse_float(data.get("shipping_cost"), o.get("shipping_cost",0)),
                "items": data.get("items") if data.get("items") is not None else o.get("items",[]),
            })
            calc_order_totals(o)
            items[i] = o
            save_orders(items)
            return jsonify({"ok": True, "order": o})
    return jsonify({"error":"not found"}), 404

@app.patch("/api/china-orders/<oid>/status")
@login_required
def api_china_orders_status(oid):
    data = get_payload()
    new_status = one_line(data.get("status"))
    if not new_status:
        return jsonify({"error":"status is required"}), 400
    items = load_orders()
    for o in items:
        if o.get("id") == oid:
            o["status"] = new_status
            save_orders(items)
            return jsonify({"ok": True, "id": oid, "status": new_status})
    return jsonify({"error":"not found"}), 404

@app.delete("/api/china-orders/<oid>")
@login_required
def api_china_orders_delete(oid):
    items = load_orders()
    new_items = [o for o in items if o.get("id") != oid]
    if len(new_items) == len(items):
        return jsonify({"error":"not found"}), 404
    save_orders(new_items)
    return jsonify({"ok": True})

@app.get("/api/china-orders/export.csv")
@login_required
def api_china_orders_export_csv():
    """Экспорт всех заказов в CSV (плоский список строк, одна строка — одна позиция)."""
    items = load_orders()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["order_id","date","vendor","currency","status","note","shipping_cost","item_brand","item_model","item_quality","price","qty","line_total","order_total"])
    for o in items:
        total = o.get("total",0)
        if not o.get("items"):
            writer.writerow([o.get("id"), o.get("date"), o.get("vendor"), o.get("currency"), o.get("status"), o.get("note"), o.get("shipping_cost"), "", "", "", "", "", "", total])
        else:
            for it in o["items"]:
                price = parse_float(it.get("price"),0)
                qty = parse_int(it.get("qty"),0)
                writer.writerow([o.get("id"), o.get("date"), o.get("vendor"), o.get("currency"), o.get("status"), o.get("note"), o.get("shipping_cost"),
                                 it.get("brand",""), it.get("model",""), it.get("quality",""), price, qty, round(price*qty,2), total])
    resp = make_response(output.getvalue())
    resp.headers["Content-Type"] = "text/csv; charset=utf-8"
    resp.headers["Content-Disposition"] = 'attachment; filename="china_orders.csv"'
    return resp

@app.get("/api/china-orders/totals")
@login_required
def api_china_orders_totals():
    """Суммы по валютам и распределение по статусам."""
    sums = {}
    statuses = {}
    for o in load_orders():
        cur = o.get("currency","TJS")
        sums[cur] = round(sums.get(cur,0) + float(o.get("total",0)), 2)
        st = o.get("status","New")
        statuses[st] = statuses.get(st,0) + 1
    return jsonify({"sums": sums, "statuses": statuses})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8080)), debug=True)
