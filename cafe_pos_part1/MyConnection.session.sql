-- Tạo database nếu chưa có
CREATE DATABASE IF NOT EXISTS cafe_pos 
CHARACTER SET utf8mb4 
COLLATE utf8mb4_unicode_ci;

-- chọn database
USE cafe_pos;

-- ============================
-- 1. Bảng phân quyền (2 role)
-- ============================
CREATE TABLE IF NOT EXISTS roles (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,     -- admin, customer
    description VARCHAR(255)
);

INSERT IGNORE INTO roles (name, description) VALUES
('admin', 'Quản trị hệ thống'),
('customer', 'Khách hàng tích điểm');

-- ============================
-- 2. Bảng USERS (admin + customer)
-- ============================
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,

    username VARCHAR(50) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL,
    fullname VARCHAR(100),

    role_id INT NOT NULL,    -- admin hoặc customer

    -- Dành cho khách hàng
    phone VARCHAR(20),
    email VARCHAR(100),
    points INT DEFAULT 0,
    vip_level VARCHAR(50) DEFAULT 'basic',

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    FOREIGN KEY (role_id) REFERENCES roles(id)
);

INSERT INTO users (username, password, fullname, phone, email, role_id)
VALUES ('admin', 'admin123', 'Quan tri vien', '', NULL, 1);


-- ============================
-- 3. Danh mục đồ uống
-- ============================
CREATE TABLE IF NOT EXISTS categories (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    description VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================
-- 4. Menu sản phẩm
-- ============================
CREATE TABLE IF NOT EXISTS products (
    id INT AUTO_INCREMENT PRIMARY KEY,
    category_id INT NOT NULL,
    name VARCHAR(100) NOT NULL,
    price DECIMAL(10,2) NOT NULL,
    status TINYINT DEFAULT 1, -- 1: còn bán

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    FOREIGN KEY (category_id) REFERENCES categories(id)
);

-- ============================
-- 5. Danh sách bàn
-- ============================
CREATE TABLE IF NOT EXISTS tables (
    id INT AUTO_INCREMENT PRIMARY KEY,
    table_name VARCHAR(50) NOT NULL UNIQUE,
    status TINYINT DEFAULT 0, -- 0: trống, 1: đang dùng
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO tables (table_name, status) VALUES
('Bàn 1', 0),
('Bàn 2', 0),
('Bàn 3', 0),
('Bàn 4', 1),
('Bàn 5', 0),
('Bàn 6', 0),
('Bàn 7', 1),
('Bàn 8', 0);
-- ============================
-- 6. Đơn hàng
-- ============================
CREATE TABLE IF NOT EXISTS orders (
    id INT AUTO_INCREMENT PRIMARY KEY,

    table_id INT,
    user_id INT,  -- chính là khách hàng (customer)

    status TINYINT DEFAULT 0,  -- 0: đang order, 1: đã thanh toán
    total_amount DECIMAL(12,2) DEFAULT 0,
    note VARCHAR(255),

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (table_id) REFERENCES tables(id),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- ============================
-- 7. Chi tiết đơn hàng
-- ============================
CREATE TABLE IF NOT EXISTS order_items (
    id INT AUTO_INCREMENT PRIMARY KEY,
    order_id INT NOT NULL,
    product_id INT NOT NULL,
    quantity INT NOT NULL DEFAULT 1,
    price DECIMAL(10,2) NOT NULL,
    total DECIMAL(12,2) NOT NULL,

    FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products(id)
);

-- ============================
-- 8. Thanh toán
-- ============================
CREATE TABLE IF NOT EXISTS receipts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    order_id INT NOT NULL,
    user_id INT NOT NULL,  -- người thanh toán (khách hàng)

    amount DECIMAL(12,2) NOT NULL,
    payment_method VARCHAR(50),

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (order_id) REFERENCES orders(id),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- ============================
-- 9. Nhật ký hệ thống
-- ============================
CREATE TABLE IF NOT EXISTS logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT,
    action VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);