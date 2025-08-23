
from flask import Flask, render_template

app = Flask(__name__)

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

if __name__ == "__main__":
    app.run(debug=True)
