from flask import Flask, render_template, request, redirect, url_for, flash, session
import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # 用於閃存消息和 session

# 連接 MySQL 資料庫
def connect_db():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="Ab921218",
        database="user_registration"
    )

# 註冊頁面
@app.route("/", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        password = request.form.get("password")
        
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')

        db = connect_db()
        cursor = db.cursor()

        try:
            cursor.execute("INSERT INTO users (name, email, password) VALUES (%s, %s, %s)", (name, email, hashed_password))
            db.commit()
            flash("You have successfully registered!", "success")
            return redirect(url_for('login'))
        except mysql.connector.IntegrityError as e:
            if "unique_name" in str(e):
                flash("Name already exists. Please choose a different name.", "danger")
            elif "users.email" in str(e):
                flash("Email already exists. Please try again.", "danger")
        finally:
            cursor.close()
            db.close()

    return render_template("register.html")


# 登入頁面
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        name = request.form.get("name")
        password = request.form.get("password")

        db = connect_db()
        cursor = db.cursor(dictionary=True)

        cursor.execute("SELECT * FROM users WHERE name = %s", (name,))
        user = cursor.fetchone()
        
        if user:
            print(f"Stored password hash: {user['password']}")
            print(f"User input password: {password}")

        cursor.close()
        db.close()

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["user_name"] = user["name"]
            session["user_email"] = user["email"]
            flash("Login successful!", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid credentials. Please try again.", "danger")

    return render_template("login.html")

# Dashboard 頁面
@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        flash("Please login to access the dashboard.", "danger")
        return redirect(url_for("login"))

    return render_template("dashboard.html", user_name=session["user_name"], user_email=session["user_email"])

# 登出功能
@app.route("/logout")
def logout():
    session.clear()
    flash("Log out successfully", "success")
    return redirect(url_for("login"))

if __name__ == "__main__":
    app.run(debug=True)
