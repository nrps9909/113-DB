from flask import Flask, render_template, request, redirect, url_for, flash, session
from db import connect_db  # Import connect_db from db.py
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from join import join_bp  # Import Blueprint from join.py
import mysql.connector

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Used for flash messages and session

# Register Blueprint
app.register_blueprint(join_bp)

# Registration page
@app.route("/", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("name")  # Changed `name` to `username`
        email = request.form.get("email")
        password = request.form.get("password")
        
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')

        db = connect_db()
        cursor = db.cursor()

        # Check if username or email already exists
        cursor.execute("SELECT * FROM users WHERE username = %s OR email = %s", (username, email))
        existing_user = cursor.fetchone()

        if existing_user:
            if existing_user[1] == username:
                flash("Username already exists. Please choose another username.", "danger")
            elif existing_user[2] == email:
                flash("Email already exists. Please try another one.", "danger")
        else:
            try:
                # Insert new user if no duplicates
                cursor.execute("INSERT INTO users (username, email, password_hash) VALUES (%s, %s, %s)", (username, email, hashed_password))
                db.commit()
                flash("Registration successful! Please log in.", "success")
                return redirect(url_for('login'))
            except mysql.connector.Error as e:
                flash(f"An error occurred: {str(e)}", "danger")
            finally:
                cursor.close()
                db.close()

    return render_template("register.html")

# Login page
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("name")
        password = request.form.get("password")

        db = connect_db()
        cursor = db.cursor(dictionary=True)

        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()
        cursor.close()
        db.close()

        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["user_email"] = user["email"]
            flash("Login successful!", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("Incorrect username or password. Please try again.", "danger")

    return render_template("login.html")

# Dashboard page
@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        flash("Please log in to access the dashboard.", "danger")
        return redirect(url_for("login"))

    return render_template("dashboard.html", username=session.get("username"), user_email=session.get("user_email"))

# Route for creating a new order
@app.route("/create_order", methods=["GET", "POST"])
def create_order():
    if "user_id" not in session:
        flash("Please log in to create an order.", "danger")
        return redirect(url_for("login"))
    
    if request.method == "POST":
        product_id = request.form.get("product_id")
        amount = request.form.get("amount")
        order_date = request.form.get("order_date")
        user_id = session["user_id"]

        db = connect_db()
        cursor = db.cursor()

        try:
            cursor.execute("INSERT INTO orders (user_id, product_id, order_date, amount) VALUES (%s, %s, %s, %s)",
                           (user_id, product_id, order_date, amount))
            db.commit()
            flash("Order created successfully!", "success")
            return redirect(url_for("dashboard"))
        except Exception as e:
            flash(f"An error occurred: {str(e)}", "danger")
        finally:
            cursor.close()
            db.close()
    
    # Fetch product list for selection
    db = connect_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM products")
    products = cursor.fetchall()
    cursor.close()
    db.close()
    return render_template("create_order.html", products=products)

# Route for updating user email
@app.route("/update_email", methods=["GET", "POST"])
def update_email():
    if "user_id" not in session:
        flash("Please log in to update your email.", "danger")
        return redirect(url_for("login"))
    
    if request.method == "POST":
        new_email = request.form.get("email")

        db = connect_db()
        cursor = db.cursor()
        
        try:
            cursor.execute("UPDATE users SET email = %s WHERE id = %s", (new_email, session["user_id"]))
            db.commit()
            session["user_email"] = new_email
            flash("Email updated successfully!", "success")
        except mysql.connector.Error as e:
            flash(f"An error occurred: {str(e)}", "danger")
        finally:
            cursor.close()
            db.close()
    
    return render_template("update_email.html", current_email=session["user_email"])

# Route for deleting user account
@app.route("/delete_account", methods=["POST"])
def delete_account():
    if "user_id" not in session:
        flash("Please log in to delete your account.", "danger")
        return redirect(url_for("login"))

    db = connect_db()
    cursor = db.cursor()
    
    try:
        # Delete user's orders first due to foreign key constraints
        cursor.execute("DELETE FROM orders WHERE user_id = %s", (session["user_id"],))
        cursor.execute("DELETE FROM users WHERE id = %s", (session["user_id"],))
        db.commit()
        session.clear()
        flash("Account deleted successfully.", "success")
        return redirect(url_for("register"))
    except mysql.connector.Error as e:
        flash(f"An error occurred: {str(e)}", "danger")
    finally:
        cursor.close()
        db.close()

# Route for updating order amount
@app.route("/update_order/<int:order_id>", methods=["GET", "POST"])
def update_order(order_id):
    if "user_id" not in session:
        flash("Please log in to update your order.", "danger")
        return redirect(url_for("login"))
    
    db = connect_db()
    cursor = db.cursor(dictionary=True)

    if request.method == "POST":
        new_amount = request.form.get("amount")
        
        try:
            cursor.execute("UPDATE orders SET amount = %s WHERE id = %s AND user_id = %s", (new_amount, order_id, session["user_id"]))
            db.commit()
            flash("Order amount updated successfully!", "success")
            return redirect(url_for("dashboard"))
        except mysql.connector.Error as e:
            flash(f"An error occurred: {str(e)}", "danger")
        finally:
            cursor.close()
            db.close()

    # Fetch the existing order amount for display
    cursor.execute("SELECT * FROM orders WHERE id = %s AND user_id = %s", (order_id, session["user_id"]))
    order = cursor.fetchone()
    cursor.close()
    db.close()
    return render_template("update_order.html", order=order)

# Route for deleting an order
@app.route("/delete_order/<int:order_id>", methods=["POST"])
def delete_order(order_id):
    if "user_id" not in session:
        flash("Please log in to delete an order.", "danger")
        return redirect(url_for("login"))

    db = connect_db()
    cursor = db.cursor()

    try:
        cursor.execute("DELETE FROM orders WHERE id = %s AND user_id = %s", (order_id, session["user_id"]))
        db.commit()
        flash("Order deleted successfully!", "success")
    except mysql.connector.Error as e:
        flash(f"An error occurred: {str(e)}", "danger")
    finally:
        cursor.close()
        db.close()
    
    return redirect(url_for("dashboard"))

# Logout function
@app.route("/logout")
def logout():
    session.clear()
    flash("You have successfully logged out.", "success")
    return redirect(url_for("login"))

if __name__ == "__main__":
    app.run(debug=True)
