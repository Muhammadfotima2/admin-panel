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

# --- Утилиты нормализации ---
def one_line(v) -> str:
    s = f"{v or ''}"
    return " ".join(s.split()).strip()

def title_brand(slug: str) -> str:
    s = (slug or "").strip()
    return s[:1].upper() + s[1:] if s else ""

def specs_to_size(specs) -> str:
    """Преобразует specs (dict/list/str) в одну строку без переносов."""
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

# --- Страницы (админка) ---
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
#            API
# =========================

# Все товары
@app.get("/api/products")
def api_products_all():
    return jsonify(load_products())

# Создать товар
@app.post("/api/products")
def api_products_create():
    data = request.get_json(force=True, silent=True) or {}
    item = {
        "id": str(uuid.uuid4()),
        "brand": one_line((data.get("brand") or "").lower()),  # slug: samsung
        "model": one_line(data.get("model")),
        "quality": one_line(data.get("quality")),
        "price": float(data.get("price") or 0),
        "currency": one_line(data.get("currency") or "TJS"),
        "vendor": one_line(data.get("vendor")),
        "photo": one_line(data.get("photo")),
        "stock": int(data.get("stock") or 0),
        "type": one_line(data.get("type")),
        "tags": list(data.get("tags") or []),
        "specs": data.get("specs") or {},          # можно строку или объект
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
                "brand": one_line((data.get("brand") or p.get("brand") or "").lower()),
                "model": one_line(data.get("model") or p.get("model") or ""),
                "quality": one_line(data.get("quality") or p.get("quality") or ""),
                "price": float(data.get("price") or p.get("price") or 0),
                "currency": one_line(data.get("currency") or p.get("currency") or "TJS"),
                "vendor": one_line(data.get("vendor") or p.get("vendor") or ""),
                "photo": one_line(data.get("photo") or p.get("photo") or ""),
                "stock": int(data.get("stock") or p.get("stock") or 0),
                "type": one_line(data.get("type") or p.get("type") or ""),
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

# Товары по бренду (без смешивания полей)
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

        type_str  = one_line(p.get("type"))         # IPS / OLED (отдельно)
        specs_str = specs_to_size(p.get("specs"))   # ВАШИ характеристики (строкой)

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
            "type": type_str,        # показывается отдельно
            "tags": p.get("tags") or [],
            "specs": specs_str,      # только то, что ввели в админке
            "size": type_str,        # дублируем type для совместимости клиента
            "stock": int(p.get("stock") or 0),
            "active": bool(p.get("active", True)),
        })

    return jsonify({"ok": True, "items": out})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
