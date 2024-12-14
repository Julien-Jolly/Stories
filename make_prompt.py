def make_prompt(theme, user_keywords, age, sexe, personnages, selected_perso):
    # Concaténer les descriptions des personnages sélectionnés
    personnages_descriptions = ', '.join([personnages[p]['description'] for p in selected_perso])

    messages = [
        {
            "role": "system",
            "content": "Tu es un assistant qui crée des histoires originales, captivantes, dont l'histoire diffère des contes traditionnels mais peut s'en inspirer et adaptées aux enfants."
        },
        {
            "role": "user",
            "content": f"""Peux-tu écrire une histoire originale en français, d'environ 2000 mots (pas moins de 1700) avec au maximum 6 paragraphes, pour un enfant ?

Critères :
- Thème : {theme}
- Personnages principaux : {personnages_descriptions}
- Mots-clés : {user_keywords}
- Âge de l'enfant : {age} ans
- Sexe de l'enfant : {sexe}

Donnes le titre au début de l'histoire
L'histoire ne doit pas être trop proche des contes classiques traditionnels, mais rester compréhensible et adaptée à l'âge indiqué. Intègre les mots-clés.
Ne termine pas par “Fin de l’histoire” ni par des crédits d’illustration ou d’auteur. Arrête l’histoire après la dernière phrase, sans ajouter d’autre mention. Et assures toi bien qu'on est proche des 2000 mots (pas moins de 1700)."""
        }
    ]
    return messages