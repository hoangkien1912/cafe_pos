from functools import wraps

from flask import Flask, jsonify, redirect, render_template, request, session
import mysql.connector
from mysql.connector import Error, IntegrityError

app = Flask(__name__)
app.secret_key = "secret123"


def get_db():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="123456",
        database="cafe_pos",
        charset="utf8mb4",
        collation="utf8mb4_unicode_ci",
    )


def login_required(view_func):
    @wraps(view_func)
    def wrapped_view(*args, **kwargs):
        if "user_id" not in session:
            return redirect("/login")
        return view_func(*args, **kwargs)

    return wrapped_view


def init_default_admin():
    conn = get_db()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT id FROM roles WHERE name = %s", ("admin",))
        role = cursor.fetchone()
        if not role:
            cursor.execute(
                "INSERT INTO roles (name, description) VALUES (%s, %s)",
                ("admin", "Quan tri he thong"),
            )
            admin_role_id = cursor.lastrowid
        else:
            admin_role_id = role[0]

        cursor.execute("SELECT id FROM users WHERE username = %s", ("admin",))
        user = cursor.fetchone()
        if not user:
            cursor.execute(
                """
                INSERT INTO users (username, password, fullname, role_id)
                VALUES (%s, %s, %s, %s)
                """,
                ("admin", "admin123", "Administrator", admin_role_id),
            )
            conn.commit()
    finally:
        cursor.close()
        conn.close()


def init_sample_data():
    conn = get_db()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT COUNT(*) FROM products")
        count = cursor.fetchone()[0]

        if count == 0:
            print(">>> Tao menu mau...")

            cursor.execute("SELECT id FROM categories WHERE name = %s", ("Đồ uống",))
            category = cursor.fetchone()

            if category:
                cate_id = category[0]
            else:
                cursor.execute(
                    "INSERT INTO categories (name, description) VALUES (%s, %s)",
                    ("Đồ uống", "Menu mặc định"),
                )
                cate_id = cursor.lastrowid

            sample = [
                ("Cà phê sữa", 30000),
                ("Trà đào cam sả", 40000),
                ("Trà sữa trân châu", 35000),
                ("Sinh tố xoài", 45000),
                ("Bạc xỉu", 32000),
                ("Hồng trà kem cheese", 38000),
            ]

            for name, price in sample:
                cursor.execute(
                    "INSERT INTO products (category_id, name, price) VALUES (%s, %s, %s)",
                    (cate_id, name, price),
                )

            conn.commit()
            print(">>> Tao menu mau thanh cong!")
    finally:
        cursor.close()
        conn.close()

@app.route("/login", methods=["GET", "POST"])
def login():
    message = ""

    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]

        conn = get_db()
        cursor = conn.cursor(dictionary=True)

        try:
            cursor.execute(
                "SELECT * FROM users WHERE username=%s AND password=%s",
                (username, password),
            )
            user = cursor.fetchone()
        finally:
            cursor.close()
            conn.close()

        if user:
            session["user_id"] = user["id"]
            return redirect("/tables")

        message = "Sai tài khoản hoặc mật khẩu!"

    return render_template("login.html", message=message)


@app.route("/tables")
@login_required
def table_list():
    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("SELECT * FROM tables ORDER BY id")
        tables = cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

    return render_template("tables.html", tables=tables)


@app.route("/register", methods=["GET", "POST"])
def register():
    msg = ""

    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]
        fullname = request.form["fullname"].strip()
        phone = request.form["phone"].strip()
        email = request.form["email"].strip()

        conn = get_db()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                INSERT INTO users (username, password, fullname, phone, email, role_id)
                VALUES (%s, %s, %s, %s, %s, 2)
                """,
                (username, password, fullname, phone, email or None),
            )
            conn.commit()
            msg = "Tạo tài khoản thành công! Bạn có thể đăng nhập."
        except IntegrityError:
            conn.rollback()
            msg = "Tên tài khoản đã tồn tại, vui lòng chọn tên khác."
        finally:
            cursor.close()
            conn.close()

    return render_template("register.html", message=msg)


@app.route("/")
@login_required
def home():
    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("SELECT * FROM users WHERE id=%s", (session["user_id"],))
        user = cursor.fetchone()
    finally:
        cursor.close()
        conn.close()

    if not user:
        session.clear()
        return redirect("/login")

    return render_template("home.html", user=user)


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


@app.route("/add_points", methods=["POST"])
@login_required
def add_points():
    try:
        total = int(request.form["total"])
    except (KeyError, TypeError, ValueError):
        return "Tong hoa don khong hop le", 400

    if total < 0:
        return "Tong hoa don khong hop le", 400

    points = total // 10000

    conn = get_db()
    cursor = conn.cursor()

    try:
        cursor.execute(
            "UPDATE users SET points = points + %s WHERE id=%s",
            (points, session["user_id"]),
        )
        conn.commit()
    finally:
        cursor.close()
        conn.close()

    return redirect("/")


@app.route("/order/<int:table_id>")
@login_required
def order_page(table_id):
    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("SELECT * FROM tables WHERE id=%s", (table_id,))
        table = cursor.fetchone()

        if not table:
            return "Khong tim thay ban", 404

        cursor.execute(
            "SELECT id, name, price FROM products WHERE status=1 ORDER BY name"
        )
        products = cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

    return render_template("order.html", products=products, table=table)


@app.route("/checkout", methods=["POST"])
@login_required
def checkout():
    data = request.get_json(silent=True) or {}
    table_id = data.get("table_id")
    items = data.get("items") or []

    if not table_id or not items:
        return jsonify({"error": "Du lieu thanh toan khong hop le"}), 400

    payment_method = "cash"

    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("SELECT * FROM tables WHERE id=%s", (table_id,))
        table = cursor.fetchone()
        if not table:
            return jsonify({"error": "Khong tim thay ban"}), 404

        product_ids = [item.get("product_id") for item in items if item.get("product_id")]
        if len(product_ids) != len(items):
            return jsonify({"error": "San pham khong hop le"}), 400

        placeholders = ", ".join(["%s"] * len(product_ids))
        cursor.execute(
            f"SELECT id, name, price, status FROM products WHERE id IN ({placeholders})",
            tuple(product_ids),
        )
        product_rows = cursor.fetchall()
        product_map = {product["id"]: product for product in product_rows}

        if len(product_map) != len(set(product_ids)):
            return jsonify({"error": "Co san pham khong ton tai"}), 400

        total_amount = 0
        normalized_items = []

        for item in items:
            product_id = item["product_id"]
            quantity = item.get("quantity", 0)

            if not isinstance(quantity, int) or quantity <= 0:
                return jsonify({"error": "So luong san pham khong hop le"}), 400

            product = product_map.get(product_id)
            if not product or product["status"] != 1:
                return jsonify({"error": "San pham hien khong con ban"}), 400

            price = int(product["price"])
            line_total = price * quantity
            total_amount += line_total
            normalized_items.append(
                {
                    "product_id": product_id,
                    "name": product["name"],
                    "quantity": quantity,
                    "price": price,
                    "total": line_total,
                }
            )

        points = total_amount // 10000

        cursor.execute("UPDATE tables SET status=1 WHERE id=%s", (table_id,))
        cursor.execute(
            """
            INSERT INTO orders (table_id, user_id, status, total_amount)
            VALUES (%s, %s, 1, %s)
            """,
            (table_id, session["user_id"], total_amount),
        )
        order_id = cursor.lastrowid

        for item in normalized_items:
            cursor.execute(
                """
                INSERT INTO order_items (order_id, product_id, quantity, price, total)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    order_id,
                    item["product_id"],
                    item["quantity"],
                    item["price"],
                    item["total"],
                ),
            )

        cursor.execute(
            "UPDATE users SET points = points + %s WHERE id=%s",
            (points, session["user_id"]),
        )
        cursor.execute(
            """
            INSERT INTO receipts (order_id, user_id, amount, payment_method)
            VALUES (%s, %s, %s, %s)
            """,
            (order_id, session["user_id"], total_amount, payment_method),
        )
        cursor.execute("UPDATE tables SET status=0 WHERE id=%s", (table_id,))

        conn.commit()
    except Error:
        conn.rollback()
        return jsonify({"error": "Khong the thanh toan don hang"}), 500
    finally:
        cursor.close()
        conn.close()

    return jsonify(
        {
            "message": "Thanh toan thanh cong",
            "order_id": order_id,
            "points_added": points,
            "total_amount": total_amount,
        }
    )


# if __name__ == "__main__":
#     init_default_admin()
#     init_sample_data()
#     app.run(debug=True)
