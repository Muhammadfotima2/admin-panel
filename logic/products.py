# logic/products.py
from flask import request, jsonify, Response
from pathlib import Path
import json, uuid

# ---------- Хранилище ----------
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)
PRODUCTS_FILE = DATA_DIR / "products.json"

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

# ---------- Утилиты ----------
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

def norm_ws(v: str) -> str:
    return one_line(v).replace("  ", " ")

def make_sku(brand: str, model: str, quality: str) -> str:
    b = one_line(brand).replace(" ", "-")
    m = one_line(model).replace(" ", "-")
    q = one_line(quality).replace(" ", "-")
    parts = [p for p in (b, m, q) if p]
    return "-".join(parts)

def normalized_item(data: dict, *, keep_id: bool = False) -> dict:
    """Нормализуем входные данные в формат хранения."""
    tags_raw = data.get("tags")
    if isinstance(tags_raw, list):
        tags = [one_line(t) for t in tags_raw if one_line(t)]
    else:
        tags = [one_line(t) for t in str(tags_raw or "").split(",") if one_line(t)]

    brand_raw = one_line((data.get("brand") or ""))  # храним в нижнем регистре
    brand = brand_raw.lower()
    model = one_line(data.get("model"))
    quality = one_line(data.get("quality"))
    price = parse_float(data.get("price"), 0)
    currency = one_line(data.get("currency") or "TJS")
    vendor = one_line(data.get("vendor"))
    photo = one_line(data.get("photo") or data.get("image"))  # допускаем "image"
    stock = parse_int(data.get("stock"), 0)
    type_ = one_line(data.get("type"))
    specs_text = specs_to_size(data.get("specs"))
    active = parse_bool(data.get("active"), True)

    sku = one_line(data.get("sku"))
    if not sku:
        sku = make_sku(brand, model, quality)

    out = {
        "id": (one_line(data.get("id")) if keep_id and data.get("id") else str(uuid.uuid4())),
        "sku": sku,
        "brand": brand,
        "model": model,
        "quality": quality,
        "price": price,
        "currency": currency,
        "vendor": vendor,
        "photo": photo,
        "stock": stock,
        "type": type_,
        "tags": tags,
        "specs": specs_text,
        "active": active,
    }
    return out

def merge_product(dst: dict, src: dict):
    """
    Правила объединения (как во фронте):
    - ключ: SKU (должен быть не пустой)
    - stock: суммируем
    - price: если в src есть цена (>0) — обновляем
    - пустые поля в dst заполняем из src
    """
    dst["stock"] = int(dst.get("stock") or 0) + int(src.get("stock") or 0)
    if parse_float(src.get("price"), 0) > 0:
        dst["price"] = parse_float(src.get("price"), dst.get("price") or 0)

    for k in ("brand", "model", "quality", "currency", "vendor", "photo", "type", "specs"):
        if not one_line(dst.get(k)):
            dst[k] = src.get(k) or dst.get(k)

    # tags: если в src есть — берём их, иначе оставляем dst
    src_tags = src.get("tags") or []
    if isinstance(src_tags, list) and len(src_tags) > 0:
        dst["tags"] = src_tags

    # active: по умолчанию True; если src передал — обновим
    if "active" in src:
        dst["active"] = bool(src.get("active"))

    # sku всегда приводим к виду из src (если dst пустой)
    if not one_line(dst.get("sku")):
        dst["sku"] = src.get("sku") or dst.get("sku")

    # гарантия совместимости с фронтом по названию поля картинок
    if not one_line(dst.get("photo")) and one_line(src.get("image")):
        dst["photo"] = src.get("image")

    return dst

def find_by_sku(items: list, sku: str):
    key = one_line(sku).lower()
    for p in items:
        if one_line(p.get("sku")).lower() == key:
            return p
    return None

# ---------- Фото: префикс и вычисление URL ----------
IMAGES_PREFIX = "/images/"
PLACEHOLDER_IMAGE = "placeholder.png"

def photo_src(photo) -> str:
    """
    Возвращает абсолютный URL для фото:
    - если photo начинается с http — вернуть как есть
    - если пусто — /images/placeholder.png
    - если передано имя файла — префикс /images/
    - если уже передан путь вида images/xxx.jpg — нормализуем к /images/xxx.jpg
    """
    s = one_line(photo)
    if not s:
        return f"{IMAGES_PREFIX}{PLACEHOLDER_IMAGE}"
    low = s.lower()
    if low.startswith("http://") or low.startswith("https://"):
        return s
    s2 = s.lstrip("/")
    if s2.lower().startswith("images/"):
        return f"/{s2}"
    return f"{IMAGES_PREFIX}{s2}"

def with_brand_and_photo(p: dict) -> dict:
    brand = one_line(p.get("brand")).lower()
    return {
        **p,
        "brandLabel": title_brand(brand) or brand.upper(),
        "photoUrl": photo_src(p.get("photo")),
    }

# ---------- Регистрация маршрутов ----------
def register_products_routes(app):
    # ====== CRUD ======
    @app.get("/api/products")
    def api_products_all():
        items = load_products()
        # возвращаем вместе с brandLabel и photoUrl
        out = [with_brand_and_photo(p) for p in items]
        return jsonify(out)

    @app.post("/api/products")
    def api_products_create():
        """
        Upsert по SKU.
        Если товара с таким SKU нет — создаём.
        Если есть — объединяем (stock суммируется, price/пустые поля обновляются).
        """
        data = get_payload()
        item = normalized_item(data, keep_id=False)
        items = load_products()

        if not one_line(item.get("sku")):
            item["sku"] = make_sku(item.get("brand"), item.get("model"), item.get("quality"))

        exist = find_by_sku(items, item["sku"])
        if exist:
            merge_product(exist, item)
            save_products(items)
            return jsonify(with_brand_and_photo(exist)), 200

        items.append(item)
        save_products(items)
        return jsonify(with_brand_and_photo(item)), 201

    @app.put("/api/products/<id>")
    def api_products_update(id):
        data = get_payload()
        items = load_products()

        # найдём по id
        for p in items:
            if p.get("id") == id:
                updated = normalized_item({**p, **data}, keep_id=True)

                # если поменяли SKU и такой SKU уже есть у другого товара — объединим в того
                if one_line(updated.get("sku")) and one_line(updated.get("sku")).lower() != one_line(p.get("sku")).lower():
                    dup = find_by_sku(items, updated["sku"])
                    if dup and dup.get("id") != id:
                        # переносим stock/поля и удаляем исходный
                        merge_product(dup, updated)
                        items = [x for x in items if x.get("id") != id]
                        save_products(items)
                        return jsonify(with_brand_and_photo(dup)), 200

                # обычное обновление
                p.update(updated)
                save_products(items)
                return jsonify(with_brand_and_photo(p)), 200

        return jsonify({"error": "not found"}), 404

    @app.delete("/api/products/<id>")
    def api_products_delete(id):
        items = load_products()
        new_items = [p for p in items if p.get("id") != id]
        if len(new_items) == len(items):
            return jsonify({"error": "not found"}), 404
        save_products(new_items)
        return jsonify({"ok": True})

    # ====== Импорт/Экспорт ======
    @app.post("/api/products/import")
    def api_products_import():
        """
        Принимает массив товаров. Нормализует и объединяет по SKU (upsert).
        """
        payload = request.get_json(silent=True)
        if not isinstance(payload, list):
            return jsonify({"error": "expect array"}), 400

        items = load_products()
        merged = 0
        created = 0

        for row in payload:
            item = normalized_item(row, keep_id=False)
            if not one_line(item.get("sku")):
                item["sku"] = make_sku(item.get("brand"), item.get("model"), item.get("quality"))

            exist = find_by_sku(items, item["sku"])
            if exist:
                merge_product(exist, item)
                merged += 1
            else:
                items.append(item)
                created += 1

        save_products(items)
        return jsonify({"ok": True, "created": created, "merged": merged, "total": len(items)}), 200

    @app.get("/api/products/export")
    def api_products_export():
        items = load_products()
        return Response(
            json.dumps(items, ensure_ascii=False, indent=2),
            mimetype="application/json; charset=utf-8"
        )

    # ====== Справочники/выдача ======
    @app.get("/api/brands")
    def api_brands():
        items = load_products()
        slugs = sorted({(one_line(p.get("brand")) or "").lower()
                        for p in items if one_line(p.get("brand"))})
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
                    one_line(p.get("sku")),
                    one_line(p.get("model")),
                    one_line(p.get("quality")),
                    one_line(p.get("type")),
                    one_line(p.get("specs")),
                    " ".join([one_line(t) for t in (p.get("tags") or [])]),
                ]).lower()
                if q not in hay:
                    continue

            type_str  = one_line(p.get("type"))
            specs_str = specs_to_size(p.get("specs"))

            out.append({
                "id": p.get("id"),
                "sku": one_line(p.get("sku")),
                "brand": p_brand,
                "brandLabel": title_brand(p_brand),
                "model": one_line(p.get("model")),
                "quality": one_line(p.get("quality")),
                "price": parse_float(p.get("price"), 0),
                "currency": one_line(p.get("currency") or "TJS"),
                "vendor": one_line(p.get("vendor")),
                "photo": one_line(p.get("photo")),
                "photoUrl": photo_src(p.get("photo")),
                "type": type_str,
                "tags": p.get("tags") or [],
                "specs": specs_str,
                "size": type_str,   # обратная совместимость
                "stock": int(p.get("stock") or 0),
                "active": bool(p.get("active", True)),
            })

        return jsonify({"ok": True, "items": out})
