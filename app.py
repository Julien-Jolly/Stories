import streamlit as st
from users import login_page, create_account_page, forgot_password_page, load_personnages
import openai
import os
import make_prompt
import json
from dotenv import load_dotenv
import requests
import re

load_dotenv()

openai.api_key = os.getenv("OPENAI_API_KEY")

personnages = load_personnages()

def summarize_paragraph(paragraph, max_length=1000):
    """
    Génère un résumé court d'un paragraphe en utilisant l'API OpenAI.
    Tronque le résumé à max_length caractères si nécessaire.
    """
    try:
        print("réduction paragraphes pour prompt image")
        response = openai.ChatCompletion.create(
            model="gpt-4",
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


def generate_images_with_summaries(paragraphs, style, story_id, personnage):
    """
    Génère des images à partir des paragraphes tout en conservant l'apparence physique du personnage
    en se basant sur une image source.
    """
    summarized_prompts = []
    for paragraph in paragraphs:
        print("Réduction des paragraphes pour prompt image")
        summarized_prompt = summarize_paragraph(paragraph)

        if isinstance(personnage, list):
            personnage_description = " ".join([personnages[p]["description"] for p in personnage])
        else:
            personnage_description = personnages[personnage]["description"]

        image_reference_path = os.path.join("images_source", f"zouzou.png")
        image_reference_text = f"Basé sur l'image initiale du personnage située dans {image_reference_path}."
        full_prompt = f"{image_reference_text} {personnage_description} {summarized_prompt} {style}"

        summarized_prompts.append(full_prompt[:1000])
        print("Réduction des paragraphes pour prompt image... terminé")

    image_urls = []
    for summarized_prompt in summarized_prompts:
        try:
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[
                    {
                        "role": "system",
                        "content": "Tu es un assistant expert en génération d'images.",
                    },
                    {
                        "role": "user",
                        "content": f"Crée une illustration basée sur le texte suivant : {summarized_prompt}",
                    },
                ],
                functions=[
                    {
                        "name": "generate_image",
                        "description": "Génère une image basée sur une description textuelle.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "prompt": {"type": "string"},
                                "size": {"type": "string", "enum": ["256x256"]},
                            },
                            "required": ["prompt", "size"],
                        },
                    }
                ],
                function_call={"name": "generate_image"},
            )
            print("Réponse brute de l'API :", response)
            arguments = json.loads(response.choices[0].message["function_call"]["arguments"])
            prompt = arguments["prompt"]
            size = arguments["size"]
            image_response = openai.Image.create(prompt=prompt, size=size, n=1)
            image_url = image_response["data"][0]["url"]
            image_urls.append(image_url)
        except Exception as e:
            print(f"Erreur lors de la génération de l'image : {e}")
            image_urls.append(None)

    image_paths = []
    for index, image_url in enumerate(image_urls):
        if image_url:
            image_path = save_image(image_url, story_id, index + 1)
            image_paths.append(image_path)
            print(f"Image {index + 1} sauvegardée : {image_path}")
        else:
            image_paths.append(None)
    return image_paths


def generate_images_for_paragraphs(paragraphs, style, story_id):
    """
    Génère et stocke toutes les images en une seule requête.
    Retourne une liste des chemins des images locales.
    """
    image_urls = generate_images_with_summaries(paragraphs, style)
    image_paths = []

    for index, image_url in enumerate(image_urls):
        if image_url:
            image_path = save_image(image_url, story_id, index + 1)
            image_paths.append(image_path)
        else:
            image_paths.append(None)  # Si une image n'est pas générée
    return image_paths


def options(theme_list, mode_list, style_images, personnage_names):
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

    style_images = st.sidebar.selectbox(
        "Quel style souhaites-tu pour les images ?", style_images, key="selected_style"
    )

    st.sidebar.markdown("<br><br>", unsafe_allow_html=True)

    user_keywords = st.sidebar.text_area(
        "Entre ici les mots-clés pour orienter le récit", key="user_input"
    )

    st.sidebar.markdown("<br><br>", unsafe_allow_html=True)

    return theme, mode, user_keywords, style_images, selected_perso


def load_stories(username):
    """
    Charge et affiche les histoires enregistrées pour un utilisateur donné.
    """
    try:
        with open("json/users.json", "r") as user_file:
            users = json.load(user_file)

        if username not in users or "stories" not in users[username]:
            st.warning("Aucune histoire enregistrée pour cet utilisateur.")
            return

        with open("json/stories.json", "r") as stories_file:
            all_stories = json.load(stories_file)

        user_story_titles = users[username]["stories"]
        for story_title in user_story_titles:
            story = all_stories.get(story_title)
            if story:
                with st.expander(story.get("title", "Titre manquant")):
                    st.write(story.get("story", "Contenu manquant"))
            else:
                st.warning(f"Histoire avec le titre '{story_title}' introuvable.")
    except Exception as e:
        st.error(f"Erreur lors du chargement des histoires : {e}")


def main_app(users):
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
        theme_list, mode_list, style_images, personnage_names
    )
    print(f"selection {selected_perso}")

    if mode == "nouvelle histoire":
        if st.sidebar.button("Lancer"):
            generated_story = generate_story(theme, user_keywords, users, selected_perso)
            image_paths = ""

            paragraphs = generated_story.split("\n\n")
            style = f"Illustration pour un livre pour enfants, {style_images}, personnages constants."
            display_story_with_images(generated_story, image_paths)
            st.write(generated_story)
            save_story(generated_story, theme, user_keywords, users, image_paths)

    elif mode == "histoires enregistrées":
        load_stories(st.session_state['username'])

    if st.sidebar.button("Quitter"):
        st.session_state["authenticated"] = False
        st.session_state["username"] = None
        st.rerun()


def generate_story(theme, user_keywords, users, selected_perso):
    """
    Génère une histoire en appelant l'API OpenAI avec les paramètres.
    """

    messages = make_prompt.make_prompt(
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


def generate_image(prompt, size="256x256", n=1):
    try:
        response = openai.Image.create(prompt=prompt, n=n, size=size)
        # Récupère l'URL de la première image générée
        image_url = response["data"][0]["url"]
        print("Image URL:", image_url)
        return image_url
    except Exception as e:
        print("Erreur lors de la génération de l'image:", e)
        return None


def display_story_with_images(story, image_paths):
    """
    Affiche le texte avec les images correspondantes sous chaque paragraphe.
    """
    paragraphs = story.split("\n\n")
    for paragraph, image_path in zip(paragraphs, image_paths):
        st.write(paragraph.strip())
        if image_path:
            st.image(image_path, caption="Illustration", use_container_width=True)
        else:
            st.write("(Illustration non disponible)")


def save_story(story, theme, keywords, users, image_paths):
    """
    Sauvegarde une histoire dans le fichier JSON avec le titre comme clé.
    Nettoie le titre pour éviter les caractères non souhaités.
    """
    try:
        # Extraction et nettoyage du titre
        raw_title = story.split("\n")[0].replace("Titre : ", "").strip()
        title = re.sub(r'[\\/:"*?<>|]', "", raw_title)  # Enlève les caractères non valides pour un nom de fichier

        new_story = {
            "theme": theme,
            "keywords": keywords,
            "age": users[st.session_state["username"]].get("age", ""),
            "sexe": users[st.session_state["username"]].get("sexe", ""),
            "title": title,
            "story": story,
            "images": image_paths,
        }

        # Charger les histoires existantes
        with open("json/stories.json", "r") as stories_file:
            all_stories = json.load(stories_file)

        # Ajouter ou mettre à jour l'histoire
        all_stories[title] = new_story

        # Sauvegarder les histoires mises à jour
        with open("json/stories.json", "w") as stories_file:
            json.dump(all_stories, stories_file, indent=4, ensure_ascii=False)

        # Ajouter le titre de l'histoire à l'utilisateur
        with open("json/users.json", "r") as user_file:
            users_data = json.load(user_file)

        if title not in users_data[st.session_state["username"]]["stories"]:
            users_data[st.session_state["username"]]["stories"].append(title)

        with open("json/users.json", "w") as user_file:
            json.dump(users_data, user_file, indent=4, ensure_ascii=False)

        st.success(f"Histoire '{title}' sauvegardée avec succès !")

    except Exception as e:
        st.error(f"Erreur lors de la sauvegarde de l'histoire : {e}")


def save_image(image_url, story_id, paragraph_index):
    """
    Télécharge et enregistre une image à partir de son URL.
    Les images sont stockées dans le dossier 'images/' avec un nom unique.
    """
    images_dir = "images"
    os.makedirs(images_dir, exist_ok=True)  # Crée le dossier s'il n'existe pas

    image_path = os.path.join(
        images_dir, f"story_{story_id}_image_{paragraph_index}.png"
    )

    try:
        response = requests.get(image_url)
        response.raise_for_status()  # Vérifie si la requête a réussi
        with open(image_path, "wb") as f:
            f.write(response.content)
        return image_path
    except Exception as e:
        print(f"Erreur lors du téléchargement de l'image : {e}")
        return None


if __name__ == "__main__":

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