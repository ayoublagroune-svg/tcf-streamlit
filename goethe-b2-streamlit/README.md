# Goethe-Zertifikat B2 Trainer

Application Streamlit pour préparer le Goethe-Zertifikat B2.

La structure suit le format B2 actuel :

- Lesen : 5 parties, 65 minutes
- Hören : 4 parties, environ 40 minutes
- Schreiben : 2 tâches, 75 minutes
- Sprechen : 2 parties, environ 15 minutes

Les tâches sont originales et conçues pour l'entraînement. Elles ne copient pas les sujets officiels Goethe.

## Fonctionnalités

- Examen blanc complet
- Entraînement par module
- Banque locale : 150 items Lesen, 150 items Hören, sujets Schreiben et Sprechen
- Audio d'entraînement via synthèse vocale navigateur pour Hören
- Correction locale de secours pour fonctionner sans clé API
- Explication IA optionnelle des QCM : signification de la bonne réponse, règle de langue ou stratégie, tips en allemand et arabe classique
- Correction IA optionnelle de Schreiben avec feedback bilingue, règles utiles, erreurs corrigées, version améliorée et conseils
- Tableau de bord par module
- Export PDF, CSV et JSON

## Installation locale

```bash
pip install -r requirements.txt
streamlit run app.py
```

## IA optionnelle

L'application fonctionne sans clé API. Aucun appel IA ne part automatiquement.

Pour activer l'IA, ajoutez dans les secrets Streamlit :

```toml
OPENAI_API_KEY = "sk-..."
OPENAI_MODEL = "gpt-4.1-mini"
```

Puis activez le bouton `KI aktivieren` dans la barre latérale. Les appels IA sont déclenchés uniquement par les boutons dédiés :

- `KI-Erklärung: Bedeutung, Regel und Tipps` dans la correction des QCM
- `Mit KI korrigieren` dans le module Schreiben

## Déploiement Streamlit Cloud

Pour publier la version B2, configurez l'application Streamlit Cloud avec :

- Repository : `ayoublagroune-svg/tcf-streamlit`
- Branch : `main`
- Main file path : `goethe-b2-streamlit/app.py`
- Secrets : `OPENAI_API_KEY` seulement si vous voulez utiliser le Mode IA

Si une app existe déjà avec le fichier B1, changez seulement le champ `Main file path` vers `goethe-b2-streamlit/app.py`, puis relancez le déploiement.

## Sources de format

Le format est basé sur les informations publiques du Goethe-Institut :

- Module Lesen : 5 parties, 65 minutes
- Module Hören : environ 40 minutes
- Module Schreiben : 2 tâches, 75 minutes
- Module Sprechen : 2 parties, environ 15 minutes

Sources officielles :

- https://www.goethe.de/ins/de/de/prf/prf/gzb2/wi9.html
- https://bfu.goethe.de/b2_mod_2MX6/lesen.php
- https://bfu.goethe.de/b2_mod_2MX6/sprechen.php
