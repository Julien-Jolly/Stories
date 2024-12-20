import os
from users import login_page, create_account_page, forgot_password_page
import json
import openai
import make_prompt
import streamlit as st
from dotenv import load_dotenv
import requests

load_dotenv()

# Assumons que la clé API de Grok est configurée de manière similaire
grok_api_key = os.getenv("GROK_API_KEY")

def options(theme_list, mode_list):
    mode = st.sidebar.radio(
        label="Que souhaites tu lire ?", options=mode_list, key="selected_mode"
    )

    st.sidebar.markdown("<br><br>", unsafe_allow_html=True)

    theme = st.sidebar.selectbox(
        "Quel thème souhaites tu aborder ?", theme_list, key="selected_theme"
    )

    st.sidebar.markdown("<br><br>", unsafe_allow_html=True)

    user_keywords = st.sidebar.text_area(
        "Entre ici les mots clé pour orienter le récit", key="user_input"
    )

    st.sidebar.markdown("<br><br>", unsafe_allow_html=True)

    return theme, mode, user_keywords

def main_app(users):
    st.title(f"Bienvenue {st.session_state['username']}")

    theme_list = ("Aventure", "Fantastique", "Science-fiction", "Comédie")
    mode_list = ("nouvelle histoire", "histoires enregistrées")

    theme, mode, user_keywords = options(theme_list, mode_list)

    if st.sidebar.button("Lancer"):
        generated_story = generate_story(theme, user_keywords, users)

        st.text(generated_story)

        record_story(generated_story, theme, user_keywords, users)

    if st.sidebar.button("Quitter"):
        st.session_state["authenticated"] = False
        st.session_state["username"] = None
        st.rerun()


def generate_story(theme, user_keywords, users):
    # Construire le message pour l'API Grok
    messages = make_prompt.make_prompt(
        theme, user_keywords, users[username]["age"], users[username]["sexe"]
    )

    # Envoyer la requête à l'API Grok avec la bibliothèque requests
    response = requests.post(
        "https://api.x.ai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {grok_api_key}",
            "Content-Type": "application/json"
        },
        json={
            "model": "grok-beta",
            "messages": messages,
            "max_tokens": 2000,
            "temperature": 0.7
        }
    )

    # Vérifier si la requête a réussi
    if response.status_code == 200:
        data = response.json()
        generated_story = data['choices'][0]['message']['content']
        return generated_story
    else:
        raise Exception(f"Erreur lors de l'appel à l'API Grok: {response.status_code}")

def record_story(generated_story, theme, user_keywords, users):
    with open("json/stories.json", "r") as f:
        stories = json.load(f)

    new_id = len(stories) + 1
    stories[new_id] = {
        "theme": theme,
        "keywords": user_keywords,
        "age": users[username]["age"],
        "sexe": users[username]["sexe"],
        "story": generated_story,
    }
    with open("json/stories.json", "w") as f:
        json.dump(stories, f, indent=4, ensure_ascii=False)
    if "stories" not in users[username]:
        users[username]["stories"] = []
    users[username]["stories"].append(new_id)
    with open("json/stories_users.json", "w") as f:
        json.dump(users, f, indent=4, ensure_ascii=False)

if __name__ == "__main__":

    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False
        st.session_state["username"] = None

    if st.session_state["authenticated"]:
        with open("json/stories_users.json", "r") as f:
            users = json.load(f)
        username = st.session_state["username"]
        main_app(users)

    else:
        st.sidebar.title("Navigation")
        page = st.sidebar.radio(
            "Accès à l'application",
            ["Connexion", "Créer un compte", "Mot de passe oublié"],
        )
        if page == "Connexion":
            login_page()
        # elif page == "Créer un compte":
        #     create_account_page()
        elif page == "Mot de passe oublié":
            forgot_password_page()