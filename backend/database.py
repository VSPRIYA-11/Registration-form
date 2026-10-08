import os
import mysql.connector


def get_connection():
    return mysql.connector.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        user=os.environ.get("DB_USER", "root"),
        password=os.environ.get("DB_PASSWORD", "Tringapps@01"),
        database=os.environ.get("DB_NAME", "registration_app"),
    )


def create_tables():
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            full_name VARCHAR(100) NOT NULL,
            username VARCHAR(20) NOT NULL UNIQUE,
            email VARCHAR(100) NOT NULL UNIQUE,
            password VARCHAR(255) NOT NULL,
            date_of_birth DATE NOT NULL,
            phone VARCHAR(15) NOT NULL,
            gender VARCHAR(10) NOT NULL,
            country VARCHAR(50) NOT NULL,
            state VARCHAR(50) NOT NULL,
            address TEXT NOT NULL,
            department VARCHAR(50) NOT NULL,
            year_of_study VARCHAR(20) NOT NULL,
            skills VARCHAR(255),
            skill_level VARCHAR(20) NOT NULL,
            portfolio_url VARCHAR(255),
            experience INT,
            preferred_contact_time VARCHAR(5),
            profile_picture VARCHAR(255) DEFAULT ''
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS files (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            original_filename VARCHAR(255) NOT NULL,
            stored_filename VARCHAR(255) NOT NULL,
            file_path VARCHAR(255) NOT NULL,
            file_type VARCHAR(100),
            category VARCHAR(30) NOT NULL,
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    connection.commit()
    cursor.close()
    connection.close()