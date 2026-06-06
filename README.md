# TCF Tout Public - Examen Blanc

Application Streamlit d'entraînement au TCF Tout Public pour un candidat B1 visant B2.

## Fonctionnalités

- Examen blanc complet avec les sections du TCF TP
- Entraînement par compétence
- Chronomètre par section avec progression
- Sauvegarde automatique des réponses pendant la session
- Correction pédagogique question par question
- Analyse des points faibles par thème
- Tableau de bord avec graphiques Plotly
- Export PDF, CSV et JSON
- Historique local dans la session Streamlit

## Installation locale

1. Créer un environnement Python 3.10+.
2. Installer les dépendances :

```bash
pip install -r requirements.txt
```

3. Lancer l'application :

```bash
streamlit run app.py
```

## Création du dépôt GitHub

1. Créer un nouveau dépôt sur GitHub.
2. Ajouter les fichiers du projet :

```bash
git init
git add .
git commit -m "Initial TCF training app"
git branch -M main
git remote add origin https://github.com/votre-compte/votre-depot.git
git push -u origin main
```

## Déploiement sur Streamlit Cloud

1. Aller sur [Streamlit Cloud](https://streamlit.io/cloud).
2. Connecter le compte GitHub.
3. Choisir le dépôt.
4. Définir le fichier principal sur `app.py`.
5. Cliquer sur Deploy.

Aucune clé API n'est nécessaire.

## Mise à jour de la banque de questions

Les questions sont dans `questions.json`.

Chaque question suit ce format :

```json
{
  "id": "SL_001",
  "section": "structures_langue",
  "theme": "passe_compose",
  "niveau": "B1",
  "consigne": "Choisissez la bonne réponse.",
  "texte": "Hier, elle ___ au marché.",
  "choix": {
    "A": "va",
    "B": "ira",
    "C": "est allée",
    "D": "allait"
  },
  "bonne_reponse": "C",
  "explication": "L'indicateur 'hier' demande une action terminée au passé.",
  "rappel_regle": "Le passé composé exprime une action terminée dans le passé.",
  "astuce_tcf": "Repérez les mots comme hier, la semaine dernière ou ce matin."
}
```

Pour ajouter un futur fichier audio, ajouter par exemple un champ `audio_url` ou `audio_file` aux questions de compréhension orale. L'application affichera déjà les scripts sous la forme "Vous entendez : ...".

## Partage du lien public

Après le déploiement, copier l'URL fournie par Streamlit Cloud et l'envoyer aux candidats. Ils pourront passer le test directement dans leur navigateur.
