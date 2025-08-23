
from flask import Flask, render_template, jsonify, request
from pathlib import Path
import json, uuid, os

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

# -------- Products API --------
@app.route("/api/products", methods=["GET"])
def api_products():
    return jsonify(load_products())

@app.route("/api/products", methods=["POST"])
def api_products_create():
    data = request.get_json() or {}
    item = {
        "id": str(uuid.uuid4()),
        "model": data.get("model", "").strip(),
        "quality": data.get("quality", "").strip(),
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
            p["price"] = int(data.get("price") or 0)
            p["stock"] = int(data.get("stock") or 0)
            save_products(items)
            return jsonify(p)
    return jsonify({"error":"not found"}), 404

@app.route("/api/products/<id>", methods=["DELETE"])
def api_product_delete(id):
    items = load_products()
    new_items = [p for p in items if p.get("id") != id]
    if len(new_items) == len(items):
        return jsonify({"error":"not found"}), 404
    save_products(new_items)
    return jsonify({"ok": True})

if __name__ == "__main__":
    app.run(debug=True)
