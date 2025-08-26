# app.py
from flask import Flask, render_template, Response, redirect, url_for, session, request, jsonify
from functools import wraps
from werkzeug.security import check_password_hash
import os

# Подключаем маршруты из модулей логики
from logic.products import register_products_routes
from logic.china_orders import register_china_orders_routes

app = Flask(__name__)

# ====== Сессии и админ-креды ======
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "change-me-please-very-secret")

ADMIN_USER = "Muhammad"
# Хэш для пароля "Fotimajon2021" (pbkdf2:sha256)
ADMIN_PASS_HASH = "pbkdf2:sha256:1000000$WwOv7o68tBt6SSAF$e04e8141a904cc656031c234a8e13e33b327ebd87d281659bc6c78d9c4f706ee"

def login_required(view_func):
    """
    Правило простое и надёжное:
      - Не залогинен и путь начинается с /api/ -> JSON 401
      - Не залогинен и это страница -> redirect на /login
    """
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if session.get("user") != ADMIN_USER:
            if request.path.startswith("/api/"):
                return jsonify({"error": "unauthorized"}), 401
            return redirect(url_for("login", next=request.path))
        return view_func(*args, **kwargs)
    return wrapped

# =========================
#        Аутентификация
# =========================
@app.route("/login", methods=["GET", "POST"])
def login():
    # уже залогинен
    if session.get("user") == ADMIN_USER:
        return redirect(url_for("products_page"))

    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        if username == ADMIN_USER and check_password_hash(ADMIN_PASS_HASH, password):
            session["user"] = ADMIN_USER
            next_url = request.args.get("next") or url_for("products_page")
            return redirect(next_url)
        # неверные креды
        return render_template("login.html"), 401

    # GET
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# Диагностика: быстро понять, вошли ли
@app.get("/whoami")
def whoami():
    return jsonify({
        "user": session.get("user"),
        "is_admin": session.get("user") == ADMIN_USER
    })

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
#   Регистрация модулей API
# =========================
register_products_routes(app)        # /api/products, /api/products/import, /api/products/export, /api/brands, /api/products-by-brand
register_china_orders_routes(app)    # /api/china-orders*, экспорт, статусы

if __name__ == "__main__":
    # На хостингах (Railway/Render/Heroku) PORT приходит из окружения
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8080)), debug=True)
