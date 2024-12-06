import streamlit as st
from users import login_page, create_account_page, forgot_password_page
import openai
import os
import make_prompt
import json
from dotenv import load_dotenv

load_dotenv()

openai.api_key = os.getenv("OPENAI_API_KEY")


def options(theme_list, mode_list):
    mode=st.sidebar.radio(label="Que souhaites tu lire ?", options= mode_list, key="selected_mode")

    st.sidebar.markdown("<br><br>", unsafe_allow_html=True)

    theme=st.sidebar.selectbox(
        "Quel thème souhaites tu ?",
        theme_list, key="selected_theme"
    )

    st.sidebar.markdown("<br><br>", unsafe_allow_html=True)

    user_keywords = st.sidebar.text_area("entre ici les mots clé pour imaginer ton histoire", key="user_input")

    st.sidebar.markdown("<br><br>", unsafe_allow_html=True)

    return theme, mode, user_keywords


def main_app(users):
    st.title(f"Bienvenue {st.session_state["username"]}")

    theme_list = ("Aventure", "Fantastique", "Science-fiction", "Comédie")
    mode_list = ("nouvelle histoire", "histoires enregistrées")

    theme, mode, user_keywords = options(theme_list, mode_list)

    if st.sidebar.button("Lancer"):
        messages=make_prompt.make_prompt(theme, user_keywords, users[username]["age"], users[username]["sexe"])
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=messages,
            max_tokens=2000,
            temperature=0.7
        )

        generated_story = response.choices[0].message["content"]

        st.text(generated_story)

        new_id = len(stories) + 1

        stories[new_id] = {
            "theme": theme,
            "keywords": user_keywords,
            "age": users[username]["age"],
            "sexe": users[username]["sexe"],
            "story": generated_story
        }

        with open("json/stories.json", "w") as f:
            json.dump(stories, f, indent=4, ensure_ascii=False)

        if "stories" not in users[username]:
            users[username]["stories"] = []

        users[username]["stories"].append(new_id)

        with open("json/users.json", "w") as f:
            json.dump(users, f, indent=4, ensure_ascii=False)


    st.sidebar.markdown("<br><br>", unsafe_allow_html=True)

    if st.sidebar.button("Quitter"):
        st.session_state["authenticated"] = False
        st.session_state["username"] = None
        st.rerun()


if __name__ == "__main__":

    if os.path.exists("json/stories.json"):
        with open("json/stories.json", "r") as f:
            stories = json.load(f)
    else:
        stories = {}

    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False
        st.session_state["username"] = None

    if st.session_state["authenticated"]:
        with open("json/users.json", "r") as f:
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
        #elif page == "Créer un compte":
            #create_account_page()
        elif page == "Mot de passe oublié":
            forgot_password_page()