import streamlit as st
import json
import hashlib
import smtplib
import string
import random
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
from app import (load_personnages, save_personnages)

load_dotenv()


def load_users():
    try:
        # file_content = service.files().get_media(fileId=GOOGLE_DRIVE_FILE_ID).execute()
        #
        # with open("json/users.json", "wb") as f:
        #     f.write(file_content)

        with open("json/users.json", "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except Exception as e:
        st.error(f"Erreur lors du chargement des utilisateurs : {e}")
        return {}


def create_account(username, password, email, sexe, age, description):
    users = load_users()
    personnages = load_personnages()

    # Vérifier si le nom d'utilisateur existe déjà
    if username in users:
        print("Le nom d'utilisateur est déjà utilisé.")
        return False

    # Vérifier si l'email est déjà utilisé
    if any(user_data["email"] == hash(email) for user_data in users.values()):
        print("L'email est déjà utilisé.")
        return False

    # Ajouter le nouvel utilisateur
    users[username] = {
        "password": hash(password),
        "email": hash(email),
        "sexe": sexe,
        "age": age,
    }
    save_users(users)

    # Ajouter le personnage correspondant
    if not isinstance(personnages, dict):
        personnages = {}  # Initialiser un dictionnaire vide si nécessaire

    personnages[username] = {"description": description}
    save_personnages(personnages)

    return True


def save_users(users):
    try:
        with open("json/users.json", "w") as f:
            json.dump(users, f, indent=4)
            st.success("Fichier 'users.json' mis à jour.")

        # service = authenticate_google_drive()
        # media = MediaFileUpload("json/users.json", mimetype="application/json")
        #
        # service.files().get(fileId=GOOGLE_DRIVE_FILE_ID).execute()
        # service.files().update(fileId=GOOGLE_DRIVE_FILE_ID, media_body=media).execute()
        #
        # st.success("Fichier 'users.json' mis à jour sur Google Drive.")
    except Exception as e:
        st.error(f"Erreur lors de la sauvegarde des utilisateurs : {e}")
        print(f"Erreur lors de la sauvegarde des utilisateurs : {e}")


def hash(element):
    return hashlib.sha256(element.encode()).hexdigest()


def verify_password(username, password):
    users = load_users()
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
    description = st.text_input("décris toi pour créer ton prersonnage")

    if st.button("Créer le compte"):
        if create_account(username, password, email, sexe, age, description):
            st.success(
                "Compte créé avec succès ! Vous pouvez maintenant vous connecter."
            )
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
    users = load_users()
    if username in users and users[username].get("reset_code") == reset_code:
        return True
    return False


def reinit_code_validation():
    reset_code = st.text_input("Entrez le code de réinitialisation envoyé par email")
    if st.button("Valider le code"):
        users = load_users()
        username = None
        for user, data in users.items():
            if data["email"] == st.session_state.reset_email:
                username = user
                break
            else:
                st.error("souci email.")

        if username and verify_reset_code(username, reset_code):
            st.session_state.reset_step = "new_password"
            st.success(
                "Code validé avec succès. Veuillez entrer un nouveau mot de passe."
            )
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
        users = load_users()
        user_found = False

        for username, user_data in users.items():
            if hash(receiver_email) == users[username]["email"]:
                reset_code = generate_reset_code()
                users = load_users()
                if username in users:
                    users[username]["reset_code"] = reset_code
                    save_users(users)
                else:
                    raise ValueError("Utilisateur introuvable.")

                subject = "Code de réinitialisation de mot de passe"
                body = f"Bonjour {username},\n\nVotre code de réinitialisation est : {reset_code}\n\nCordialement."

                msg = MIMEMultipart()
                msg["From"] = os.getenv("sender_email")
                msg["To"] = receiver_email
                msg["Subject"] = subject
                msg.attach(MIMEText(body, "plain"))

                smtp_server = "smtp.gmail.com"
                smtp_port = 587

                try:
                    with smtplib.SMTP(smtp_server, smtp_port) as server:
                        server.starttls()
                        server.login(
                            os.getenv("sender_email"),
                            os.getenv("sender_password"),
                        )
                        server.sendmail(
                            os.getenv("sender_email"), receiver_email, msg.as_string()
                        )
                        print("E-mail envoyé avec succès.")
                except smtplib.SMTPException as e:
                    print(f"Erreur SMTP : {e}")

                user_found = True
                st.session_state.reset_email = hash(receiver_email)
                st.session_state.reset_step = "code"
                st.success(
                    f"Un code de réinitialisation a été envoyé à {receiver_email}."
                )
                st.rerun()
                break

        if not user_found:
            st.error("Aucun utilisateur trouvé avec cet email.")


def reset_user_password(email, new_password):
    users = load_users()
    for username, user_data in users.items():
        if user_data["email"] == email:
            hashed_password = hash(new_password)
            users[username]["password"] = hashed_password
            save_users(users)
            return True
    return False


