from flask import Flask, render_template, request, redirect, url_for, session, flash
import cv2
import face_recognition
import numpy as np
import pickle
from db_config import get_connection
import os

app = Flask(__name__)
app.secret_key = "supersecretkey"  # Replace with a real secret in production

# Face encoding helper
def get_face_encoding(image):
    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    boxes = face_recognition.face_locations(rgb)
    encodings = face_recognition.face_encodings(rgb, boxes)
    return encodings[0] if encodings else None

# Route: Home
@app.route('/')
def home():
    return redirect(url_for('dashboard'))

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')
# Route: Register
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        username = request.form['username']
        password = request.form['password']

        cap = cv2.VideoCapture(0)
        ret, frame = cap.read()
        cap.release()

        encoding = get_face_encoding(frame)
        if encoding is None:
            flash("Face not detected. Try again.")
            return redirect(url_for('register'))

        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO users (name, username, password, face_encoding) VALUES (%s, %s, %s, %s)",
                           (name, username, password, encoding.tobytes()))
            conn.commit()
        except:
            flash("Voter ID already exists.")
            return redirect(url_for('register'))
        finally:
            cursor.close()
            conn.close()

        flash("Registered successfully!")
        return redirect(url_for('login'))

    return render_template('register.html')

# Route: Login with Face
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        cap = cv2.VideoCapture(0)
        ret, frame = cap.read()
        cap.release()

        encoding = get_face_encoding(frame)
        if encoding is None:
            flash("Face not detected.")
            return redirect(url_for('login'))

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, face_encoding FROM users")
        users = cursor.fetchall()
        for user_id, face_data in users:
            db_encoding = np.frombuffer(face_data, dtype=np.float64)
            matches = face_recognition.compare_faces([db_encoding], encoding)
            if matches[0]:
                session['user_id'] = user_id
                return redirect(url_for('vote'))

        flash("Face not recognized.")
        return redirect(url_for('login'))

    return render_template('login.html')

# Route: Vote
@app.route('/vote', methods=['GET', 'POST'])
def vote():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT has_voted FROM users WHERE id = %s", (user_id,))
    has_voted = cursor.fetchone()[0]

    if has_voted:
        flash("You have already voted.")
        return redirect(url_for('login'))

    if request.method == 'POST':
        candidate_id = request.form['candidate']
        cursor.execute("INSERT INTO votes (user_id, candidate_id) VALUES (%s, %s)", (user_id, candidate_id))
        cursor.execute("UPDATE users SET has_voted = TRUE WHERE id = %s", (user_id,))
        conn.commit()
        flash("Vote cast successfully!")
        return redirect(url_for('dashboard'))

    cursor.execute("SELECT id, name FROM candidates")
    candidates = cursor.fetchall()
    return render_template('vote.html', candidates=candidates)

# Route: Results
@app.route('/results')
def results():
    conn=get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT c.name, COUNT(v.id) as vote_count FROM candidates c LEFT JOIN votes v ON c.id = v.candidate_id GROUP BY c.id")
    results = cursor.fetchall()
    return render_template("results.html", results=results)

# Logout
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    app.run(debug=True)
