from flask import Flask, render_template, jsonify, request, Response
from pathlib import Path
import json, uuid

app = Flask(__name__)

# --- Файловое хранилище ---
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

# --- Страницы ---
@app.route("/")
def dashboard():
    return render_template("dashboard.html")

@app.route("/admin/products")
def products_page():
    return render_template("products.html")

@app.route("/admin/orders")
def orders_page():
    return render_template("orders.html")

@app.route("/admin/clients")
def clients_page():
    return render_template("clients.html")

@app.route("/admin/warehouse")
def warehouse_page():
    return render_template("warehouse.html")

@app.route("/admin/china-orders")
def china_orders_page():
    return render_template("china_orders.html")

@app.route("/admin/stats")
def stats_page():
    return render_template("stats.html")

@app.route("/admin/settings")
def settings_page():
    return render_template("settings.html")

@app.route("/admin/import")
def import_page():
    return render_template("import.html")

@app.route("/admin/scanner")
def scanner_page():
    return render_template("scanner.html")

# --- Health ---
@app.get("/health")
def health():
    return Response("OK", content_type="text/plain; charset=utf-8")

# =========================
#         API
# =========================

# Все товары
@app.get("/api/products")
def api_products_all():
    return jsonify(load_products())

# Создать товар (из формы админки)
@app.post("/api/products")
def api_products_create():
    data = request.get_json(force=True, silent=True) or {}
    item = {
        "id": str(uuid.uuid4()),
        "brand": (data.get("brand") or "").strip().lower(),  # slug: samsung
        "model": (data.get("model") or "").strip(),
        "quality": (data.get("quality") or "").strip(),
        "price": float(data.get("price") or 0),
        "currency": (data.get("currency") or "TJS").strip(),
        "vendor": (data.get("vendor") or "").strip(),        # для «Brend: ...»
        "photo": (data.get("photo") or "").strip(),
        "stock": int(data.get("stock") or 0),
        "type": (data.get("type") or "").strip(),            # бейдж (OLED / Copy AAA)
        "tags": list(data.get("tags") or []),
        "specs": data.get("specs") or {},                    # объект характеристик
        "active": bool(data.get("active", True)),
    }
    items = load_products()
    items.append(item)
    save_products(items)
    return jsonify(item), 201

# Обновить товар
@app.put("/api/products/<id>")
def api_products_update(id):
    data = request.get_json(force=True, silent=True) or {}
    items = load_products()
    for p in items:
        if p.get("id") == id:
            p.update({
                "brand": (data.get("brand") or p.get("brand") or "").strip().lower(),
                "model": (data.get("model") or p.get("model") or "").strip(),
                "quality": (data.get("quality") or p.get("quality") or "").strip(),
                "price": float(data.get("price") or p.get("price") or 0),
                "currency": (data.get("currency") or p.get("currency") or "TJS").strip(),
                "vendor": (data.get("vendor") or p.get("vendor") or "").strip(),
                "photo": (data.get("photo") or p.get("photo") or "").strip(),
                "stock": int(data.get("stock") or p.get("stock") or 0),
                "type": (data.get("type") or p.get("type") or "").strip(),
                "tags": list(data.get("tags") or p.get("tags") or []),
                "specs": data.get("specs") if "specs" in data else (p.get("specs") or {}),
                "active": bool(data.get("active", p.get("active", True))),
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

# Список брендов (на основе товаров)
@app.get("/api/brands")
def api_brands():
    items = load_products()
    slugs = sorted({(p.get("brand") or "").lower() for p in items if (p.get("brand") or "").strip()})
    out = [{"id": s, "slug": s, "name": s.upper(), "active": True, "order": i+1, "color": "#1D4ED8"} for i, s in enumerate(slugs)]
    return jsonify({"ok": True, "items": out})

# Товары по бренду (для приложения)
@app.get("/api/products-by-brand")
def api_products_by_brand():
    brand = (request.args.get("brand") or "").strip().lower()
    q = (request.args.get("q") or "").strip().lower()
    items = load_products()
    out = []
    for p in items:
        if brand and (p.get("brand") or "").lower() != brand:
            continue
        if q:
            hay = " ".join([
                p.get("model",""), p.get("quality",""),
                p.get("type",""), " ".join(p.get("tags") or [])
            ]).lower()
            if q not in hay:
                continue
        # приводим к полям совместимым с приложением
        out.append({
            "id": p.get("id"),
            "brand": p.get("brand"),
            "model": p.get("model"),
            "quality": p.get("quality"),
            "price": p.get("price"),
            "currency": p.get("currency"),
            "vendor": p.get("vendor"),
            "photo": p.get("photo"),
            "type": p.get("type"),
            "tags": p.get("tags") or [],
            "specs": p.get("specs") or {},
            "stock": p.get("stock") or 0,
            "active": p.get("active", True),
          })
    return jsonify({"ok": True, "items": out})

if __name__ == "__main__":
    # локально: python app.py
    app.run(host="0.0.0.0", port=8080, debug=True)
