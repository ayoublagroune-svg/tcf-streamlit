# Goethe-Zertifikat B1 Trainer

Application Streamlit pour préparer le Goethe-Zertifikat B1.

La structure suit les modules officiels :

- Lesen : 5 parties, 65 minutes
- Hören : 4 parties, 40 minutes
- Schreiben : 3 tâches, 60 minutes
- Sprechen : 3 parties, environ 15 minutes

Les tâches sont originales et conçues pour l'entraînement. Elles ne copient pas les sujets officiels Goethe.

## Fonctionnalités

- Examen blanc complet
- Entraînement par module
- Banque locale : 150 items Lesen, 150 items Hören, sujets Schreiben et Sprechen
- Audio d'entraînement via synthèse vocale navigateur
- Correction pédagogique avec explications en allemand et arabe classique
- Tableau de bord par module
- Export PDF, CSV et JSON
- IA optionnelle désactivée par défaut pour corriger Schreiben

## Installation locale

```bash
pip install -r requirements.txt
streamlit run app.py
```

## IA optionnelle

L'application fonctionne sans clé API.

Pour activer l'IA, ajoutez dans les secrets Streamlit :

```toml
OPENAI_API_KEY = "sk-..."
OPENAI_MODEL = "gpt-4.1-mini"
```

Puis activez le bouton `KI aktivieren` dans la barre latérale.

## Sources de format

Le format est basé sur les informations publiques du Goethe-Institut :

- Module Lesen : 5 parties, 65 minutes
- Module Hören : 4 parties, 40 minutes
- Module Schreiben : 3 tâches
- Module Sprechen : 3 tâches

Sources officielles :

- https://bfu.goethe.de/b1_mod/lesen.php
- https://bfu.goethe.de/b1_mod/hoeren.php
- https://bfu.goethe.de/b1_mod/schreiben.php
- https://bfu.goethe.de/b1_mod/sprechen.php
