import os
import re
import uuid
from datetime import datetime

from flask import (Flask, render_template, request, redirect,
                   url_for, session, flash, send_from_directory)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

from database import get_connection, create_tables

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-key")
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50 MB upload limit

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")

ALLOWED_FILES = {
    "profile_picture": ["jpg", "jpeg", "png"],
    "resume": ["pdf"],
    "certificate": ["pdf", "jpg", "jpeg", "png"],
    "audio": ["mp3", "wav"],
    "video": ["mp4", "webm"],
}

OPTIONS = {
    "genders": ["Male", "Female", "Other"],
    "countries": ["India", "USA", "UK"],
    "states": ["Tamil Nadu", "Kerala", "Karnataka", "Maharashtra", "Delhi", "Other"],
    "departments": ["Artificial Intelligence and Data Science","Computer Science", "Information Technology", "Electronics", "Mechanical", "Civil"],
    "years": ["1st Year", "2nd Year", "3rd Year", "4th Year"],
    "skills": ["Python", "HTML", "CSS", "JavaScript", "Flask", "MySQL"],
    "levels": ["Beginner", "Intermediate", "Advanced"],
}

FORM_FIELDS = [
    "full_name", "email", "phone", "date_of_birth", "gender", "country", "state",
    "address", "department", "year_of_study", "skill_level", "portfolio_url",
    "experience", "preferred_contact_time",
]


# ---------- Helper functions ----------

def run_query(sql, values=(), fetch=None):
    """fetch="one" -> one row, fetch="all" -> list of rows, otherwise save and return new id."""
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute(sql, values)

    if fetch == "one":
        result = cursor.fetchone()
    elif fetch == "all":
        result = cursor.fetchall()
    else:
        connection.commit()
        result = cursor.lastrowid

    cursor.close()
    connection.close()
    return result


def get_current_user():
    if "user_id" not in session:
        return None
    return run_query("SELECT * FROM users WHERE id = %s", (session["user_id"],), "one")


def read_form():
    data = {}
    for field in FORM_FIELDS:
        data[field] = request.form.get(field, "").strip()
    data["skills"] = ", ".join(request.form.getlist("skills"))
    return data


def check_form(data):
    """Returns an error message, or None if everything is fine."""
    required = ["full_name", "email", "phone", "date_of_birth", "gender", "country",
                "state", "address", "department", "year_of_study", "skill_level"]
    for field in required:
        if data[field] == "":
            return "Please fill in all required fields."

    if "@" not in data["email"]:
        return "Please enter a valid email."

    if not re.fullmatch(r"\d{10}", data["phone"]):
        return "Phone number must be 10 digits."

    try:
        datetime.strptime(data["date_of_birth"], "%Y-%m-%d")
    except ValueError:
        return "Please enter a valid date of birth."

    choices = {
        "gender": OPTIONS["genders"],
        "country": OPTIONS["countries"],
        "state": OPTIONS["states"],
        "department": OPTIONS["departments"],
        "year_of_study": OPTIONS["years"],
        "skill_level": OPTIONS["levels"],
    }
    for field, allowed in choices.items():
        if data[field] not in allowed:
            return "Invalid choice for " + field + "."

    if data["skills"]:
        for skill in data["skills"].split(", "):
            if skill not in OPTIONS["skills"]:
                return "Invalid skill selected."

    if data["portfolio_url"] and not data["portfolio_url"].startswith(("http://", "https://")):
        return "Portfolio URL must start with http:// or https://"

    if not data["experience"].isdigit() or int(data["experience"]) > 10:
        return "Experience must be a number from 0 to 10."

    if data["preferred_contact_time"] and not re.fullmatch(r"\d{2}:\d{2}", data["preferred_contact_time"]):
        return "Please enter a valid contact time."

    return None


def file_is_allowed(file, category):
    if "." not in file.filename:
        return False
    extension = file.filename.rsplit(".", 1)[1].lower()
    return extension in ALLOWED_FILES[category]


def save_file(file, category, user_id, username):
    """Saves the file in uploads/<username>/ and records it in the files table."""
    user_folder = os.path.join(UPLOAD_FOLDER, username)
    os.makedirs(user_folder, exist_ok=True)

    extension = file.filename.rsplit(".", 1)[1].lower()
    stored_filename = uuid.uuid4().hex + "." + extension
    file.save(os.path.join(user_folder, stored_filename))

    run_query(
        """INSERT INTO files
           (user_id, original_filename, stored_filename, file_path, file_type, category)
           VALUES (%s, %s, %s, %s, %s, %s)""",
        (user_id, secure_filename(file.filename), stored_filename,
         username + "/" + stored_filename, file.mimetype, category),
    )
    return stored_filename


# ---------- Routes ----------

@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("profile"))
    return redirect(url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html", options=OPTIONS, user={})

    data = read_form()
    data["username"] = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    picture = request.files.get("profile_picture")
    has_picture = picture is not None and picture.filename != ""

    error = check_form(data)
    if not error and not re.fullmatch(r"[A-Za-z0-9_]{3,20}", data["username"]):
        error = "Username must be 3-20 letters, numbers or underscores."
    if not error and len(password) < 6:
        error = "Password must be at least 6 characters."
    if not error and has_picture and not file_is_allowed(picture, "profile_picture"):
        error = "Profile picture must be JPG, JPEG or PNG."
    if not error:
        existing = run_query(
            "SELECT id FROM users WHERE username = %s OR email = %s",
            (data["username"], data["email"]), "one")
        if existing:
            error = "Username or email already exists."

    if error:
        flash(error)
        return render_template("register.html", options=OPTIONS, user=data)

    user_id = run_query(
        """INSERT INTO users
           (full_name, username, email, password, date_of_birth, phone, gender,
            country, state, address, department, year_of_study, skills,
            skill_level, portfolio_url, experience, preferred_contact_time)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        (data["full_name"], data["username"], data["email"], generate_password_hash(password),
         data["date_of_birth"], data["phone"], data["gender"], data["country"],
         data["state"], data["address"], data["department"], data["year_of_study"],
         data["skills"], data["skill_level"], data["portfolio_url"],
         int(data["experience"]), data["preferred_contact_time"]),
    )

    if has_picture:
        stored_filename = save_file(picture, "profile_picture", user_id, data["username"])
        run_query("UPDATE users SET profile_picture = %s WHERE id = %s", (stored_filename, user_id))

    flash("Registration successful. Please login.")
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")

    username_or_email = request.form.get("username_or_email", "").strip()
    password = request.form.get("password", "")

    user = run_query(
        "SELECT id, username, password FROM users WHERE username = %s OR email = %s",
        (username_or_email, username_or_email), "one")

    if user and check_password_hash(user["password"], password):
        session["user_id"] = user["id"]
        session["username"] = user["username"]
        return redirect(url_for("profile"))

    flash("Invalid username/email or password.")
    return render_template("login.html")


@app.route("/profile")
def profile():
    user = get_current_user()
    if user is None:
        return redirect(url_for("login"))

    files = run_query(
        "SELECT * FROM files WHERE user_id = %s ORDER BY uploaded_at DESC",
        (user["id"],), "all")
    return render_template("profile.html", user=user, files=files, categories=ALLOWED_FILES)


@app.route("/edit-profile", methods=["GET", "POST"])
def edit_profile():
    user = get_current_user()
    if user is None:
        return redirect(url_for("login"))

    if request.method == "GET":
        return render_template("edit-profile.html", options=OPTIONS, user=user)

    data = read_form()
    picture = request.files.get("profile_picture")
    has_picture = picture is not None and picture.filename != ""

    error = check_form(data)
    if not error and has_picture and not file_is_allowed(picture, "profile_picture"):
        error = "Profile picture must be JPG, JPEG or PNG."
    if not error:
        existing = run_query(
            "SELECT id FROM users WHERE email = %s AND id <> %s",
            (data["email"], user["id"]), "one")
        if existing:
            error = "That email is already used by another account."

    if error:
        flash(error)
        data["username"] = user["username"]
        data["profile_picture"] = user["profile_picture"]
        return render_template("edit-profile.html", options=OPTIONS, user=data)

    run_query(
        """UPDATE users SET
           full_name = %s, email = %s, date_of_birth = %s, phone = %s, gender = %s,
           country = %s, state = %s, address = %s, department = %s, year_of_study = %s,
           skills = %s, skill_level = %s, portfolio_url = %s, experience = %s,
           preferred_contact_time = %s
           WHERE id = %s""",
        (data["full_name"], data["email"], data["date_of_birth"], data["phone"],
         data["gender"], data["country"], data["state"], data["address"],
         data["department"], data["year_of_study"], data["skills"], data["skill_level"],
         data["portfolio_url"], int(data["experience"]), data["preferred_contact_time"],
         user["id"]),
    )

    if has_picture:
        stored_filename = save_file(picture, "profile_picture", user["id"], user["username"])
        run_query("UPDATE users SET profile_picture = %s WHERE id = %s", (stored_filename, user["id"]))

    flash("Profile updated successfully.")
    return redirect(url_for("profile"))


@app.route("/upload", methods=["POST"])
def upload():
    user = get_current_user()
    if user is None:
        return redirect(url_for("login"))

    category = request.form.get("category", "")
    file = request.files.get("file")

    if category not in ALLOWED_FILES:
        flash("Please choose a valid file category.")
    elif file is None or file.filename == "":
        flash("Please choose a file.")
    elif not file_is_allowed(file, category):
        flash("Allowed types for " + category + ": " + ", ".join(ALLOWED_FILES[category]))
    else:
        stored_filename = save_file(file, category, user["id"], user["username"])
        if category == "profile_picture":
            run_query("UPDATE users SET profile_picture = %s WHERE id = %s", (stored_filename, user["id"]))
        flash("File uploaded successfully.")

    return redirect(url_for("profile"))


@app.route("/files/<filename>")
def view_file(filename):
    if "username" not in session:
        return redirect(url_for("login"))

    # The folder comes from the session, so a user can only reach their own files.
    user_folder = os.path.join(UPLOAD_FOLDER, session["username"])
    download = request.args.get("download") == "1"
    return send_from_directory(user_folder, filename, as_attachment=download)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


if __name__ == "__main__":
    create_tables()
    app.run(debug=True)