import streamlit as st
import sqlite3
import hashlib
import smtplib
import string
import random
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import boto3

# Configuration de boto3 pour S3
s3 = boto3.client(
    's3',
    aws_access_key_id=st.secrets["AWS"]["YOUR_ACCESS_KEY"],
    aws_secret_access_key=st.secrets["AWS"]["YOUR_SECRET_KEY"],
    region_name='us-east-1'
)

LOCAL_DB_PATH = "stories.db"
S3_DB_KEY = "database/stories.db"

def upload_db_to_s3():
    """Téléverse stories.db sur S3 après une modification."""
    try:
        s3.upload_file(LOCAL_DB_PATH, "jujul", S3_DB_KEY)
        print(f"Base de données téléversée sur S3 : s3://jujul/{S3_DB_KEY}")
    except Exception as e:
        print(f"Erreur lors de l'upload de la base de données sur S3 : {e}")

def initialize_db():
    """Crée les tables nécessaires si la base de données est nouvelle."""
    conn = sqlite3.connect(LOCAL_DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS stories_user (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            utilisateur TEXT UNIQUE,
            password TEXT,
            email TEXT,
            sexe TEXT,
            age INTEGER,
            reset_code TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS personnages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            personnage TEXT UNIQUE,
            description TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS stories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titre TEXT,
            theme TEXT,
            keywords TEXT,
            sexe TEXT,
            age INTEGER,
            story TEXT,
            utilisateur TEXT,
            FOREIGN KEY (utilisateur) REFERENCES stories_user (utilisateur)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            story_id INTEGER NOT NULL,
            image_name TEXT NOT NULL,
            FOREIGN KEY (story_id) REFERENCES stories (id)
        )
    """)
    conn.commit()
    conn.close()
    print("Tables de la base de données créées ou vérifiées.")

def hash(element):
    return hashlib.sha256(element.encode()).hexdigest()

def load_users():
    try:
        conn = sqlite3.connect(LOCAL_DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT utilisateur, password, email, sexe, age, reset_code FROM stories_user")
        rows = cursor.fetchall()
        users = {row[0]: {
            "password": row[1],
            "email": row[2],
            "sexe": row[3],
            "age": row[4],
            "reset_code": row[5] if row[5] else None
        } for row in rows}
        conn.close()
        return users
    except sqlite3.OperationalError as e:
        if "no such table" in str(e):
            print("Table 'stories_user' non trouvée, initialisation de la base de données.")
            initialize_db()
            return {}
        raise e

def load_personnages():
    try:
        conn = sqlite3.connect(LOCAL_DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT personnage, description FROM personnages")
        rows = cursor.fetchall()
        personnages = {row[0]: {"description": row[1]} for row in rows}
        conn.close()
        return personnages
    except sqlite3.OperationalError as e:
        if "no such table" in str(e):
            print("Table 'personnages' non trouvée, initialisation de la base de données.")
            initialize_db()
            return {}
        raise e

def load_all_stories():
    try:
        conn = sqlite3.connect(LOCAL_DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT titre, theme, keywords, sexe, age, story, utilisateur FROM stories")
        rows = cursor.fetchall()
        stories = {row[0]: {
            "theme": row[1],
            "keywords": row[2],
            "sexe": row[3],
            "age": row[4],
            "story": row[5],
            "utilisateur": row[6],
            "images": []
        } for row in rows}
        cursor.execute("SELECT story_id, image_name FROM images")
        images = cursor.fetchall()
        for story_id, image_name in images:
            cursor.execute("SELECT titre FROM stories WHERE id = ?", (story_id,))
            titre = cursor.fetchone()[0]
            stories[titre]["images"].append(image_name)
        conn.close()
        return stories
    except sqlite3.OperationalError as e:
        if "no such table" in str(e):
            print("Table 'stories' ou 'images' non trouvée, initialisation de la base de données.")
            initialize_db()
            return {}
        raise e

def create_account(username, password, email, sexe, age, description=None):
    users = st.session_state["users"]
    personnages = st.session_state["personnages"]

    if username in users:
        st.error("Un compte avec ce nom d'utilisateur existe déjà.")
        return False

    if any(user_data["email"] == hash(email) for user_data in users.values()):
        st.error("Un compte avec cet email existe déjà.")
        return False

    conn = sqlite3.connect(LOCAL_DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO stories_user (utilisateur, password, email, sexe, age)
        VALUES (?, ?, ?, ?, ?)
    """, (username, hash(password), hash(email), sexe, age))
    conn.commit()

    if st.session_state["creer_perso"] == "oui":
        cursor.execute("""
            INSERT INTO personnages (personnage, description)
            VALUES (?, ?)
        """, (username, description))
        conn.commit()
        personnages[username] = {"description": description}

    conn.close()
    upload_db_to_s3()  # Synchroniser avec S3 après modification

    users[username] = {
        "password": hash(password),
        "email": hash(email),
        "sexe": sexe,
        "age": age,
    }
    return True

def verify_password(username, password):
    users = st.session_state["users"]
    if username in users and users[username]["password"] == hash(password):
        return True
    return False

def login_page():
    st.title("Page de connexion")
    username = st.text_input("Nom d'utilisateur")
    password = st.text_input("Mot de passe", type="password")
    if st.button("Se connecter"):
        if verify_password(username, password):
            st.success("Bienvenue, vous êtes connecté !")
            st.session_state["username"] = username
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("Nom d'utilisateur ou mot de passe incorrect.")

def create_account_page():
    st.title("Créer un compte")
    username = st.text_input("Nom d'utilisateur")
    password = st.text_input("Mot de passe", type="password")
    email = st.text_input("Email")
    sexe = st.radio("Tu es", ["une fille", "un garçon"])
    age = st.text_input("Quel est ton age ?")
    st.markdown("<br>", unsafe_allow_html=True)
    st.session_state["creer_perso"] = st.radio("Créer un personnage", ["oui", "non"])
    description = None
    if st.session_state["creer_perso"] == "oui":
        description = st.text_input("Décris-toi pour créer ton personnage")
    if st.button("Créer le compte"):
        if create_account(username, password, email, sexe, age, description):
            st.success("Compte créé avec succès ! Vous pouvez maintenant vous connecter.")
        else:
            st.error("Un compte avec ce nom d'utilisateur ou cet email existe déjà.")

def forgot_password_page():
    st.title("Mot de passe oublié")
    if "reset_email" not in st.session_state:
        st.session_state.reset_email = None
        st.session_state.reset_step = "email"
    if st.session_state.reset_step == "email":
        send_reinit_mail()
    elif st.session_state.reset_step == "code":
        reinit_code_validation()
    elif st.session_state.reset_step == "new_password":
        reinit_password()

def verify_reset_code(username, reset_code):
    users = st.session_state["users"]
    return username in users and users[username].get("reset_code") == reset_code

def reinit_code_validation():
    reset_code = st.text_input("Entrez le code de réinitialisation envoyé par email")
    if st.button("Valider le code"):
        users = st.session_state["users"]
        username = next((user for user, data in users.items() if data["email"] == st.session_state.reset_email), None)
        if username and verify_reset_code(username, reset_code):
            st.session_state.reset_step = "new_password"
            st.success("Code validé avec succès. Veuillez entrer un nouveau mot de passe.")
            st.rerun()
        else:
            st.error("Code de réinitialisation invalide.")

def reinit_password():
    new_password = st.text_input("Nouveau mot de passe", type="password")
    confirm_password = st.text_input("Confirmer le mot de passe", type="password")
    if st.button("Réinitialiser le mot de passe"):
        if new_password == confirm_password:
            if reset_user_password(st.session_state.reset_email, new_password):
                st.success("Mot de passe réinitialisé avec succès.")
                st.session_state.reset_email = None
                st.session_state.reset_step = "email"
                st.rerun()
            else:
                st.error("Erreur lors de la réinitialisation du mot de passe.")
        else:
            st.error("Les mots de passe ne correspondent pas.")

def generate_reset_code():
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=6))

def send_reinit_mail():
    receiver_email = st.text_input("Entrez votre email")
    if st.button("Envoyer un code de réinitialisation"):
        users = st.session_state["users"]
        username = next((user for user, data in users.items() if data["email"] == hash(receiver_email)), None)
        if username:
            reset_code = generate_reset_code()
            conn = sqlite3.connect(LOCAL_DB_PATH)
            cursor = conn.cursor()
            cursor.execute("UPDATE stories_user SET reset_code = ? WHERE utilisateur = ?", (reset_code, username))
            conn.commit()
            conn.close()
            upload_db_to_s3()  # Synchroniser avec S3 après modification
            users[username]["reset_code"] = reset_code

            subject = "Code de réinitialisation de mot de passe"
            body = f"Bonjour {username},\n\nVotre code de réinitialisation est : {reset_code}\n\nCordialement."
            msg = MIMEMultipart()
            msg["From"] = st.secrets["gmail"]["sender_email"]
            msg["To"] = receiver_email
            msg["Subject"] = subject
            msg.attach(MIMEText(body, "plain"))

            smtp_server = "smtp.gmail.com"
            smtp_port = 587
            try:
                with smtplib.SMTP(smtp_server, smtp_port) as server:
                    server.starttls()
                    server.login(st.secrets["gmail"]["sender_email"], st.secrets["gmail"]["sender_password"])
                    server.sendmail(st.secrets["gmail"]["sender_email"], receiver_email, msg.as_string())
                    print("E-mail envoyé avec succès.")
            except smtplib.SMTPException as e:
                print(f"Erreur SMTP : {e}")

            st.session_state.reset_email = hash(receiver_email)
            st.session_state.reset_step = "code"
            st.success(f"Un code de réinitialisation a été envoyé à {receiver_email}.")
            st.rerun()
        else:
            st.error("Aucun utilisateur trouvé avec cet email.")

def reset_user_password(email, new_password):
    users = st.session_state["users"]
    username = next((user for user, data in users.items() if data["email"] == email), None)
    if username:
        hashed_password = hash(new_password)
        conn = sqlite3.connect(LOCAL_DB_PATH)
        cursor = conn.cursor()
        cursor.execute("UPDATE stories_user SET password = ?, reset_code = NULL WHERE utilisateur = ?",
                       (hashed_password, username))
        conn.commit()
        conn.close()
        upload_db_to_s3()  # Synchroniser avec S3 après modification
        users[username]["password"] = hashed_password
        users[username]["reset_code"] = None
        return True
    return False