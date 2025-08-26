# logic/china_orders.py
from flask import request, jsonify
from pathlib import Path
import json, uuid
from datetime import date
from functools import wraps

# --- Файл для хранения заказов ---
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)
CHINA_FILE = DATA_DIR / "china_orders.json"

def load_china_orders():
    if not CHINA_FILE.exists():
        CHINA_FILE.write_text("[]", encoding="utf-8")
    with open(CHINA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_china_orders(items):
    with open(CHINA_FILE, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)

# --- Утилиты ---
def one_line(v) -> str:
    s = f"{v or ''}"
    return " ".join(s.split()).strip()

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

# --- Декоратор для защиты API (ожидание login_required из app.py) ---
def with_login_required(app):
    def decorator(func):
        @wraps(func)
        def wrapped(*args, **kwargs):
            if "login_required" in app.view_functions:
                return app.view_functions["login_required"](func)(*args, **kwargs)
            return func(*args, **kwargs)
        return wrapped
    return decorator

# --- Регистрация маршрутов ---
def register_china_orders_routes(app):
    # Список заказов
    @app.get("/api/china-orders")
    def api_china_orders_list():
        return jsonify({"ok": True, "items": load_china_orders()})

    # Создание нового заказа
    @app.post("/api/china-orders")
    def api_china_orders_create():
        data = request.get_json(silent=True) or {}

        order_date = one_line(data.get("date")) or str(date.today())
        vendor     = one_line(data.get("vendor"))
        currency   = one_line(data.get("currency") or "TJS")
        note       = one_line(data.get("note"))
        shipping   = parse_float(data.get("shipping_cost"), 0)

        items_in = data.get("items") or []
        items_norm, total = [], 0.0
        for it in items_in:
            brand   = one_line(it.get("brand"))
            model   = one_line(it.get("model"))
            quality = one_line(it.get("quality"))
            price   = parse_float(it.get("price"), 0)
            qty     = parse_int(it.get("qty"), 0)
            line_sum = round(price * qty, 2)
            total += line_sum
            items_norm.append({
                "brand": brand, "model": model, "quality": quality,
                "price": price, "qty": qty, "sum": line_sum
            })

        total = round(total + shipping, 2)

        order = {
            "id": str(uuid.uuid4()),
            "date": order_date,
            "vendor": vendor,
            "currency": currency,
            "note": note,
            "status": "New",
            "shipping_cost": shipping,
            "items": items_norm,
            "total": total
        }

        all_orders = load_china_orders()
        all_orders.append(order)
        save_china_orders(all_orders)

        return jsonify({"ok": True, "order": order}), 201

    # Удаление заказа
    @app.delete("/api/china-orders/<id>")
    def api_china_orders_delete(id):
        orders = load_china_orders()
        new_orders = [o for o in orders if o.get("id") != id]
        if len(new_orders) == len(orders):
            return jsonify({"error": "not found"}), 404
        save_china_orders(new_orders)
        return jsonify({"ok": True})

    # Обновление статуса заказа
    @app.put("/api/china-orders/<id>/status")
    def api_china_orders_status(id):
        data = request.get_json(silent=True) or {}
        new_status = one_line(data.get("status"))
        orders = load_china_orders()
        for o in orders:
            if o.get("id") == id:
                o["status"] = new_status or o.get("status")
                save_china_orders(orders)
                return jsonify({"ok": True, "order": o})
        return jsonify({"error": "not found"}), 404
