from flask import Flask, render_template, jsonify, request
from pathlib import Path
import json, uuid, os
import firebase_admin
from firebase_admin import credentials, firestore
from functools import wraps
import base64

# =========================
# Flask & локальное хранилище products.json (как было)
# =========================
app = Flask(__name__)

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

# =========================
# Firebase Admin + Firestore (поддержка RAW и B64)
# =========================
def _init_firebase():
    raw = os.environ.get("FIREBASE_SERVICE_ACCOUNT", "").strip()
    b64 = os.environ.get("FIREBASE_SERVICE_ACCOUNT_B64", "").strip()

    if not firebase_admin._apps:
        if raw:
            cred = credentials.Certificate(json.loads(raw))
        elif b64:
            decoded = base64.b64decode(b64).decode("utf-8")
            cred = credentials.Certificate(json.loads(decoded))
        else:
            raise RuntimeError("FIREBASE_SERVICE_ACCOUNT not set")
        firebase_admin.initialize_app(cred)

_init_firebase()
db = firestore.client()
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "dev-secret")

def require_admin(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        token = request.headers.get("X-Admin-Token")
        if token != ADMIN_TOKEN:
            return jsonify({"ok": False, "error": "unauthorized"}), 401
        return f(*args, **kwargs)
    return wrapper

# =========================
# Страницы админ-панели (как было)
# =========================
@app.route("/")
def dashboard():
    return render_template("dashboard.html")

@app.route("/admin/products")
def products():
    return render_template("products.html")

@app.route("/admin/orders")
def orders():
    return render_template("orders.html")

@app.route("/admin/clients")
def clients():
    return render_template("clients.html")

@app.route("/admin/warehouse")
def warehouse():
    return render_template("warehouse.html")

@app.route("/admin/china-orders")
def china_orders():
    return render_template("china_orders.html")

@app.route("/admin/stats")
def stats():
    return render_template("stats.html")

@app.route("/admin/settings")
def settings():
    return render_template("settings.html")

@app.route("/admin/import")
def imp():
    return render_template("import.html")

@app.route("/admin/scanner")
def scanner():
    return render_template("scanner.html")

@app.route("/logout")
def logout():
    return render_template("dashboard.html")

# =========================
# Products API (локальный products.json — как было)
# =========================
@app.route("/api/products", methods=["GET"])
def api_products():
    return jsonify(load_products())

@app.route("/api/products", methods=["POST"])
def api_products_create():
    data = request.get_json() or {}
    item = {
        "id": str(uuid.uuid4()),
        "model": (data.get("model") or "").strip(),
        "quality": (data.get("quality") or "").strip(),
        "price": int(data.get("price") or 0),
        "stock": int(data.get("stock") or 0),
    }
    items = load_products()
    items.append(item)
    save_products(items)
    return jsonify(item), 201

@app.route("/api/products/<id>", methods=["PUT"])
def api_product_id(id):
    data = request.get_json() or {}
    items = load_products()
    for p in items:
        if p.get("id") == id:
            p["model"] = data.get("model", p.get("model"))
            p["quality"] = data.get("quality", p.get("quality"))
            p["price"] = int(data.get("price") or p.get("price", 0))
            p["stock"] = int(data.get("stock") or p.get("stock", 0))
            save_products(items)
            return jsonify(p)
    return jsonify({"error": "not found"}), 404

@app.route("/api/products/<id>", methods=["DELETE"])
def api_product_delete(id):
    items = load_products()
    new_items = [p for p in items if p.get("id") != id]
    if len(new_items) == len(items):
        return jsonify({"error": "not found"}), 404
    save_products(new_items)
    return jsonify({"ok": True})

# =========================
# Firestore API: бренды + импорт
# =========================
@app.get("/api/brands")
def api_brands():
    docs = db.collection("brands").order_by("order").stream()
    items = [{**d.to_dict(), "id": d.id} for d in docs]
    return jsonify({"ok": True, "items": items})

@app.post("/api/import")
@require_admin
def api_import():
    p = request.get_json(force=True, silent=True) or {}
    brand = (p.get("brand") or {})
    prods = (p.get("products") or [])
    slug = (brand.get("slug") or "").strip()
    if not slug:
        return jsonify({"ok": False, "error": "brand.slug required"}), 400

    # upsert brand by slug
    exist = list(db.collection("brands").where("slug", "==", slug).limit(1).stream())
    if exist:
        bref = exist[0].reference
        bref.set({
            "name": brand.get("name", slug.upper()),
            "slug": slug,
            "color": brand.get("color", "#000000"),
            "order": int(brand.get("order", 0)),
            "active": bool(brand.get("active", True)),
        }, merge=True)
        brand_id = bref.id
    else:
        bref = db.collection("brands").document()
        bref.set({
            "name": brand.get("name", slug.upper()),
            "slug": slug,
            "color": brand.get("color", "#000000"),
            "order": int(brand.get("order", 0)),
            "active": bool(brand.get("active", True)),
        })
        brand_id = bref.id

    # batch products -> Firestore
    batch = db.batch()
    pref = db.collection("products")
    count = 0
    for it in prods:
        model = it.get("model")
        price = it.get("price")
        if not model or price is None:
            continue
        doc = pref.document()
        batch.set(doc, {
            "brandId": brand_id,
            "brand": slug,
            "model": model,
            "quality": it.get("quality", ""),
            "price": float(price),
            "currency": it.get("currency", "TJS"),
            "tags": it.get("tags", []),
            "stock": int(it.get("stock", 0)),
            "active": bool(it.get("active", True)),
            "search": f'{slug} {model} {it.get("quality","")}'.lower(),
        })
        count += 1
    batch.commit()
    return jsonify({"ok": True, "brandId": brand_id, "count": count})

# =========================
# Firestore API: товары по бренду (без индексов)
# =========================
@app.get("/api/products-by-brand")
def api_products_by_brand():
    slug = (request.args.get("brand") or "").strip().lower()
    q = (request.args.get("q") or "").strip().lower()  # опционально: поиск

    if not slug:
        return jsonify({"ok": False, "error": "brand param required"}), 400

    # slug -> brandId
    bq = list(db.collection("brands").where("slug", "==", slug).limit(1).stream())
    if not bq:
        return jsonify({"ok": True, "items": []})
    brand_id = bq[0].id

    # Простая выборка без order_by (индексы не требуются)
    docs = db.collection("products")\
             .where("active", "==", True)\
             .where("brandId", "==", brand_id)\
             .stream()

    items = [{**d.to_dict(), "id": d.id} for d in docs]

    # Поиск по подстроке в Python (без индексов)
    if q:
        def mksearch(it):
            base = it.get("search")
            if base:
                return base
            return f"{it.get('brand','')} {it.get('model','')} {it.get('quality','')}".lower()
        items = [it for it in items if q in mksearch(it)]

    # Сортировка в Python
    items.sort(key=lambda x: (str(x.get("model","")).lower(), str(x.get("quality","")).lower()))

    return jsonify({"ok": True, "items": items})

# =========================
# Healthcheck
# =========================
@app.get("/health")
def health():
    return "OK"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8080")), debug=True)
