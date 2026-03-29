from functools import wraps
from flask import Flask, jsonify, redirect, render_template, request, session
import mysql.connector
from mysql.connector import Error, IntegrityError
from datetime import datetime

app = Flask(__name__)
app.secret_key = "secret123"

# Cấu hình Database - Vui lòng cập nhật mật khẩu của bạn ở đây
def get_db():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="1234567890", # Thay đổi theo máy bạn
        database="cafe_pos",
        charset="utf8mb4",
        collation="utf8mb4_unicode_ci",
    )

# Decorator: Yêu cầu đăng nhập
def login_required(view_func):
    @wraps(view_func)
    def wrapped_view(*args, **kwargs):
        if "user_id" not in session:
            return redirect("/login")
        return view_func(*args, **kwargs)
    return wrapped_view

# Decorator: Yêu cầu quyền Admin
def admin_required(view_func):
    @wraps(view_func)
    def wrapped_view(*args, **kwargs):
        if "user_id" not in session:
            return redirect("/login")
        
        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT role_id FROM users WHERE id=%s", (session["user_id"],))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not user or user["role_id"] != 1:
            return "Bạn không có quyền truy cập trang này!", 403
        return view_func(*args, **kwargs)
    return wrapped_view

# --- ROUTES CHO ADMIN ---

@app.route("/admin")
@admin_required
def admin_dashboard():
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    
    # Thống kê tổng quan
    cursor.execute("SELECT SUM(total_amount) as total FROM orders WHERE status=1")
    total_revenue = cursor.fetchone()["total"] or 0
    
    cursor.execute("SELECT COUNT(*) as count FROM orders WHERE status=1")
    total_orders = cursor.fetchone()["count"]
    
    cursor.execute("SELECT COUNT(*) as count FROM users WHERE role_id=2")
    total_customers = cursor.fetchone()["count"]

    # Dữ liệu biểu đồ doanh thu 7 ngày gần nhất
    cursor.execute("""
        SELECT DATE(created_at) as date, SUM(total_amount) as revenue 
        FROM orders WHERE status=1 
        GROUP BY DATE(created_at) 
        ORDER BY date DESC LIMIT 7
    """)
    chart_data = cursor.fetchall()
    chart_data.reverse()

    cursor.close()
    conn.close()
    
    return render_template("admin.html", 
                           page="dashboard",
                           revenue=total_revenue, 
                           orders=total_orders, 
                           customers=total_customers,
                           chart_data=chart_data)

@app.route("/admin/products", methods=["GET", "POST"])
@admin_required
def admin_products():
    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    if request.method == "POST":
        action = request.form.get("action")
        name = request.form.get("name")
        price = request.form.get("price")
        category_id = request.form.get("category_id")
        image_url = request.form.get("image_url")
        product_id = request.form.get("product_id")

        try:
            if action == "add":
                cursor.execute(
                    "INSERT INTO products (name, price, category_id, image_url) VALUES (%s, %s, %s, %s)",
                    (name, price, category_id, image_url)
                )
            elif action == "edit":
                cursor.execute(
                    "UPDATE products SET name=%s, price=%s, category_id=%s, image_url=%s WHERE id=%s",
                    (name, price, category_id, image_url, product_id)
                )
            elif action == "delete":
                cursor.execute("DELETE FROM products WHERE id=%s", (product_id,))
            
            conn.commit()
        except Error as e:
            print(f"Error: {e}")
            conn.rollback()

    cursor.execute("SELECT p.*, c.name as cat_name FROM products p JOIN categories c ON p.category_id = c.id")
    products = cursor.fetchall()
    
    cursor.execute("SELECT * FROM categories")
    categories = cursor.fetchall()
    
    cursor.close()
    conn.close()
    return render_template("admin.html", page="products", products=products, categories=categories)

@app.route("/admin/reports")
@admin_required
def admin_reports():
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    
    # Doanh thu chi tiết theo ngày
    cursor.execute("""
        SELECT DATE(created_at) as date, COUNT(id) as order_count, SUM(total_amount) as daily_revenue 
        FROM orders WHERE status=1 
        GROUP BY DATE(created_at) 
        ORDER BY date DESC
    """)
    daily_reports = cursor.fetchall()
    
    cursor.close()
    conn.close()
    return render_template("admin.html", page="reports", daily_reports=daily_reports)

# --- ROUTES CŨ (CẬP NHẬT) ---

@app.route("/login", methods=["GET", "POST"])
def login():
    message = ""
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]
        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE username=%s AND password=%s", (username, password))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if user:
            session["user_id"] = user["id"]
            session["role_id"] = user["role_id"]
            if user["role_id"] == 1:
                return redirect("/admin")
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
        # Thêm dòng này để lấy thông tin người dùng đang đăng nhập
        cursor.execute("SELECT * FROM users WHERE id=%s", (session["user_id"],))
        user = cursor.fetchone()
    finally:
        cursor.close()
        conn.close()
    # Truyền thêm biến user vào template
    return render_template("tables.html", tables=tables, user=user)

@app.route("/")
@login_required
def home():
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE id=%s", (session["user_id"],))
    user = cursor.fetchone()
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

@app.route("/order/<int:table_id>")
@login_required
def order_page(table_id):
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    try:
        # Lấy thông tin bàn
        cursor.execute("SELECT * FROM tables WHERE id=%s", (table_id,))
        table = cursor.fetchone()
        
        if not table: return "Khong tim thay ban", 404

        # LẤY THÔNG TIN USER ĐỂ HIỆN ĐIỂM (Cập nhật ở đây)
        cursor.execute("SELECT * FROM users WHERE id=%s", (session["user_id"],))
        user = cursor.fetchone()

        # Lấy danh sách sản phẩm
        cursor.execute("SELECT id, name, price, image_url FROM products WHERE status=1 ORDER BY name")
        products = cursor.fetchall()
    finally:
        cursor.close()
        conn.close()
    
    # Truyền biến user vào template
    return render_template("order.html", products=products, table=table, user=user)

@app.route("/checkout", methods=["POST"])
@login_required
def checkout():
    data = request.get_json(silent=True) or {}
    table_id = data.get("table_id")
    items = data.get("items") or []
    if not table_id or not items:
        return jsonify({"error": "Dữ liệu không hợp lệ"}), 400

    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    try:
        # Lấy thông tin sản phẩm để tính tiền
        ids = [i["product_id"] for i in items]
        format_strings = ','.join(['%s'] * len(ids))
        cursor.execute(f"SELECT id, price FROM products WHERE id IN ({format_strings})", tuple(ids))
        price_map = {row["id"]: row["price"] for row in cursor.fetchall()}

        total_amount = sum(price_map[i["product_id"]] * i["quantity"] for i in items)
        
        # Lưu đơn hàng
        cursor.execute("INSERT INTO orders (table_id, user_id, status, total_amount) VALUES (%s, %s, 1, %s)", 
                       (table_id, session["user_id"], total_amount))
        order_id = cursor.lastrowid

        for item in items:
            p_id = item["product_id"]
            qty = item["quantity"]
            price = price_map[p_id]
            cursor.execute("INSERT INTO order_items (order_id, product_id, quantity, price, total) VALUES (%s, %s, %s, %s, %s)",
                           (order_id, p_id, qty, price, price * qty))

        # Cộng điểm: 1k = 1 điểm
        points = int(total_amount // 1000)
        cursor.execute("UPDATE users SET points = points + %s WHERE id=%s", (points, session["user_id"]))
        conn.commit()
        return jsonify({"message": "Thanh toán thành công", "order_id": order_id, "points_added": points})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    app.run(debug=True) 