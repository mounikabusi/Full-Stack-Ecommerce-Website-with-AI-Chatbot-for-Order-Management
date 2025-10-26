from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import sqlite3
import hashlib
import os
from datetime import datetime, timedelta
from chatbot import Chatbot  # Import chatbot class


app = Flask(__name__)
app.secret_key = os.urandom(24)  # Set a secret key for session management
chatbot = Chatbot()  # Initialize chatbot

@app.route('/chatbot', methods=['POST'])
def chatbot_endpoint():
    data = request.get_json()
    user_message = data.get("message", "").lower()
    
    user_id = session.get('user_id')
    
    response = chatbot.process_message(user_message, user_id, session)
    result = {"response": response}
    
    if "add to cart" in user_message or "added to your cart" in response:
        words = user_message.split()
        product_name = " ".join(words[words.index("add") + 2:])
        
        conn = sqlite3.connect('ecommerce.db')
        c = conn.cursor()
        c.execute('SELECT id FROM products WHERE name LIKE ?', (f'%{product_name}%',))
        product = c.fetchone()
        conn.close()
        
        if product and user_id:
            product_id = product[0]
            if 'cart' not in session:
                session['cart'] = {}
            
            cart = session['cart']
            if str(product_id) in cart:
                cart[str(product_id)] += 1
            else:
                cart[str(product_id)] = 1
            
            session['cart'] = cart
            result["response"] = f"{product_name} added to your cart."
            
            if "proceed to checkout" in user_message:
                result["redirect"] = url_for('checkout')
    
    elif "place order" in user_message or "checkout" in user_message:
        cart = session.get('cart', {})
        if user_id and cart:
            result["redirect"] = url_for('checkout')
            result["response"] = "Taking you to checkout to complete your order."
        else:
            result["response"] = "Your cart is empty. Add products before checking out."
    
    elif "cancel order" in user_message:
        words = user_message.replace("#", "").split()
        order_id = next((word for word in words if word.isdigit()), None)

        if order_id and user_id:
            conn = sqlite3.connect('ecommerce.db')
            c = conn.cursor()

            c.execute('SELECT id FROM orders WHERE id = ? AND user_id = ?', (order_id, user_id))
            existing_order = c.fetchone()

            if existing_order:
                c.execute('UPDATE orders SET status = ? WHERE id = ? AND user_id = ?', 
                         ('cancelled', order_id, user_id))
                conn.commit()
                result["response"] = f"Order #{order_id} has been cancelled."
            else:
                result["response"] = f"Order #{order_id} not found or already cancelled."

            conn.close()
    
    elif "view cart" in user_message:
        if user_id:
            result["redirect"] = url_for('cart')
            result["response"] = "Taking you to your cart."
    
    elif "track order" in user_message:
        order_id = chatbot.extract_order_id(user_message)
        if order_id and user_id:
            # Update the order status before fetching it
            update_order_status(order_id, user_id)
            order = chatbot.get_order_status(order_id, user_id)
            if order:
                result["response"] = f"Your order #{order_id} is currently {order[1]}. The total amount is ₹{order[3]}. Items: {order[4]}"
            else:
                result["response"] = f"I couldn't find order #{order_id}. Please check the order number and try again."
        else:
            result["response"] = "Please provide your order ID so I can track it for you."
    
    return jsonify(result)

# Database initialization
def init_db():
    conn = sqlite3.connect('ecommerce.db')
    c = conn.cursor()
    
    # Users table
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            username TEXT NOT NULL,
            password TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Products table
    c.execute('''
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT NOT NULL,
        price REAL NOT NULL,
        image TEXT NOT NULL
    )
''')
    
    # Orders table
    c.execute('''
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        total_amount DECIMAL(10, 2) NOT NULL,
        status TEXT NOT NULL,
        shipping_address TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
''')
    
    # Order items table
    c.execute('''
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            price_at_time DECIMAL(10, 2) NOT NULL,
            FOREIGN KEY (order_id) REFERENCES orders (id),
            FOREIGN KEY (product_id) REFERENCES products (id)
        )
    ''')
    
    # Insert some sample products
    c.execute('SELECT COUNT(*) FROM products')
    if c.fetchone()[0] == 0:
        sample_products = [
           ('Idli Mix', 'Soft and fluffy idli premix', 50.00, '/static/images/idli.png'),
    ('Dosa Mix', 'Crispy dosa batter mix', 60.00, '/static/images/dosa.png'),
    ('Upma Mix', 'Delicious and quick upma premix', 40.00, '/static/images/upma.png'),
    ('Poha Mix', 'Authentic poha premix', 55.00, '/static/images/poha.png'),
    ('Pancake Mix', 'Fluffy pancake premix, perfect for quick breakfasts', 150.00, '/static/images/pan-cake.png'),
    ('Cake Mix', 'Classic soft vanilla cake premix', 120.00, '/static/images/cake.png'),
    ('Vanilla Cake Mix', 'Soft and fluffy vanilla cake premix', 120.00, '/static/images/vanila.png'),
    ('Strawberry Cake Mix', 'Sweet and fruity strawberry cake premix', 120.00, '/static/images/strawberry.png'),
    ('Thandai Mix', 'Refreshing traditional thandai drink mix', 100.00, '/static/images/thandai.png'),
    ('Badam Milk Mix', 'Creamy almond-flavored milk premix', 80.00, '/static/images/badam milk.png'),
    ('Chutney Mix', 'Savory and spicy chutney premix', 70.00, '/static/images/chutney.png'),
    ('Sambar Mix', 'Authentic South Indian sambar premix', 90.00, '/static/images/sambar.png'),
    ('Rasam Mix', 'Spicy and tangy rasam premix', 85.00, '/static/images/rasam.png')
        ]
        c.executemany('INSERT INTO products (name, description, price, image) VALUES (?, ?, ?, ?)', 
              sample_products)

    
    conn.commit()
    conn.close()

# Initialize database on startup
init_db()

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

@app.route('/')
def home():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = sqlite3.connect('ecommerce.db')
    c = conn.cursor()
    c.execute('SELECT * FROM products')
    products = c.fetchall()
    conn.close()
    
    return render_template('index.html', products=products)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = hash_password(request.form['password'])
        
        conn = sqlite3.connect('ecommerce.db')
        c = conn.cursor()
        c.execute('SELECT id, email FROM users WHERE email = ? AND password = ?', 
                 (email, password))
        user = c.fetchone()
        conn.close()
        
        if user:
            session['user_id'] = user[0]
            session['email'] = user[1]
            return redirect(url_for('home'))
        else:
            flash('Invalid email or password')
    
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form['email']
        username = request.form['username']
        password = hash_password(request.form['password'])
        
        conn = sqlite3.connect('ecommerce.db')
        c = conn.cursor()
        try:
            c.execute('INSERT INTO users (email, username, password) VALUES (?, ?, ?)',
                     (email, username, password))
            conn.commit()
            conn.close()
            flash('Account created successfully! Please login.')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            conn.close()
            flash('Email already exists')
        
    return render_template('signup.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/add_to_cart/<int:product_id>')
def add_to_cart(product_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if 'cart' not in session:
        session['cart'] = {}
    
    cart = session['cart']
    if str(product_id) in cart:
        cart[str(product_id)] += 1
    else:
        cart[str(product_id)] = 1
    
    session['cart'] = cart
    return 'Product added to cart', 200

@app.route('/cart')
def cart():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if 'cart' not in session:
        session['cart'] = {}
    
    cart_items = []
    total = 0
    
    if session['cart']:
        conn = sqlite3.connect('ecommerce.db')
        c = conn.cursor()
        for product_id, quantity in session['cart'].items():
            c.execute('SELECT * FROM products WHERE id = ?', (product_id,))
            product = c.fetchone()
            if product:
                subtotal = product[3] * quantity
                cart_items.append({
                    'id': product[0],
                    'name': product[1],
                    'price': product[3],
                    'quantity': quantity,
                    'subtotal': subtotal
                })
                total += subtotal
        conn.close()
    
    return render_template('cart.html', cart_items=cart_items, total=total)

@app.route('/update_cart', methods=['POST'])
def update_cart():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    product_id = request.form['product_id']
    action = request.form['action']
    
    cart = session.get('cart', {})
    
    if action == 'increase':
        cart[product_id] = cart.get(product_id, 0) + 1
    elif action == 'decrease':
        if cart.get(product_id, 0) > 1:
            cart[product_id] -= 1
        else:
            cart.pop(product_id, None)
    
    session['cart'] = cart
    return redirect(url_for('cart'))

@app.route('/checkout', methods=['GET', 'POST'])
def checkout():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        try:
            conn = sqlite3.connect('ecommerce.db')
            c = conn.cursor()

            # 1. Save address if requested
            if 'save_address' in request.form:
                c.execute('''
                    INSERT INTO user_addresses 
                    (user_id, full_name, street, city, state, zip_code, phone)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    session['user_id'],
                    request.form['full_name'],
                    request.form['street'],
                    request.form['city'],
                    request.form['state'],
                    request.form['zip_code'],
                    request.form['phone']
                ))

            # 2. Create shipping address string
            shipping_address = (
                f"{request.form['full_name']}, {request.form['street']}, "
                f"{request.form['city']}, {request.form['state']} {request.form['zip_code']}"
            )

            # 3. Calculate total (same as before)
            total = 0
            cart_items = []
            for product_id, quantity in session['cart'].items():
                c.execute('SELECT price FROM products WHERE id = ?', (product_id,))
                price = c.fetchone()[0]
                total += price * quantity

            # 4. Create order with address
            c.execute('''
                INSERT INTO orders 
                (user_id, total_amount, status, shipping_address)
                VALUES (?, ?, ?, ?)
            ''', (session['user_id'], total, 'pending', shipping_address))
            order_id = c.lastrowid

            # 5. Add order items (same as before)
            for product_id, quantity in session['cart'].items():
                c.execute('SELECT price FROM products WHERE id = ?', (product_id,))
                price = c.fetchone()[0]
                c.execute('''
                    INSERT INTO order_items 
                    (order_id, product_id, quantity, price_at_time)
                    VALUES (?, ?, ?, ?)
                ''', (order_id, product_id, quantity, price))

            conn.commit()
            session.pop('cart', None)
            return redirect(url_for('order_confirmation', order_id=order_id))

        except Exception as e:
            conn.rollback()
            flash(f"Checkout error: {str(e)}")
            return redirect(url_for('checkout'))
        finally:
            conn.close()

    return render_template('checkout.html')

@app.route('/order_confirmation/<int:order_id>')
def order_confirmation(order_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    try:
        conn = sqlite3.connect('ecommerce.db')
        c = conn.cursor()

        c.execute('''
            SELECT o.id, o.total_amount, o.status, o.shipping_address, o.created_at,
                   GROUP_CONCAT(p.name || ' (x' || oi.quantity || ')') as items
            FROM orders o
            JOIN order_items oi ON o.id = oi.order_id
            JOIN products p ON oi.product_id = p.id
            WHERE o.id = ? AND o.user_id = ?
            GROUP BY o.id
        ''', (order_id, session['user_id']))

        order = c.fetchone()
        if not order:
            flash('Order not found')
            return redirect(url_for('home'))

        return render_template('order_confirmation.html', 
                            order_id=order[0],
                            total=order[1],
                            status=order[2],
                            shipping_address=order[3],
                            order_date=order[4],
                            items=order[5])

    except Exception as e:
        print(f"Confirmation error: {str(e)}")
        flash('Error loading order details')
        return redirect(url_for('home'))
    finally:
        conn.close()

@app.route('/orders')
def orders():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = sqlite3.connect('ecommerce.db')
    c = conn.cursor()
    
    # Fetch orders for the logged-in user
    c.execute('''
        SELECT o.id, o.total_amount, o.status, o.created_at,
               GROUP_CONCAT(p.name || ' (x' || oi.quantity || ')') as items
        FROM orders o
        JOIN order_items oi ON o.id = oi.order_id
        JOIN products p ON oi.product_id = p.id
        WHERE o.user_id = ?
        GROUP BY o.id
        ORDER BY o.created_at DESC
    ''', (session['user_id'],))
    
    orders = c.fetchall()
    conn.close()
    
    # Update the status of each order if 24 hours have passed
    for order in orders:
        update_order_status(order[0], session['user_id'])
    
    return render_template('orders.html', orders=orders)

@app.route('/cancel_order/<int:order_id>')
def cancel_order(order_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = sqlite3.connect('ecommerce.db')
    c = conn.cursor()
    
    c.execute('''
        SELECT created_at 
        FROM orders 
        WHERE id = ? AND user_id = ?
    ''', (order_id, session['user_id']))
    
    order = c.fetchone()
    
    if order:
        order_date = datetime.strptime(order[0], '%Y-%m-%d %H:%M:%S')
        if datetime.now() - order_date < timedelta(hours=24):
            c.execute('UPDATE orders SET status = ? WHERE id = ?', 
                     ('cancelled', order_id))
            conn.commit()
            flash('Order canceled, your money will be refunded.')
        else:
            flash('Product has been shipped, cannot cancel.')
    
    conn.close()
    return redirect(url_for('orders'))


def update_order_status(order_id, user_id):
    """Update order status to 'delivered' if 24 hours have passed since creation"""
    conn = sqlite3.connect('ecommerce.db')
    c = conn.cursor()
    
    # Fetch the order creation time and current status
    c.execute('''
        SELECT created_at, status
        FROM orders
        WHERE id = ? AND user_id = ?
    ''', (order_id, user_id))
    
    order = c.fetchone()
    if not order:
        return False  # Order not found
    
    created_at_str, status = order
    created_at = datetime.strptime(created_at_str, '%Y-%m-%d %H:%M:%S')
    
    # If 24 hours have passed and status is still 'pending', update to 'delivered'
    if status == 'pending' and datetime.now() - created_at >= timedelta(hours=24):
        c.execute('''
            UPDATE orders
            SET status = 'delivered'
            WHERE id = ? AND user_id = ?
        ''', (order_id, user_id))
        conn.commit()
        conn.close()
        return True  # Status updated
    
    conn.close()
    return False  # Status not updated

if __name__ == '__main__':
    app.run(debug=True)