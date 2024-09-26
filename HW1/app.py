from flask import Flask, render_template, request, redirect
import mysql.connector

app = Flask(__name__)

# Connect to MySQL
def connect_db():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="Ab921218",
        database="testdb"
    )

# Main page with posts, add post, and delete post
@app.route("/", methods=["GET", "POST"])
def index():
    db = connect_db()
    cursor = db.cursor()

    if request.method == "POST":
        # Add new post
        post_content = request.form["post"]
        cursor.execute("INSERT INTO example_table (post) VALUES (%s)", (post_content,))
        db.commit()

    # Fetch all posts to display
    cursor.execute("SELECT * FROM example_table")
    posts = cursor.fetchall()
    
    cursor.close()
    db.close()

    return render_template("index.html", posts=posts)

# Route for deleting a post
@app.route("/delete_post/<int:post_id>")
def delete_post(post_id):
    db = connect_db()
    cursor = db.cursor()
    cursor.execute("DELETE FROM example_table WHERE id = %s", (post_id,))
    db.commit()
    cursor.close()
    db.close()
    return redirect("/")

if __name__ == "__main__":
    app.run(debug=True)
