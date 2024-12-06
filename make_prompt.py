
def make_prompt(theme, user_keywords, age, sexe):
    messages = [
        {
            "role": "system",
            "content": "Tu es un assistant qui crée des histoires originales et adaptées aux enfants."
        },
        {
            "role": "user",
            "content": f"""Peux-tu écrire une histoire originale en français, d'environ 1000 mots (pas moins de 900), pour un enfant ?

Critères :
- Thème : {theme}
- Mots-clés : {user_keywords}
- Âge de l'enfant : {age} ans
- Sexe de l'enfant : {sexe}

L'histoire ne doit pas être trop proche des contes classiques traditionnels, mais rester compréhensible et adaptée à l'âge indiqué. Intègre les mots-clés.
J'aimerais que tu insères une illustration tous les 100 mots environ, au format [ILLUSTRATION : description de l'image].
À la fin, remets le tout dans un fichier texte lisible par un enfant. Ne termine pas par “Fin de l’histoire” ni par des crédits d’illustration ou d’auteur. Arrête l’histoire après la dernière phrase, sans ajouter d’autre mention. Et assures toi bien qu'on est proche des 1000 mots (pas moins de 900)"""
        }
    ]
    return messages