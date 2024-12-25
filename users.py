import streamlit as st
import json
import hashlib
import smtplib
import string
import random
import boto3
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


s3 = boto3.client(
    's3',
    aws_access_key_id=st.secrets["AWS"]["YOUR_ACCESS_KEY"],
    aws_secret_access_key=st.secrets["AWS"]["YOUR_SECRET_KEY"],
    region_name='us-east-1'
)


def load_json_from_s3(bucket_name, object_key):
    response = s3.get_object(Bucket=bucket_name, Key=object_key)
    content = response['Body'].read().decode('utf-8')
    return json.loads(content)


def save_json_to_s3(file_path, bucket_name, s3_key):
    s3.upload_file(file_path, bucket_name, s3_key)
    print(f"Sauvegardé : s3://{bucket_name}/{s3_key}")



def create_account(username, password, email, sexe, age, description=None):
    users = st.session_state["users"]
    personnages = st.session_state["personnages"]

    # Vérifier si le nom d'utilisateur existe déjà
    if username in users:
        print("Le nom d'utilisateur est déjà utilisé.")
        st.error("Un compte avec ce nom d'utilisateur existe déjà.")
        return False

    # Vérifier si l'email est déjà utilisé
    if any(user_data["email"] == hash(email) for user_data in users.values()):
        print("L'email est déjà utilisé.")
        st.error("Un compte avec cet email existe déjà.")
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
    if st.session_state["creer_perso"] == "oui":
        if not isinstance(personnages, dict):
            personnages = {}  # Initialiser un dictionnaire vide si nécessaire

        personnages[username] = {"description": description}
        save_personnages(personnages)

    return True


def save_users(users):
    try:
        with open("json/stories_users.json", "w") as f:
            json.dump(users, f, indent=4)

        save_json_to_s3("json/stories_users.json", "jujul", "stories_users.json")

        st.success("Fichier 'stories_users.json' mis à jour en local et sur AWS.")

    except Exception as e:
        st.error(f"Erreur lors de la sauvegarde des utilisateurs : {e}")
        print(f"Erreur lors de la sauvegarde des utilisateurs : {e}")


def hash(element):
    return hashlib.sha256(element.encode()).hexdigest()


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
    st.session_state["creer_perso"] = st.radio("créer un personnage", ["oui", "non"])
    if st.session_state["creer_perso"]=="oui":
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
    users = st.session_state["users"]
    if username in users and users[username].get("reset_code") == reset_code:
        return True
    return False


def reinit_code_validation():
    reset_code = st.text_input("Entrez le code de réinitialisation envoyé par email")
    if st.button("Valider le code"):
        users = st.session_state["users"]
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
        users = st.session_state["users"]
        user_found = False

        for username, user_data in users.items():
            if hash(receiver_email) == users[username]["email"]:
                reset_code = generate_reset_code()
                users = st.session_state["users"]
                if username in users:
                    users[username]["reset_code"] = reset_code
                    save_users(users)
                else:
                    raise ValueError("Utilisateur introuvable.")

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
                        server.login(
                            st.secrets["gmail"]["sender_email"],
                            st.secrets["gmail"]["sender_password"],
                        )
                        server.sendmail(
                            st.secrets["gmail"]["sender_email"],
                            receiver_email,
                            msg.as_string(),
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

        if not user_found:
            st.error("Aucun utilisateur trouvé avec cet email.")


def reset_user_password(email, new_password):
    users = st.session_state["users"]
    for username, user_data in users.items():
        if user_data["email"] == email:
            hashed_password = hash(new_password)
            users[username]["password"] = hashed_password
            save_users(users)
            return True
    return False


def ensure_json_exists(item):
    os.makedirs("json", exist_ok=True)  # Crée le dossier s'il n'existe pas
    if not os.path.exists(f"json/{item}.json"):
        with open(f"json/{item}.json", "w") as f:
            f.write("{}")


def load_jsons():
    # Télécharger les fichiers JSON depuis AWS S3
    personnages_content = load_json_from_s3("jujul", "personnages.json")
    users_file_content = load_json_from_s3("jujul", "stories_users.json")
    stories_file_content = load_json_from_s3("jujul", "stories.json")

    ensure_json_exists("personnages")
    ensure_json_exists("stories_users")
    ensure_json_exists("stories")

    with open("json/personnages.json", "w") as f:
        json.dump(personnages_content, f, indent=4)

    with open("json/stories_users.json", "w") as f:
        json.dump(users_file_content, f, indent=4)

    with open("json/stories.json", "w") as f:
        json.dump(stories_file_content, f, indent=4)

    return personnages_content, users_file_content, stories_file_content


def save_personnages(personnages):
    try:
        # Sauvegarde locale
        with open("json/personnages.json", "w") as f:
            json.dump(personnages, f, indent=4, ensure_ascii=False)

        # Mise à jour sur AWS
        save_json_to_s3("json/personnages.json", "jujul", "personnages.json")

        st.success("Personnages mis à jour sur Google Drive.")
    except Exception as e:
        st.error(f"Erreur lors de la sauvegarde des personnages : {e}")
