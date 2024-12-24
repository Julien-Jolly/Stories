import streamlit as st
from users import (
    login_page,
    create_account_page,
    forgot_password_page,
    load_jsons,
    save_json_to_s3,
)
import openai
import os
from make_prompt import make_prompt
import json
from dotenv import load_dotenv
import uuid
import re
import requests

openai.api_key = st.secrets["openai"]["OPENAI_API_KEY"]

(
    st.session_state["personnages"],
    st.session_state["users"],
    st.session_state["all_stories"],
) = load_jsons()


def summarize_paragraph(paragraph, max_length=1000):
    """
    Génère un résumé court d'un paragraphe en utilisant l'API OpenAI.
    Tronque le résumé à max_length caractères si nécessaire.
    """
    try:
        print("réduction paragraphes pour prompt image")
        response = openai.ChatCompletion.create(
            model="gpt-3.5",
            messages=[
                {
                    "role": "system",
                    "content": "Tu es un assistant qui résume des textes.",
                },
                {
                    "role": "user",
                    "content": f"Résumé ce paragraphe pour un prompt d'image : {paragraph}",
                },
            ],
            max_tokens=150,  # Ajustez cette valeur si nécessaire
            temperature=0.7,
        )
        summary = response.choices[0].message["content"]
        if len(summary) > max_length:
            print("réduction paragraphes à refaire")
            summary = (
                summary[:max_length] + "..."
            )  # Tronquer et ajouter des points de suspension
        return summary.strip()
    except Exception as e:
        print(f"Erreur lors du résumé du paragraphe : {e}")
        return (
            (paragraph[:max_length] + "...")
            if len(paragraph) > max_length
            else paragraph
        )


def save_image(image_url, story_id, paragraph_index):
    """
    Télécharge et enregistre une image à partir de son URL.
    Renvoie un chemin par défaut si l'image ne peut pas être téléchargée.
    """
    images_dir = "images"
    os.makedirs(images_dir, exist_ok=True)  # Crée le dossier s'il n'existe pas

    # Générer un identifiant unique pour éviter les conflits
    unique_id = uuid.uuid4().hex
    image_path = os.path.join(
        images_dir, f"story_{story_id}_paragraph_{paragraph_index}_{unique_id}.png"
    )

    try:
        response = requests.get(image_url)
        response.raise_for_status()  # Vérifie si la requête a réussi
        with open(image_path, "wb") as f:
            f.write(response.content)
        return image_path
    except Exception as e:
        print(f"Erreur lors du téléchargement de l'image : {e}")
        return None  # Renvoie None si une erreur survient


def edit_images_with_dalle(paragraphs, style, story_id, personnage):
    """
    Modifie des images existantes en utilisant les paragraphes comme prompts.
    Utilise une image source comme base et génère une image éditée pour chaque paragraphe.
    """
    base_image_path = os.path.join("images_source", "zouzou.png")
    if not os.path.exists(base_image_path):
        print(f"Image source introuvable : {base_image_path}")
        return []

    image_paths = []

    for index, paragraph in enumerate(paragraphs):
        summarized_prompt = summarize_paragraph(paragraph)

        full_prompt = f"{personnage}: {summarized_prompt}. Style: {style}"
        mask_path = os.path.join("images_source", "mask.png")

        try:
            response = openai.Image.create_edit(
                image=open(base_image_path, "rb"),
                mask=open(mask_path, "rb"),
                prompt=full_prompt,
                n=1,
                size="256x256",
            )
            image_url = response["data"][0]["url"]

            # Télécharger et enregistrer l'image générée avec un nom unique basé sur l'histoire
            image_path = save_image(image_url, story_id, index + 1)
            image_paths.append(image_path)
        except Exception as e:
            print(f"Erreur lors de l'édition de l'image : {e}")
            image_paths.append(None)

    return image_paths


def options(theme_list, mode_list, style_images, personnages, personnage_names):
    mode = st.sidebar.radio(
        label="Que souhaites tu lire ?", options=mode_list, key="selected_mode"
    )

    st.sidebar.markdown("<br><br>", unsafe_allow_html=True)

    selected_perso = st.sidebar.multiselect(
        "Quel personnage souhaites-tu voir apparaître ?",
        personnage_names,
        key="selected_perso",
    )

    st.sidebar.markdown("<br>", unsafe_allow_html=True)

    st.sidebar.write(
        "\n\n".join([personnages[p]["description"] for p in selected_perso])
    )

    st.sidebar.markdown("<br><br>", unsafe_allow_html=True)

    theme = st.sidebar.selectbox(
        "Quel thème souhaites-tu aborder ?", theme_list, key="selected_theme"
    )

    st.sidebar.markdown("<br><br>", unsafe_allow_html=True)

    # style_images = st.sidebar.selectbox(
    #     "Quel style souhaites-tu pour les images ?", style_images, key="selected_style"
    # )
    style_images = ""

    st.sidebar.markdown("<br><br>", unsafe_allow_html=True)

    user_keywords = st.sidebar.text_area(
        "Entre ici les mots-clés pour orienter le récit", key="user_input"
    )

    st.sidebar.markdown("<br><br>", unsafe_allow_html=True)

    return theme, mode, user_keywords, style_images, selected_perso


def load_stories(users, user, stories):
    """
    Charge et affiche les histoires enregistrées pour un utilisateur donné (si username est fourni),
    ou retourne toutes les histoires si aucun username n'est spécifié.
    En téléchargeant le fichier stories.json depuis Google Drive si nécessaire.
    """
    try:

        if user not in users or "stories" not in users[username]:
            st.warning("Aucune histoire enregistrée pour cet utilisateur.")
            return

        user_story_titles = users[username]["stories"]
        for story_title in user_story_titles:
            story = stories.get(story_title)
            if story:
                with st.expander(story.get("title", "Titre manquant")):
                    story_text = story.get("story", "Contenu manquant")
                    images = story.get("images", [])

                    paragraphs = story_text.split("\n\n")
                    for i, paragraph in enumerate(paragraphs):
                        st.write(paragraph.strip())

                        if i < len(images) and images[i]:
                            if os.path.exists(images[i]):
                                st.image(
                                    images[i],
                                    caption="Illustration",
                                    use_container_width=True,
                                )
                            else:
                                #st.info("(Image non disponible pour ce paragraphe.)")
                                return

                    if not images:
                        st.info("(Cette histoire n'a pas d'illustrations associées.)")
            else:
                st.warning(f"Histoire avec le titre '{story_title}' introuvable.")

    except Exception as e:
        st.error(f"Erreur lors du chargement des histoires : {e}")
        return {}


def main_app(users, personnages):
    st.title(f"Bienvenue {st.session_state['username']}")

    theme_list = ("Aventure", "Fantastique", "Science-fiction", "Comédie")
    mode_list = ("nouvelle histoire", "histoires enregistrées")
    style_images = (
        "cartoon",
        "dessin classique",
        "photo réaliste",
        "photo non réaliste",
    )

    personnage_names = list(personnages.keys())
    theme, mode, user_keywords, style_images, selected_perso = options(
        theme_list, mode_list, style_images, personnages, personnage_names
    )
    print(f"selection {selected_perso}")

    if mode == "nouvelle histoire":
        if st.sidebar.button("Lancer"):
            image_paths = []
            generated_story = generate_story(
                theme, user_keywords, users, personnages, selected_perso
            )
            paragraphs = generated_story.split("\n\n")
            if not paragraphs:
                st.error("L'histoire générée est vide.")
                return
            style = f"Illustration pour un livre pour enfants, {style_images}, personnages constants."
            # image_paths = edit_images_with_dalle(
            #     paragraphs, style, "story_id_placeholder", selected_perso
            # )
            display_story_with_images(image_paths, paragraphs)
            save_story(generated_story, theme, user_keywords, users, image_paths)

    elif mode == "histoires enregistrées":
        load_stories(
            st.session_state["users"],
            st.session_state["username"],
            st.session_state["all_stories"],
        )

    if st.sidebar.button("Quitter"):
        st.session_state["authenticated"] = False
        st.session_state["username"] = None
        st.rerun()


def generate_story(theme, user_keywords, users, personnages, selected_perso):
    """
    Génère une histoire en appelant l'API OpenAI avec les paramètres.
    """

    messages = make_prompt(
        theme,
        user_keywords,
        users[username]["age"],
        users[username]["sexe"],
        personnages,
        selected_perso,
    )
    response = openai.ChatCompletion.create(
        model="gpt-4", messages=messages, max_tokens=4000, temperature=0.7
    )
    generated_story = response.choices[0].message["content"]
    return generated_story


def display_story_with_images(image_paths, paragraphs):
    """
    Affiche le texte avec les images correspondantes sous chaque paragraphe.
    """
    for i, paragraph in enumerate(paragraphs):
        st.write(paragraph.strip())  # Affiche le paragraphe
        if (
            image_paths and i < len(image_paths) and image_paths[i]
        ):  # Vérifie si une image est disponible
            st.image(image_paths[i], caption="Illustration", use_container_width=True)


def save_story(story, theme, keywords, users, image_paths):
    """
    Sauvegarde une histoire dans le fichier JSON avec le titre comme clé et synchronise avec Google Drive.
    """
    try:
        # Extraction et nettoyage du titre
        raw_title = story.split("\n")[0].replace("Titre : ", "").strip()
        title = re.sub(
            r'[\\/:"*?<>|]', "", raw_title
        )  # Supprime les caractères non valides

        # Générer un ID unique pour l'histoire
        story_id = title + "_" + uuid.uuid4().hex

        # Nouvelle histoire
        new_story = {
            "theme": theme,
            "keywords": keywords,
            "age": users[st.session_state["username"]].get("age", ""),
            "sexe": users[st.session_state["username"]].get("sexe", ""),
            "title": title,
            "story": story,
            "images": image_paths,
            "story_id": story_id,
        }

        # Charger toutes les histoires
        stories = st.session_state["all_stories"]

        # Ajouter ou mettre à jour l'histoire
        stories[title] = new_story

        # Sauvegarde locale
        with open("json/stories.json", "w") as f:
            json.dump(stories, f, indent=4, ensure_ascii=False)

        try:
            with open("json/stories_users.json", "r") as f:
                stories_users = json.load(f)
        except FileNotFoundError:
            stories_users = {}

        if st.session_state["username"] not in stories_users:
            stories_users[st.session_state["username"]] = []

        if title not in stories_users[st.session_state["username"]]:
            stories_users[st.session_state["username"]].append(title)

        with open("json/stories_users.json", "w") as f:
            json.dump(stories_users, f, indent=4, ensure_ascii=False)

        # Mise à jour sur AWS
        save_json_to_s3(stories, "my-bucket-name", "stories.json")
        save_json_to_s3(stories_users, "my-bucket-name", "stories_users.json")

    except Exception as e:
        st.error(f"Erreur lors de la sauvegarde de l'histoire : {e}")


if __name__ == "__main__":

    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False
        st.session_state["username"] = None

    if st.session_state["authenticated"]:
        username = st.session_state["username"]
        main_app(st.session_state["users"], st.session_state["personnages"])

    else:
        st.sidebar.title("Navigation")
        page = st.sidebar.radio(
            "Accès à l'application",
            ["Connexion", "Créer un compte", "Mot de passe oublié"],
        )
        if page == "Connexion":
            login_page()
        elif page == "Créer un compte":
            create_account_page()
        elif page == "Mot de passe oublié":
            forgot_password_page()
