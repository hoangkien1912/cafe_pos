from flask import Flask, jsonify, redirect, render_template, request, session, url_for
import mysql.connector
from mysql.connector import Error, IntegrityError
from datetime import datetime
from functools import wraps
from contextlib import closing

app = Flask(__name__)
app.secret_key = "secret123"

# ==========================================
# CẤU HÌNH DATABASE
# ==========================================
def get_db():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="123456",  # Nhớ đổi lại đúng pass của bạn nhé
        database="cafe_pos",
        charset="utf8mb4",
        collation="utf8mb4_unicode_ci",
    )

def write_log(user_id, action):
    """
    Chèn một mục log vào bảng logs với user_id, hành động và timestamp.
    """
    conn = get_db()
    cur = conn.cursor()
    try:
        # Sử dụng truy vấn tham số để tránh SQL Injection【9†L146-L154】
        cur.execute(
            "INSERT INTO logs (user_id, action, created_at) VALUES (%s, %s, NOW())",
            (user_id, action)
        )
        conn.commit()  # commit ngay để ghi log vĩnh viễn【14†L662-L670】
    except Exception as e:
        print("Log Error:", e)
        conn.rollback()  # rollback nếu có lỗi
    finally:
        cur.close()
        conn.close()  # Đóng kết nối (contextlib.closing tương tự)【20†L175-L182】


# Hàm lấy thông tin user nhanh
def get_user_info(user_id):
    with closing(get_db()) as conn:
        with closing(conn.cursor(dictionary=True)) as cursor:
            cursor.execute("SELECT * FROM users WHERE id=%s", (user_id,))
            return cursor.fetchone()

# ==========================================
# DECORATORS (PHÂN QUYỀN)
# ==========================================
def login_required(view_func):
    @wraps(view_func)
    def wrapped_view(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return view_func(*args, **kwargs)
    return wrapped_view

def admin_required(view_func):
    @wraps(view_func)
    def wrapped_view(*args, **kwargs):
        # Kiểm tra xem role_id có phải là 1 (Admin) hay không
        if session.get("role_id") != 1:
            return "Bạn không có quyền truy cập trang quản trị!", 403
        return view_func(*args, **kwargs)
    return wrapped_view

# ==========================================
# ROUTES ĐĂNG NHẬP / ĐĂNG KÝ
# ==========================================
@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("admin_dashboard")) if session.get("role_id") == 1 else redirect(url_for("home"))
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        with closing(get_db()) as conn:
            with closing(conn.cursor(dictionary=True)) as cursor:
                cursor.execute("SELECT * FROM users WHERE username=%s AND password=%s", (username, password))
                user = cursor.fetchone()
        
        if user:
            session.update({"user_id": user["id"], "role_id": user["role_id"], "fullname": user["fullname"]})
            write_log(user["id"], "Đăng nhập")
            return redirect(url_for("admin_dashboard")) if user["role_id"] == 1 else redirect(url_for("home"))
        return render_template("login.html", message="Sai tài khoản hoặc mật khẩu!")
    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        data = (request.form.get("username"), request.form.get("password"), request.form.get("fullname"), request.form.get("phone"), request.form.get("email"))
        try:
            with closing(get_db()) as conn:
                with closing(conn.cursor()) as cursor:
                    cursor.execute("INSERT INTO users (username, password, fullname, phone, email, role_id, points) VALUES (%s, %s, %s, %s, %s, 2, 0)", data)
                    conn.commit()
                    write_log(cursor.lastrowid, "Đăng ký tài khoản")
            return render_template("login.html", message="Đăng ký thành công! Hãy đăng nhập.")
        except IntegrityError:
            return render_template("register.html", message="Tên tài khoản đã tồn tại!")
    return render_template("register.html")

# ==========================================
# ROUTES KHÁCH HÀNG (HOME, CHỌN BÀN, ĐẶT MÓN)
# ==========================================
@app.route("/home")
@login_required
def home():
    user = get_user_info(session["user_id"])
    return render_template("home.html", user=user, show_history=False)

@app.route("/history")
@login_required
def history():
    user = get_user_info(session["user_id"])
    with closing(get_db()) as conn:
        with closing(conn.cursor(dictionary=True)) as cursor:
            cursor.execute("SELECT o.*, t.table_name FROM orders o LEFT JOIN tables t ON o.table_id = t.id WHERE o.user_id = %s ORDER BY o.created_at DESC", (session["user_id"],))
            orders = cursor.fetchall()
    return render_template("home.html", user=user, orders=orders, show_history=True)

@app.route("/tables")
@login_required
def table_list():
    user = get_user_info(session["user_id"])
    with closing(get_db()) as conn:
        with closing(conn.cursor(dictionary=True)) as cursor:
            cursor.execute("SELECT * FROM tables ORDER BY id")
            tables = cursor.fetchall()
    return render_template("tables.html", tables=tables, user=user)

# ĐÂY LÀ ROUTE GÂY LỖI 500 BAN NÃY - ĐÃ FIX ĐẦY ĐỦ BIẾN
@app.route("/order/<int:table_id>")
@login_required
def order_page(table_id):
    user = get_user_info(session["user_id"])
    with closing(get_db()) as conn:
        with closing(conn.cursor(dictionary=True)) as cursor:
            # Lấy thông tin bàn
            cursor.execute("SELECT * FROM tables WHERE id=%s", (table_id,))
            table = cursor.fetchone()
            if not table: return "Không tìm thấy bàn", 404

            # Lấy danh mục và sản phẩm (Tránh thiếu biến cho file order.html)
            cursor.execute("SELECT * FROM categories")
            categories = cursor.fetchall()
            
            cursor.execute("SELECT * FROM products WHERE status=1 OR status IS NULL ORDER BY name")
            products = cursor.fetchall()

    return render_template("order.html", products=products, table=table, user=user, categories=categories)

@app.route("/checkout", methods=["POST"])
@login_required
def checkout():
    data = request.get_json(silent=True) or {}
    table_id, items = data.get("table_id"), data.get("items", [])
    if not items: return jsonify({"error": "Đơn hàng trống"}), 400

    with closing(get_db()) as conn:
        with closing(conn.cursor(dictionary=True)) as cursor:
            try:
                # Tính tổng tiền chuẩn xác từ Database
                total_amount = 0
                for item in items:
                    cursor.execute("SELECT price FROM products WHERE id=%s", (item["product_id"],))
                    product = cursor.fetchone()
                    if product:
                        total_amount += product["price"] * item["quantity"]

                # Tạo đơn
                cursor.execute("INSERT INTO orders (table_id, user_id, status, total_amount) VALUES (%s, %s, 1, %s)", (table_id, session["user_id"], total_amount))
                order_id = cursor.lastrowid

                # Chi tiết đơn
                for item in items:
                    cursor.execute("SELECT price FROM products WHERE id=%s", (item["product_id"],))
                    price = cursor.fetchone()["price"]
                    cursor.execute("INSERT INTO order_items (order_id, product_id, quantity, price, total) VALUES (%s,%s,%s,%s,%s)", 
                                   (order_id, item["product_id"], item["quantity"], price, price * item["quantity"]))
                cursor.execute("""
                    INSERT INTO receipts (order_id, user_id, amount, payment_method)
                    VALUES (%s, %s, %s, %s)
                """, (order_id, session["user_id"], total_amount, None))    
                # Cộng điểm và trả bàn
                points = int(total_amount // 10000)
                cursor.execute("UPDATE users SET points = points + %s WHERE id=%s", (points, session["user_id"]))
                cursor.execute("UPDATE tables SET status = 0 WHERE id=%s", (table_id,))
                
                conn.commit()
                write_log(session["user_id"], f"Thanh toán đơn hàng #{order_id}")
                return jsonify({"message": "Thành công", "order_id": order_id, "points": points})
            except Exception as e:
                conn.rollback()
                return jsonify({"error": str(e)}), 500

# @app.route("/invoice/<int:order_id>")
# @login_required
# def export_invoice_pdf(order_id):
#     with closing(get_db()) as conn:
#         with closing(conn.cursor(dictionary=True)) as cursor:
#             cursor.execute("SELECT o.*, t.table_name, u.fullname FROM orders o JOIN tables t ON o.table_id = t.id JOIN users u ON o.user_id = u.id WHERE o.id = %s", (order_id,))
#             order = cursor.fetchone()
#             cursor.execute("SELECT oi.*, p.name FROM order_items oi JOIN products p ON oi.product_id = p.id WHERE oi.order_id = %s", (order_id,))
#             items = cursor.fetchall()
#     return render_template('invoice.html', order=order, items=items)

@app.route("/receipt/<int:order_id>")
@login_required
def view_receipt(order_id):
    with closing(get_db()) as conn:
        with closing(conn.cursor(dictionary=True)) as cursor:
            
            cursor.execute("""
                SELECT o.*, t.table_name, u.fullname
                FROM orders o
                JOIN tables t ON o.table_id = t.id
                JOIN users u ON o.user_id = u.id
                WHERE o.id = %s
            """, (order_id,))
            order = cursor.fetchone()

            cursor.execute("""
                SELECT oi.*, p.name
                FROM order_items oi
                JOIN products p ON oi.product_id = p.id
                WHERE oi.order_id = %s
            """, (order_id,))
            items = cursor.fetchall()

    return render_template("receipt.html", order=order, items=items)
# ==========================================
# QUẢN TRỊ ADMIN (NẾU CÓ DÙNG)
# ==========================================
@app.route("/admin")
@login_required
@admin_required
def admin_dashboard():
    with closing(get_db()) as conn:
        with closing(conn.cursor(dictionary=True)) as cursor:
            cursor.execute("SELECT SUM(total_amount) as total FROM orders")
            revenue = cursor.fetchone()["total"] or 0
            cursor.execute("SELECT COUNT(*) as c FROM orders")
            orders_count = cursor.fetchone()["c"]
            cursor.execute("SELECT COUNT(*) as c FROM users WHERE role_id=2")
            customers_count = cursor.fetchone()["c"]
            cursor.execute("SELECT DATE(created_at) as date, SUM(total_amount) as revenue FROM orders GROUP BY date ORDER BY date DESC LIMIT 7")
            chart_data = cursor.fetchall()
    return render_template("admin.html", page="dashboard", revenue=revenue, orders=orders_count, customers=customers_count, chart_data=chart_data)


@app.route("/admin/reports")
@admin_required
def admin_reports():
    with closing(get_db()) as conn:
        with closing(conn.cursor(dictionary=True)) as cursor:
            cursor.execute("""
                SELECT DATE(created_at) as date, COUNT(*) as order_count, SUM(total_amount) as daily_revenue 
                FROM orders WHERE status=1 GROUP BY DATE(created_at) ORDER BY date DESC
            """)
            daily_reports = cursor.fetchall()
    return render_template("admin.html", page="reports", daily_reports=daily_reports)

@app.route("/admin/report/view")
@admin_required
def admin_report_view():
    with closing(get_db()) as conn:
        with closing(conn.cursor(dictionary=True)) as cursor:
            cursor.execute("SELECT SUM(total_amount) as total FROM orders WHERE status=1")
            revenue = cursor.fetchone()["total"] or 0

            cursor.execute("""
                SELECT DATE(created_at) as date, 
                       SUM(total_amount) as revenue 
                FROM orders 
                GROUP BY DATE(created_at) 
                ORDER BY date DESC
            """)
            data = cursor.fetchall()

    # Render ra trang HTML để xem
    return render_template("admin_report.html", revenue=revenue, data=data, now=datetime.now())

@app.route("/admin/products", methods=["GET", "POST"])
@admin_required
def admin_products():
    with closing(get_db()) as conn:
        with closing(conn.cursor(dictionary=True)) as cursor:
            if request.method == "POST":
                action = request.form.get("action")
                p_id = request.form.get("product_id")
                name, price = request.form.get("name"), request.form.get("price")
                cat_id, img = request.form.get("category_id"), request.form.get("image_url")

                if action == "add":
                    cursor.execute("INSERT INTO products (name, price, category_id, image_url, status) VALUES (%s,%s,%s,%s, 1)", (name, price, cat_id, img))
                    conn.commit()
                    write_log(session["user_id"], f"Thêm sản phẩm {name}")
                elif action == "edit":
                    cursor.execute("UPDATE products SET name=%s, price=%s, category_id=%s, image_url=%s WHERE id=%s", (name, price, cat_id, img, p_id))
                    conn.commit()
                    write_log(session["user_id"], f"Sửa sản phẩm ID={p_id}")
                elif action == "delete":
                    cursor.execute("UPDATE products SET status=0 WHERE id=%s", (p_id,))
                    conn.commit()
                    write_log(session["user_id"], f"Xóa sản phẩm ID={p_id}")


            cursor.execute("SELECT p.*, c.name as cat_name FROM products p LEFT JOIN categories c ON p.category_id = c.id WHERE p.status=1")
            products = cursor.fetchall()
            cursor.execute("SELECT * FROM categories")
            categories = cursor.fetchall()
    return render_template("admin.html", page="products", products=products, categories=categories)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

if __name__ == "__main__":
    app.run(debug=True)