# TCF Trainer - Objectif B2, C1 et plus

Application Streamlit d'entraînement au TCF Tout Public pour progresser vers B2, C1 et des usages avancés du français.

L'application fonctionne d'abord avec la banque locale `questions.json`. Une couche IA optionnelle peut être activée pour une utilisation personnelle à coût minimal, uniquement via des boutons explicites.

## Fonctionnalités

- Examen blanc complet avec les sections du TCF TP
- Banque locale de 300 QCM, équilibrée entre compréhension orale, structures de la langue et compréhension écrite
- Entraînement par compétence
- Chronomètre par section avec progression
- Sauvegarde automatique des réponses pendant la session
- Correction pédagogique question par question
- Analyse des points faibles par thème
- Section "Mes erreurs fréquentes"
- Retest ciblé d'une erreur avec 3 questions similaires générées par IA, si le Mode IA est activé
- Correction IA optionnelle de l'expression écrite, déclenchée uniquement par bouton
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

## Mode IA optionnel

Le Mode IA est désactivé par défaut dans le code avec :

```python
AI_ENABLED = False
```

Même avec une clé API configurée, aucun appel IA n'est lancé automatiquement. L'utilisateur doit activer "Mode IA" dans la barre latérale, puis cliquer sur un bouton dédié.

Contrôles de coût inclus :

- limite de 10 appels IA par session
- génération limitée à 3 questions similaires pour un retest
- cache de session pour éviter de régénérer la même réponse IA
- entrées tronquées avant envoi au modèle
- banque `questions.json` conservée comme source principale

### Configurer une clé API

Sur Streamlit Cloud, ajouter dans les secrets de l'application :

```toml
OPENAI_API_KEY = "sk-..."
OPENAI_MODEL = "gpt-5-mini"
```

En local, vous pouvez aussi utiliser des variables d'environnement :

```bash
export OPENAI_API_KEY="sk-..."
export OPENAI_MODEL="gpt-5-mini"
```

`OPENAI_MODEL` est optionnel. Si la variable est absente, l'application utilise le modèle défini dans `AI_DEFAULT_MODEL`.

### Désactiver totalement l'IA

Pour utiliser seulement `questions.json`, ne configurez pas `OPENAI_API_KEY` et laissez `AI_ENABLED = False`.

Vous pouvez aussi ne jamais activer "Mode IA" dans la barre latérale. Les examens, corrections pédagogiques, graphiques et exports continuent de fonctionner sans clé API.

## Déploiement sur Streamlit Cloud

1. Aller sur [Streamlit Cloud](https://streamlit.io/cloud).
2. Connecter le compte GitHub.
3. Choisir le dépôt.
4. Définir le fichier principal sur `app.py`.
5. Ajouter les secrets OpenAI seulement si vous voulez activer le Mode IA.
6. Cliquer sur Deploy.

Aucune clé API n'est nécessaire pour le mode gratuit basé sur `questions.json`.

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
