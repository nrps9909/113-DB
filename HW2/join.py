from flask import Blueprint, render_template, request, flash, redirect, url_for, session
from db import connect_db  # Import connect_db from db.py

join_bp = Blueprint('join', __name__)

@join_bp.route('/join')
def join():
    # 確保用戶已登入
    if 'user_id' not in session:
        flash("Please log in to view orders.", "danger")
        return redirect(url_for("login"))

    db = connect_db()
    cursor = db.cursor(dictionary=True)
    query = """
        SELECT users.username, users.email, orders.order_date, orders.amount, products.product_name,
               orders.id AS order_id, orders.user_id
        FROM users
        JOIN orders ON users.id = orders.user_id
        JOIN products ON orders.product_id = products.id
    """
    cursor.execute(query)
    results = cursor.fetchall()
    cursor.close()
    db.close()
    return render_template('join.html', results=results)
