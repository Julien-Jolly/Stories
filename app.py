import streamlit as st
from users import (
    login_page,
    create_account_page,
    forgot_password_page,
    load_users,
    load_personnages,
    load_all_stories,
)
import openai
import os
from make_prompt import make_prompt
import uuid
import re
import requests
import sqlite3
import boto3
import tempfile
import time
import s3

# Configuration de boto3 pour S3
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_DEFAULT_REGION")
S3_BUCKET_NAME = "jujul"

try:
    s3_client = boto3.client(
        "s3",
        region_name=AWS_REGION,
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    )
    s3_client.head_bucket(Bucket=S3_BUCKET_NAME)
except Exception as e:
    st.error(f"Erreur de configuration S3 : {e}. Vérifiez vos credentials et le bucket.")
    st.stop()

# Chemin local temporaire pour stories.db
LOCAL_DB_PATH = "stories.db"
S3_DB_KEY = "database/stories.db"  # Chemin sur S3 : s3://jujul/database/stories.db

openai.api_key = st.secrets["openai"]["OPENAI_API_KEY"]

def log_stories_table(step):
    """Log l'état de la table stories à un moment donné."""
    conn = sqlite3.connect(LOCAL_DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, titre, utilisateur FROM stories")
    stories = cursor.fetchall()
    print(f"État de la table stories à l'étape '{step}':")
    for story in stories:
        print(f"  ID: {story[0]}, Titre: {story[1]}, Utilisateur: {story[2]}")
    conn.close()

def download_db_from_s3():
    """Télécharge stories.db depuis S3 s'il existe, sinon utilise une base vide."""
    max_retries = 3
    retry_delay = 1  # secondes
    if os.path.exists(LOCAL_DB_PATH):
        try:
            os.remove(LOCAL_DB_PATH)
            print(f"Fichier local {LOCAL_DB_PATH} supprimé avant le téléchargement.")
        except Exception as e:
            print(f"Erreur lors de la suppression de {LOCAL_DB_PATH} : {e}")
            raise e

    for attempt in range(max_retries):
        try:
            # Télécharger le fichier depuis S3
            print(f"Tentative {attempt + 1}/{max_retries} de téléchargement depuis S3...")
            s3.download_file("jujul", S3_DB_KEY, LOCAL_DB_PATH)
            print(f"Base de données téléchargée depuis S3 : s3://jujul/{S3_DB_KEY}")

            # Vérifier si le fichier existe et n'est pas vide
            if not os.path.exists(LOCAL_DB_PATH):
                print("Le fichier téléchargé n'existe pas.")
                raise FileNotFoundError("Fichier téléchargé n'existe pas")
            file_size = os.path.getsize(LOCAL_DB_PATH)
            print(f"Taille du fichier téléchargé : {file_size} octets")
            if file_size == 0:
                print("Le fichier téléchargé est vide.")
                raise FileNotFoundError("Fichier téléchargé est vide")

            # Vérifier l'intégrité de la base de données
            print("Vérification de l'intégrité de la base de données...")
            try:
                with sqlite3.connect(LOCAL_DB_PATH) as conn:
                    cursor = conn.cursor()
                    cursor.execute("PRAGMA integrity_check;")
                    result = cursor.fetchone()
                    print(f"Résultat de la vérification d'intégrité : {result}")
                    if result[0] != "ok":
                        print(f"Échec de la vérification d'intégrité : {result}")
                        raise sqlite3.DatabaseError("Base de données corrompue")
                    # Vérifier le contenu de la table stories
                    cursor.execute("SELECT id, titre, utilisateur FROM stories")
                    stories = cursor.fetchall()
                    print("État de la table stories dans le fichier local après téléchargement :")
                    for story in stories:
                        print(f"  ID: {story[0]}, Titre: {story[1]}, Utilisateur: {story[2]}")
            except sqlite3.Error as e:
                print(f"Erreur lors de la vérification de la base de données : {e}")
                raise e

            print("Base de données téléchargée et vérifiée avec succès.")
            return True

        except s3.exceptions.ClientError as e:
            if e.response['Error']['Code'] == "404":
                print("Base de données non trouvée sur S3, création d'une nouvelle base locale.")
                with sqlite3.connect(LOCAL_DB_PATH) as conn:
                    conn.close()
                return False
            else:
                print(f"Erreur S3 lors du téléchargement : {e}")
                raise e
        except PermissionError as e:
            if attempt < max_retries - 1:
                print(f"Erreur de permission lors du téléchargement de stories.db : {e}. Réessai dans {retry_delay} secondes...")
                time.sleep(retry_delay)
            else:
                print(f"Échec après {max_retries} tentatives : {e}")
                raise e
        except (sqlite3.Error, FileNotFoundError) as e:
            print(f"Erreur lors de la validation de la base de données : {e}")
            # Supprimer le fichier corrompu et réessayer
            if os.path.exists(LOCAL_DB_PATH):
                os.remove(LOCAL_DB_PATH)
            if attempt < max_retries - 1:
                print(f"Réessai dans {retry_delay} secondes...")
                time.sleep(retry_delay)
            else:
                print("Échec après toutes les tentatives, création d'une nouvelle base locale.")
                with sqlite3.connect(LOCAL_DB_PATH) as conn:
                    conn.close()
                return False

def upload_db_to_s3():
    """Téléverse stories.db sur S3 après une modification."""
    try:
        s3.upload_file(LOCAL_DB_PATH, "jujul", S3_DB_KEY)
        print(f"Base de données téléversée sur S3 : s3://jujul/{S3_DB_KEY}")
        log_stories_table("Après téléversement sur S3")  # Log après téléversement
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
            story_id TEXT,
            titre TEXT NOT NULL,
            theme TEXT,
            keywords TEXT,
            sexe TEXT,
            age INTEGER,
            story TEXT NOT NULL,
            utilisateur TEXT NOT NULL,
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

# Télécharger la base de données au démarrage et initialiser si nécessaire
was_downloaded = download_db_from_s3()
if not was_downloaded:
    initialize_db()

# Log après initialisation
log_stories_table("Après initialisation de la base")

# Charger les données initiales
st.session_state["personnages"] = load_personnages()
st.session_state["users"] = load_users()
st.session_state["all_stories"] = load_all_stories()

# Log après chargement des données initiales
log_stories_table("Après chargement des données initiales")

def download_from_s3(bucket_name, s3_key, local_path):
    """Télécharge un fichier depuis S3 vers un chemin local temporaire."""
    try:
        s3.download_file(bucket_name, s3_key, local_path)
        return local_path
    except Exception as e:
        print(f"Erreur lors du téléchargement depuis S3 : {e}")
        return None

def upload_to_s3(local_path, bucket_name, s3_key):
    """Téléverse un fichier local vers S3."""
    try:
        s3.upload_file(local_path, bucket_name, s3_key)
        print(f"Sauvegardé sur S3 : s3://jujul/{s3_key}")
        s3_url = f"https://{bucket_name}.s3.amazonaws.com/{s3_key}"
        return s3_url
    except Exception as e:
        print(f"Erreur lors de l'upload vers S3 : {e}")
        return None

def summarize_paragraph(paragraph, max_length=1000):
    try:
        print("réduction paragraphes pour prompt image")
        response = openai.ChatCompletion.create(
            model="gpt-3.5",
            messages=[
                {"role": "system", "content": "Tu es un assistant qui résume des textes."},
                {"role": "user", "content": f"Résumé ce paragraphe pour un prompt d'image : {paragraph}"},
            ],
            max_tokens=150,
            temperature=0.7,
        )
        summary = response.choices[0].message["content"]
        return summary[:max_length] + "..." if len(summary) > max_length else summary.strip()
    except Exception as e:
        print(f"Erreur lors du résumé du paragraphe : {e}")
        return paragraph[:max_length] + "..." if len(paragraph) > max_length else paragraph

def save_image(image_url, story_id, paragraph_index):
    """Télécharge une image depuis une URL et la téléverse sur S3."""
    unique_id = uuid.uuid4().hex
    s3_key = f"images/story_{story_id}_paragraph_{paragraph_index}_{unique_id}.png"

    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as temp_file:
        response = requests.get(image_url)
        response.raise_for_status()
        temp_file.write(response.content)
        temp_file_path = temp_file.name

    s3_url = upload_to_s3(temp_file_path, "jujul", s3_key)
    os.unlink(temp_file_path)
    return s3_url if s3_url else None

def edit_images_with_dalle(paragraphs, style, story_id, personnage):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as base_temp, \
            tempfile.NamedTemporaryFile(delete=False, suffix=".png") as mask_temp:
        base_image_path = download_from_s3("jujul", "images_source/zouzou.png", base_temp.name)
        mask_path = download_from_s3("jujul", "images_source/mask.png", mask_temp.name)

        if not base_image_path or not mask_path:
            print("Impossible de télécharger les fichiers de base depuis S3.")
            return []

        image_paths = []
        for index, paragraph in enumerate(paragraphs):
            summarized_prompt = summarize_paragraph(paragraph)
            full_prompt = f"{personnage}: {summarized_prompt}. Style: {style}"
            try:
                response = openai.Image.create_edit(
                    image=open(base_image_path, "rb"),
                    mask=open(mask_path, "rb"),
                    prompt=full_prompt,
                    n=1,
                    size="256x256",
                )
                image_url = response["data"][0]["url"]
                s3_url = save_image(image_url, story_id, index + 1)
                image_paths.append(s3_url)
            except Exception as e:
                print(f"Erreur lors de l'édition de l'image : {e}")
                image_paths.append(None)

    os.unlink(base_image_path)
    os.unlink(mask_path)
    return image_paths

def options(theme_list, mode_list, style_images, personnages, personnage_names):
    mode = st.sidebar.radio(label="Que souhaites-tu lire ?", options=mode_list, key="selected_mode")
    st.sidebar.markdown("<br><br>", unsafe_allow_html=True)
    selected_perso = st.sidebar.multiselect("Quel personnage souhaites-tu voir apparaître ?", personnage_names,
                                            key="selected_perso")
    st.sidebar.markdown("<br>", unsafe_allow_html=True)
    st.sidebar.write("\n\n".join([personnages[p]["description"] for p in selected_perso]))
    st.sidebar.markdown("<br><br>", unsafe_allow_html=True)
    theme = st.sidebar.selectbox("Quel thème souhaites-tu aborder ?", theme_list, key="selected_theme")
    st.sidebar.markdown("<br><br>", unsafe_allow_html=True)
    user_keywords = st.sidebar.text_area("Entre ici les mots-clés pour orienter le récit", key="user_input")
    st.sidebar.markdown("<br><br>", unsafe_allow_html=True)
    return theme, mode, user_keywords, "", selected_perso

def load_stories(username):
    conn = sqlite3.connect(LOCAL_DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT titre, story FROM stories WHERE utilisateur = ?", (username,))
    user_stories = cursor.fetchall()
    if not user_stories:
        st.warning("Aucune histoire enregistrée pour cet utilisateur.")
        return
    for titre, story_text in user_stories:
        with st.expander(titre):
            paragraphs = story_text.split("\n\n")
            for paragraph in paragraphs:
                st.write(paragraph.strip())
    conn.close()

def main_app(users, personnages):
    st.title(f"Bienvenue {st.session_state['username']}")
    theme_list = ("Aventure", "Fantastique", "Science-fiction", "Comédie")
    mode_list = ("nouvelle histoire", "histoires enregistrées")
    style_images = ("cartoon", "dessin classique", "photo réaliste", "photo non réaliste")
    personnage_names = list(personnages.keys())
    theme, mode, user_keywords, style_images, selected_perso = options(theme_list, mode_list, style_images, personnages,
                                                                       personnage_names)

    if mode == "nouvelle histoire":
        if st.sidebar.button("Lancer"):
            image_paths = []
            username = st.session_state["username"]
            generated_story = generate_story(theme, user_keywords, users, personnages, selected_perso)
            paragraphs = generated_story.split("\n\n")
            if not paragraphs:
                st.error("L'histoire générée est vide.")
                return

            # Sauvegarder l'histoire pour obtenir un story_id
            raw_title = generated_story.split("\n")[0].replace("Titre : ", "").strip()
            title = re.sub(r'[\\/:"*?<>|]', "", raw_title)
            conn = sqlite3.connect(LOCAL_DB_PATH)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO stories (story_id, titre, theme, keywords, sexe, age, story, utilisateur)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (None, title, theme, user_keywords, users[username]["sexe"], users[username]["age"], generated_story, username))
            story_id = cursor.lastrowid
            conn.commit()
            conn.close()
            upload_db_to_s3()  # Synchroniser avec S3 après modification

            style = f"Illustration pour un livre pour enfants, cartoon, personnages constants."
            image_paths = edit_images_with_dalle(paragraphs, style, story_id, ', '.join(selected_perso))
            display_story_with_images(image_paths, paragraphs)
            save_story(generated_story, theme, user_keywords, users, image_paths)

    elif mode == "histoires enregistrées":
        load_stories(st.session_state["username"])

    if st.sidebar.button("Quitter"):
        st.session_state["authenticated"] = False
        st.session_state["username"] = None
        st.rerun()

def generate_story(theme, user_keywords, users, personnages, selected_perso):
    username = st.session_state["username"]
    messages = make_prompt(theme, user_keywords, users[username]["age"], users[username]["sexe"], personnages,
                           selected_perso)
    response = openai.ChatCompletion.create(model="gpt-4", messages=messages, max_tokens=4000, temperature=0.7)
    return response.choices[0].message["content"]

def display_story_with_images(image_paths, paragraphs):
    for i, paragraph in enumerate(paragraphs):
        st.write(paragraph.strip())
        if image_paths and i < len(image_paths) and image_paths[i]:
            st.image(image_paths[i], caption="Illustration", use_container_width=True)

def save_story(story, theme, user_keywords, users, image_paths):
    raw_title = story.split("\n")[0].replace("Titre : ", "").strip()
    title = re.sub(r'[\\/:"*?<>|]', "", raw_title)
    username = st.session_state["username"]
    conn = sqlite3.connect(LOCAL_DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO stories (story_id, titre, theme, keywords, sexe, age, story, utilisateur)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (None, title, theme, user_keywords, users[username]["sexe"], users[username]["age"], story, username))
    story_id = cursor.lastrowid
    for image_path in image_paths:
        if image_path:
            cursor.execute("INSERT INTO images (story_id, image_name) VALUES (?, ?)", (story_id, image_path))
    conn.commit()
    conn.close()
    upload_db_to_s3()  # Synchroniser avec S3 après modification
    st.session_state["all_stories"][title] = {
        "theme": theme,
        "keywords": user_keywords,
        "sexe": users[username]["sexe"],
        "age": users[username]["age"],
        "story": story,
        "utilisateur": username,
        "images": image_paths
    }

if __name__ == "__main__":
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False
        st.session_state["username"] = None

    if st.session_state["authenticated"]:
        main_app(st.session_state["users"], st.session_state["personnages"])
    else:
        st.sidebar.title("Navigation")
        page = st.sidebar.radio("Accès à l'application", ["Connexion", "Créer un compte", "Mot de passe oublié"])
        if page == "Connexion":
            login_page()
        elif page == "Créer un compte":
            create_account_page()
        elif page == "Mot de passe oublié":
            forgot_password_page()