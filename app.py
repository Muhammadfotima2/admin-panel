from flask import Flask, render_template, jsonify, request, Response, redirect, url_for, session
from pathlib import Path
from os import getenv
import json, uuid, functools

app = Flask(__name__)

# ===== СЕССИИ / ДОСТУП =====
app.secret_key = getenv("SECRET_KEY", "change-me-in-env")
ADMIN_USER = getenv("ADMIN_USER", "admin")
ADMIN_PASS = getenv("ADMIN_PASS", "set-me")

def is_authed() -> bool:
    return bool(session.get("authed") is True)

def require_auth(fn):
    @functools.wraps(fn)
    def _wrap(*args, **kwargs):
        if not is_authed():
            return redirect(url_for("login", next=request.path))
        return fn(*args, **kwargs)
    return _wrap

# ===== ХРАНИЛИЩЕ =====
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

# ===== УТИЛИТЫ =====
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
    return s in ("1", "true", "yes", "y", "on", "да")

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

# ===== АУТЕНТИФИКАЦИЯ =====
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = (request.form.get("username") or "").strip()
        p = (request.form.get("password") or "").strip()
        if u == ADMIN_USER and p == ADMIN_PASS:
            session["authed"] = True
            return redirect(request.args.get("next") or url_for("dashboard"))
        return render_template("login.html", error="Неверный логин или пароль")
    return render_template("login.html")

@app.get("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# ===== СТРАНИЦЫ =====
@app.route("/")
@require_auth
def dashboard():
    return render_template("dashboard.html")

@app.route("/admin/products")
@require_auth
def products_page():
    return render_template("products.html")

@app.route("/admin/orders")
@require_auth
def orders_page():
    return render_template("orders.html")

@app.route("/admin/clients")
@require_auth
def clients_page():
    return render_template("clients.html")

@app.route("/admin/warehouse")
@require_auth
def warehouse_page():
    return render_template("warehouse.html")

@app.route("/admin/china-orders")
@require_auth
def china_orders_page():
    return render_template("china_orders.html")

@app.route("/admin/stats")
@require_auth
def stats_page():
    return render_template("stats.html")

@app.route("/admin/settings")
@require_auth
def settings_page():
    return render_template("settings.html")

@app.route("/admin/import")
@require_auth
def import_page():
    return render_template("import.html")

@app.route("/admin/scanner")
@require_auth
def scanner_page():
    return render_template("scanner.html")

# ===== Health =====
@app.get("/health")
def health():
    return Response("OK", content_type="text/plain; charset=utf-8")

# =========================
#            API (PROTECTED)
# =========================
@app.get("/api/products")
@require_auth
def api_products_all():
    return jsonify(load_products())

@app.post("/api/products")
@require_auth
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
@require_auth
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
@require_auth
def api_products_delete(id):
    items = load_products()
    new_items = [p for p in items if p.get("id") != id]
    if len(new_items) == len(items):
        return jsonify({"error": "not found"}), 404
    save_products(new_items)
    return jsonify({"ok": True})

@app.get("/api/brands")
@require_auth
def api_brands():
    items = load_products()
    slugs = sorted({(p.get("brand") or "").lower() for p in items if (p.get("brand") or "").strip()})
    out = [{
        "id": s, "slug": s, "name": title_brand(s) or s.upper(),
        "active": True, "order": i + 1, "color": "#1D4ED8"
    } for i, s in enumerate(slugs)]
    return jsonify({"ok": True, "items": out})

@app.get("/api/products-by-brand")
@require_auth
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
            "id": p.get("id"), "brand": p_brand, "brandLabel": title_brand(p_brand),
            "model": one_line(p.get("model")), "quality": one_line(p.get("quality")),
            "price": p.get("price"), "currency": one_line(p.get("currency")),
            "vendor": one_line(p.get("vendor")), "photo": one_line(p.get("photo")),
            "type": type_str, "tags": p.get("tags") or [], "specs": specs_str,
            "size": type_str, "stock": int(p.get("stock") or 0),
            "active": bool(p.get("active", True)),
        })
    return jsonify({"ok": True, "items": out})

# === EXPORT CSV ===
@app.get("/api/products/export")
@require_auth
def api_products_export():
    import io, csv, time
    from flask import send_file
    items = load_products()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["id","brand","model","quality","price","currency","vendor","photo","type","tags","specs","stock","active","created_at"])
    now = int(time.time())
    for p in items:
        tags = ",".join(p.get("tags") or [])
        w.writerow([
            p.get("id",""), p.get("brand",""), p.get("model",""), p.get("quality",""),
            p.get("price",""), p.get("currency","TJS"), p.get("vendor",""), p.get("photo",""),
            p.get("type",""), tags, p.get("specs",""), int(p.get("stock") or 0),
            1 if p.get("active", True) else 0, int(p.get("created_at") or now),
        ])
    mem = io.BytesIO(buf.getvalue().encode("utf-8-sig"))
    return send_file(mem, mimetype="text/csv", as_attachment=True, download_name="products.csv")

# === IMPORT CSV ===
@app.post("/api/products/import")
@require_auth
def api_products_import():
    import csv, io, time
    if "file" not in request.files:
        return jsonify({"ok": False, "error": "file is required"}), 400
    f = request.files["file"]
    text = f.read().decode("utf-8", errors="ignore")
    rdr = csv.DictReader(io.StringIO(text))
    items = load_products()
    now = int(time.time())
    added = 0
    for r in rdr:
        def g(*keys, default=""):
            for k in keys:
                if k in r and str(r[k]).strip() != "":
                    return str(r[k]).strip()
            return default
        tags_raw = g("tags","Теги")
        tags = [t.strip() for t in tags_raw.split(",") if t.strip()]
        try:    price = float(g("price","Цена", default="0").replace(",",".")) if g("price","Цена") else 0
        except: price = 0
        try:    stock = int(float(g("stock","Остаток", default="0").replace(",","."))) if g("stock","Остаток") else 0
        except: stock = 0
        item = {
            "id": g("id","ID", default=str(uuid.uuid4())),
            "brand": g("brand","Бренд").lower(),
            "model": g("model","Модель"),
            "quality": g("quality","Качество"),
            "price": price,
            "currency": g("currency","Валюта", default="TJS"),
            "vendor": g("vendor","Поставщик"),
            "photo": g("photo","Фото"),
            "type": g("type","Тип"),
            "tags": tags,
            "specs": g("specs","Характеристики"),
            "stock": stock,
            "active": g("active","Активен", default="1") in ("1","true","True","да","Да","yes","on"),
            "created_at": int(g("created_at","createdAt", default=str(now)) or now),
        }
        if item["model"] and item["quality"]:
            items.append(item); added += 1
    save_products(items)
    return jsonify({"ok": True, "added": added, "total": len(items)})

# === МАССОВОЕ ОБНОВЛЕНИЕ ОСТАТКОВ ===
@app.put("/api/stock-batch")
@require_auth
def api_stock_batch():
    rows = request.get_json(silent=True) or []
    if not isinstance(rows, list):
        return jsonify({"ok": False, "error": "list expected"}), 400
    items = load_products()
    by_id = {p.get("id"): p for p in items}
    updated = 0
    for row in rows:
        try:
            pid = str(row.get("id") or "")
            if pid and pid in by_id:
                by_id[pid]["stock"] = parse_int(row.get("stock"), by_id[pid].get("stock") or 0)
                updated += 1
        except Exception:
            pass
    save_products(items)
    return jsonify({"ok": True, "updated": updated, "total": len(items)})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
