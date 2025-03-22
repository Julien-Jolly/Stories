import sqlite3
import json
import os
from users import upload_db_to_s3  # Importer la fonction depuis users.py

# Chemin vers la base de données
DB_PATH = "stories.db"

def create_connection():
    """Crée une connexion à la base de données SQLite."""
    try:
        conn = sqlite3.connect(DB_PATH)
        return conn
    except sqlite3.Error as e:
        print(f"Erreur lors de la connexion à la base de données : {e}")
        return None

def create_tables(conn):
    """Crée les tables nécessaires dans la base de données."""
    try:
        cursor = conn.cursor()

        # Table stories_user
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS stories_user (
                utilisateur TEXT PRIMARY KEY,
                password TEXT NOT NULL,
                email TEXT NOT NULL,
                sexe TEXT NOT NULL,
                age INTEGER NOT NULL,
                reset_code TEXT
            )
        ''')

        # Table personnages
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS personnages (
                personnage TEXT PRIMARY KEY,
                description TEXT NOT NULL
            )
        ''')

        # Table stories
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS stories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                story_id TEXT,
                titre TEXT NOT NULL,
                theme TEXT NOT NULL,
                keywords TEXT,
                sexe TEXT NOT NULL,
                age INTEGER NOT NULL,
                story TEXT NOT NULL,
                utilisateur TEXT NOT NULL,
                FOREIGN KEY (utilisateur) REFERENCES stories_user (utilisateur)
            )
        ''')

        # Table images
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                story_id INTEGER NOT NULL,
                image_name TEXT NOT NULL,
                FOREIGN KEY (story_id) REFERENCES stories (id)
            )
        ''')

        conn.commit()
        print("Tables de la base de données créées.")
    except sqlite3.Error as e:
        print(f"Erreur lors de la création des tables : {e}")

def insert_users(conn, users_data):
    """Insère les utilisateurs à partir de stories_users.json."""
    try:
        cursor = conn.cursor()
        for username, user_info in users_data.items():
            if not isinstance(user_info, dict):
                print(f"Erreur : Entrée utilisateur invalide pour '{username}', attendu un dictionnaire, trouvé {type(user_info)}")
                continue
            cursor.execute('''
                INSERT OR REPLACE INTO stories_user (utilisateur, password, email, sexe, age, reset_code)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                username,
                user_info.get('password', ''),
                user_info.get('email', ''),
                user_info.get('sexe', ''),
                int(user_info.get('age', 0)),
                None  # Valeur par défaut pour reset_code
            ))
        conn.commit()
        print("Utilisateurs insérés depuis stories_users.json.")
    except sqlite3.Error as e:
        print(f"Erreur lors de l'insertion des utilisateurs : {e}")

def insert_personnages(conn, personnages_data):
    """Insère les personnages à partir de personnages.json."""
    try:
        cursor = conn.cursor()
        for personnage, info in personnages_data.items():
            cursor.execute('''
                INSERT OR REPLACE INTO personnages (personnage, description)
                VALUES (?, ?)
            ''', (personnage, info.get('description', '')))
        conn.commit()
        print("Personnages insérés depuis personnages.json.")
    except sqlite3.Error as e:
        print(f"Erreur lors de l'insertion des personnages : {e}")

def insert_stories_and_images(conn, stories_data):
    """Insère les histoires et leurs images à partir de stories.json."""
    try:
        cursor = conn.cursor()
        for story_title, story_info in stories_data.items():
            # Vérifier si l'utilisateur existe
            cursor.execute("SELECT utilisateur FROM stories_user WHERE utilisateur = ?", (story_info['utilisateur'],))
            if not cursor.fetchone():
                print(f"Utilisateur '{story_info['utilisateur']}' non trouvé dans stories_user, ajout avec des valeurs par défaut.")
                cursor.execute('''
                    INSERT INTO stories_user (utilisateur, password, email, sexe, age, reset_code)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (story_info['utilisateur'], 'default_password', 'default_email@example.com', story_info['sexe'], int(story_info['age']), None))

            # Insérer l'histoire
            cursor.execute('''
                INSERT INTO stories (story_id, titre, theme, keywords, sexe, age, story, utilisateur)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                story_info.get('story_id', None),
                story_info['title'],
                story_info['theme'],
                story_info.get('keywords', ''),
                story_info['sexe'],
                int(story_info['age']),
                story_info['story'],
                story_info['utilisateur']
            ))
            story_id = cursor.lastrowid

            # Insérer les images
            images = story_info.get('images', [])
            if isinstance(images, str):
                images = [] if images.strip() == "" else [images]
            for image in images:
                if image and image != "null":  # Ignorer les valeurs nulles ou vides
                    cursor.execute('''
                        INSERT INTO images (story_id, image_name)
                        VALUES (?, ?)
                    ''', (story_id, image))

        conn.commit()
        print("Histoires et images insérées depuis stories.json.")
    except sqlite3.Error as e:
        print(f"Erreur lors de l'insertion des histoires et images : {e}")

def main():
    # Supprimer la base de données existante
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print(f"Base de données existante supprimée : {DB_PATH}")

    # Créer une nouvelle connexion
    conn = create_connection()
    if conn is None:
        return

    try:
        # Créer les tables
        create_tables(conn)

        # Charger les données des fichiers JSON
        with open('stories_users.json', 'r', encoding='utf-8') as f:
            users_data = json.load(f)
        with open('personnages.json', 'r', encoding='utf-8') as f:
            personnages_data = json.load(f)
        with open('stories.json', 'r', encoding='utf-8') as f:
            stories_data = json.load(f)

        # Insérer les données
        insert_users(conn, users_data)
        insert_personnages(conn, personnages_data)
        insert_stories_and_images(conn, stories_data)

        # Téléverser la base de données sur S3
        upload_db_to_s3()

        print("Initialisation de la base de données terminée.")
    except Exception as e:
        print(f"Erreur lors de l'initialisation de la base de données : {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    main()