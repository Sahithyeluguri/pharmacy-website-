from flask import Flask, render_template, request, redirect, flash, url_for, session
import mysql.connector
from mysql.connector import Error
from datetime import datetime
from flask import Flask, jsonify, render_template
from flask_sqlalchemy import SQLAlchemy
import pandas as pd
from statsmodels.tsa.arima.model import ARIMA
from sqlalchemy import create_engine


app = Flask(__name__)
def get_db_connection():
    try:
        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password="1857",
            database="medipharm"
        )
        return conn
    except Error as e:
        print("Error connecting to the database:", e)
        return None

def close_db_connection(cursor, conn):
    if cursor:
        cursor.close()
    if conn:
        conn.close()
app.secret_key = 'your_secret_key'  # Replace with a secure key
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+mysqlconnector://root:1857@localhost/medipharm'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Define the Orders model (adjust to match your table schema)
class Orders(db.Model):
    __tablename__ = 'orders'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)  # 'name' column for product names
    quantity = db.Column(db.Integer, nullable=False)
    date = db.Column(db.DateTime, nullable=False)

    def __repr__(self):
        return f'<Orders {self.id}>'

# MySQL Configuration


# Signup Route
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        phone_number = request.form['phone_number']
        address = request.form['address']

        if not username or not password or not phone_number or not address:
            flash("All fields are required.")
            return redirect(url_for('signup'))

        try:
            conn = get_db_connection()
            if conn is None:
                flash("Database connection error.")
                return redirect(url_for('signup'))

            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO Customer (username, password, phone_number, address) VALUES (%s, %s, %s, %s)",
                (username, password, phone_number, address)
            )
            conn.commit()

            flash("Account created successfully! Please log in.")
            return redirect(url_for('login'))
        except Error as e:
            flash("Error creating account.")
            print(e)
        finally:
            close_db_connection(cursor, conn)

    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'username' in session:
        flash("You are already logged in.")
        return redirect(url_for('home'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if not username or not password:
            flash("Username and password are required.")
            return redirect(url_for('login'))

        # Check if the user is the admin
        if username == 'admin' and password == 'admin':
            session['username'] = 'admin'
            session['is_admin'] = 1  # Set admin privileges in the session
            flash("Logged in as admin.")
            return redirect(url_for('admin_dashboard'))

        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM Customer WHERE username = %s AND password = %s", (username, password))
            user = cursor.fetchone()

            if user:
                session['username'] = username
                session['customer_id'] = user['customer_id']  # Store customer_id in session
                session['is_admin'] = user.get('is_admin', 0)  # Store admin status in session (default to 0)
                flash("Logged in successfully!")
                return redirect(url_for('home'))
            else:
                flash("Invalid username or password.")
        except Error as e:
            flash("Error during login.")
            print(e)
        finally:
            close_db_connection(cursor, conn)

    return render_template('login.html')


# Home Route
@app.route('/')
def home():
    return render_template('home.html')

# Products Route
@app.route('/products', methods=['GET', 'POST'])
def products():
    if 'username' not in session:
        flash("Please log in to add products to the cart.")
        return redirect(url_for('login'))
    
    customer_id = session.get('customer_id')
    
    if request.method == 'POST':
        product_id = request.form['product_id']
        quantity = 1  # Default to adding 1 unit
        
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Check if product is already in the cart
            cursor.execute("SELECT * FROM Cart WHERE customer_id = %s AND product_id = %s", (customer_id, product_id))
            existing_item = cursor.fetchone()
            
            if existing_item:
                # Update quantity
                cursor.execute(
                    "UPDATE Cart SET quantity = quantity + %s WHERE customer_id = %s AND product_id = %s",
                    (quantity, customer_id, product_id)
                )
            else:
                # Add new product to cart
                cursor.execute(
                    "INSERT INTO Cart (customer_id, product_id, quantity) VALUES (%s, %s, %s)",
                    (customer_id, product_id, quantity)
                )
            conn.commit()
            flash("Product added to cart.")
        except Error as e:
            flash("Error adding product to cart.")
            print(e)
        finally:
            close_db_connection(cursor, conn)
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM Product")  # Fetch all products
        products = cursor.fetchall()
    except Error as e:
        flash("Error fetching products.")
        print(e)
        products = []
    finally:
        close_db_connection(cursor, conn)
    
    return render_template('products.html', products=products)

# Cart Route
@app.route('/cart', methods=['GET', 'POST'])
def cart():
    if 'username' not in session:
        flash("Please log in to view your cart.")
        return redirect(url_for('login'))

    customer_id = session.get('customer_id')
    alert_message = None

    if request.method == 'POST':
        action = request.form.get('action', None)
        product_id = request.form['product_id']

        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)

            # Check stock before updating
            if action == 'update':
                quantity = int(request.form['quantity'])
                cursor.execute("SELECT quantity FROM Product WHERE product_id = %s", (product_id,))
                available_quantity = cursor.fetchone()['quantity']

                if quantity > available_quantity:
                    alert_message = f"Insufficient stock for this product. Only {available_quantity} units available."
                else:
                    cursor.execute(
                        "UPDATE Cart SET quantity = %s WHERE customer_id = %s AND product_id = %s",
                        (quantity, customer_id, product_id)
                    )
                    conn.commit()
                    flash("Cart updated.")
            elif action == 'remove':
                cursor.execute("DELETE FROM Cart WHERE customer_id = %s AND product_id = %s", (customer_id, product_id))
                conn.commit()
                flash("Product removed from cart.")
        except Error as e:
            flash("Error updating cart.")
            print(e)
        finally:
            close_db_connection(cursor, conn)

    # Fetch updated cart items
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT c.product_id, p.name, c.quantity AS cart_quantity, p.quantity AS available_quantity,
                   p.price, (c.quantity * p.price) AS total
            FROM Cart c
            INNER JOIN Product p ON c.product_id = p.product_id
            WHERE c.customer_id = %s
        """, (customer_id,))
        cart_items = cursor.fetchall()
    except Error as e:
        flash("Error fetching cart items.")
        print(e)
        cart_items = []
    finally:
        close_db_connection(cursor, conn)

    return render_template('cart.html', cart_items=cart_items, alert_message=alert_message)
@app.route('/checkout', methods=['GET', 'POST'])
def checkout():
    if 'username' not in session:
        flash("Please log in to complete the checkout process.")
        return redirect(url_for('login'))

    customer_id = session.get('customer_id')

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Fetch cart items for the logged-in customer, including the related_disease (disease from product)
        cursor.execute("""
            SELECT c.product_id, p.name, c.quantity AS cart_quantity, p.price, p.quantity AS available_quantity,
                   p.disease AS Related_Disease, (c.quantity * p.price) AS total
            FROM Cart c
            INNER JOIN Product p ON c.product_id = p.product_id
            WHERE c.customer_id = %s
        """, (customer_id,))
        cart_items = cursor.fetchall()

        # Calculate total amount
        total_amount = sum(item['total'] for item in cart_items)

        # Check for quantity issues
        for item in cart_items:
            if item['cart_quantity'] > item['available_quantity']:
                flash(f"Insufficient stock for {item['name']}. Only {item['available_quantity']} units available.")
                return redirect(url_for('cart'))

        if request.method == 'POST':
            # Handle order placement
            payment_method = request.form.get('payment_method')

            if payment_method != 'Pay on Delivery':
                flash("Invalid payment method. Only 'Pay on Delivery' is available.")
                return redirect(url_for('checkout'))

            # Insert into orders table and reduce product quantity
            for item in cart_items:
                cursor.execute("""
                    INSERT INTO Orders (customer_id, product_id, quantity, price, order_date, name, Related_Disease)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (customer_id, item['product_id'], item['cart_quantity'], item['price'], datetime.now(), item['name'], item['Related_Disease']))

                # Deduct quantity from product table
                cursor.execute("""
                    UPDATE Product
                    SET quantity = quantity - %s
                    WHERE product_id = %s
                """, (item['cart_quantity'], item['product_id']))

            # Clear cart
            cursor.execute("DELETE FROM Cart WHERE customer_id = %s", (customer_id,))
            conn.commit()

            flash("Order placed successfully! Thank you for shopping with us.")
            return redirect(url_for('home'))

        return render_template('checkout.html', cart_items=cart_items, total_amount=total_amount)
    except Error as e:
        flash("Error during checkout.")
        print(e)
        return redirect(url_for('home'))
    finally:
        close_db_connection(cursor, conn)

@app.route('/admin_dashboard', methods=['GET', 'POST'])
def admin_dashboard():
    if 'username' not in session or session.get('is_admin') != 1:
        flash("You need to log in as admin.")
        return redirect(url_for('login'))

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Fetch counts for the dashboard
        cursor.execute("SELECT COUNT(*) AS customer_count FROM Customer")
        customer_count = cursor.fetchone()['customer_count']

        cursor.execute("SELECT COUNT(*) AS product_count FROM Product")
        product_count = cursor.fetchone()['product_count']

        cursor.execute("SELECT COUNT(*) AS order_count FROM Orders")
        order_count = cursor.fetchone()['order_count']

        # Fetch customers, orders, and products for the dashboard
        cursor.execute("SELECT * FROM Customer")
        customers = cursor.fetchall()

        cursor.execute("SELECT * FROM Orders")
        orders = cursor.fetchall()

        cursor.execute("SELECT * FROM Product")
        products = cursor.fetchall()
    except Error as e:
        flash("Error fetching data for admin dashboard.")
        print(e)
        customers = orders = products = []
        customer_count = product_count = order_count = 0
    finally:
        close_db_connection(cursor, conn)

    if request.method == 'POST':
        # If the Forecast button is clicked
        try:
            train_arima_model()  # Call the ARIMA model to generate forecasts
            flash("Forecast generated successfully!")
            return redirect(url_for('forecast_results'))  # Redirect to forecast results page
        except Exception as e:
            flash(f"Error generating forecast: {e}")
            return redirect(url_for('admin_dashboard'))

    return render_template(
        'admin_dashboard.html',
        customers=customers,
        orders=orders,
        products=products,
        customer_count=customer_count,
        product_count=product_count,
        order_count=order_count
    )
@app.route('/admin/orders', methods=['GET', 'POST'])
def admin_orders():
    if 'username' not in session or session.get('is_admin') != 1:
        flash("You need to log in as admin.")
        return redirect(url_for('login'))
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT o.order_id, o.customer_id, o.product_id, o.quantity, o.price, o.order_date, 
                   c.username, c.address, p.name
            FROM Orders o
            INNER JOIN customer c ON o.customer_id = c.customer_id
            INNER JOIN Product p ON o.product_id = p.product_id
        """)
        orders = cursor.fetchall()
    except Error as e:
        flash("Error fetching orders.")
        print(e)
        orders = []
    finally:
        close_db_connection(cursor, conn)

    return render_template('admin_orders.html', orders=orders)

@app.route('/admin/products', methods=['GET', 'POST'])
def admin_products():
    """Admin interface for managing products."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        if request.method == 'POST':
            action = request.form.get('action')

            # Add Product
            if action == 'add':
                name = request.form.get('name')
                price = request.form.get('price')
                quantity = request.form.get('quantity')

                if not name or not price or not quantity:
                    flash("All fields are required to add a product.")
                    return redirect(url_for('admin_products'))

                try:
                    cursor.execute("""
                        INSERT INTO Product (name, price, quantity)
                        VALUES (%s, %s, %s)
                    """, (name, price, quantity))
                    conn.commit()
                    flash("Product added successfully!")
                except Error as e:
                    flash("Error adding product.")
                    print(e)

            # Update Product
            elif action == 'update':
                product_id = request.form.get('product_id')
                name = request.form.get('name')
                price = request.form.get('price')
                quantity = request.form.get('quantity')

                if not product_id or not name or not price or not quantity:
                    flash("All fields are required to update a product.")
                    return redirect(url_for('admin_products'))

                try:
                    cursor.execute("""
                        UPDATE Product
                        SET name = %s, price = %s, quantity = %s
                        WHERE product_id = %s
                    """, (name, price, quantity, product_id))
                    conn.commit()
                    flash("Product updated successfully!")
                except Error as e:
                    flash("Error updating product.")
                    print(e)

            # Delete Product
            elif action == 'delete':
                product_id = request.form.get('product_id')

                if not product_id:
                    flash("Product ID is required to delete a product.")
                    return redirect(url_for('admin_products'))

                try:
                    cursor.execute("DELETE FROM Product WHERE product_id = %s", (product_id,))
                    conn.commit()
                    flash("Product deleted successfully!")
                except Error as e:
                    flash("Error deleting product.")
                    print(e)

        # Fetch updated product list
        cursor.execute("SELECT * FROM Product")
        products = cursor.fetchall()

    except Error as e:
        flash("Error fetching products.")
        print(e)
        products = []
    finally:
        close_db_connection(cursor, conn)

    return render_template('admin_products.html', products=products)
@app.route('/forecast', methods=['GET'])
def forecast():
    try:
        # Fetch data from the orders table
        conn = get_db_connection()
        cursor = conn.cursor()

        # Fetch orders data
        orders_data = db.session.query(Orders.name, db.func.sum(Orders.quantity).label('total_quantity')).group_by(Orders.name).all()

        # Convert the orders data into a DataFrame
        orders_df = pd.DataFrame(orders_data, columns=['name', 'total_quantity'])

        # Call the ARIMA training function
        train_arima_model()

        # Combine the orders data with the forecast (from forecast_sales.csv)
        forecast_df = pd.read_csv('forecast_sales.csv')

        # Merge the orders and forecast data based on 'name' (product_name) 
        merged_df = pd.merge(orders_df, forecast_df, how='left', on='name')

        # Group the results by product name and sum the predicted quantities
        grouped_df = merged_df.groupby('name').agg({
            'forecast_date': 'first',
            'total_quantity': 'first',
            'predicted_quantity': 'sum'
        }).reset_index()

        # Render the results to billing.html
        return render_template('billing.html', forecasts=grouped_df.to_dict(orient='records'))
    
    except Exception as e:
        # Handle any exceptions and return an error response
        return jsonify({"error": f"Error occurred: {str(e)}"}), 500

    finally:
        # Close the database connection and cursor if they were opened
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.route('/logout')
def logout():
    session.pop('username', None)
    session.pop('customer_id', None)
    session.pop('is_admin', None)
    flash("You have been logged out.")
    return redirect(url_for('home'))

def train_arima_model():
    try:
        # Load the sales data from the CSV file (forecast data)
        sales_data = pd.read_csv("medical_sales1.csv")

        # Check if the 'Date' column exists
        if 'Date' not in sales_data.columns:
            raise ValueError("The 'Date' column is missing from medical_sales.csv.")

        # Convert the 'Date' column to datetime
        sales_data['Date'] = pd.to_datetime(sales_data['Date'], errors='coerce')

        # Check for any invalid date entries
        if sales_data['Date'].isnull().any():
            raise ValueError("There are invalid date values in the 'Date' column.")

        # Sort and prepare the data for training
        sales_data = sales_data.sort_values(by='Date')
        sales_data['month_year'] = sales_data['Date'].dt.to_period('M')

        # Aggregate quantity data by month and product
        monthly_sales = sales_data.groupby(['month_year', 'product_name'])['quantity'].sum().reset_index()
        pivot_sales = monthly_sales.pivot(index='month_year', columns='product_name', values='quantity').fillna(0)

        # Forecast the next 12 months for each product
        forecast_horizon = 12
        forecast_results = {}

        for product_name in pivot_sales.columns:
            series = pivot_sales[product_name]
            try:
                model = ARIMA(series, order=(1, 1, 1))
                model_fit = model.fit()
                future_forecast = model_fit.forecast(steps=forecast_horizon)
                forecast_results[product_name] = future_forecast
            except Exception as e:
                print(f"Error training ARIMA for {product_name}: {e}")
                forecast_results[product_name] = [0] * forecast_horizon

        # Generate forecast data and save it
        last_date = pivot_sales.index[-1].to_timestamp()
        forecast_dates = pd.date_range(start=last_date + pd.offsets.MonthBegin(1), periods=forecast_horizon, freq='MS')
        forecast_data = [
            {
                'forecast_date': forecast_dates[i].strftime('%Y-%m-%d'),
                'name': product_name,
                'predicted_quantity': forecast
            }
            for product_name, forecasts in forecast_results.items()
            for i, forecast in enumerate(forecasts)
        ]
        forecast_sales_df = pd.DataFrame(forecast_data)
        forecast_sales_df.to_csv('forecast_sales.csv', index=False)
        print("ARIMA training and forecast complete. Data saved to forecast_sales.csv.")

    except Exception as e:
        print(f"Error training ARIMA model: {e}")
        raise e


# Run the App
if __name__ == '__main__':
    app.run(debug=True)
