# TCF Coach IA

TCF Coach IA est un MVP Streamlit de préparation au TCF. L'application propose des examens blancs chronométrés, un entraînement par compétence, une correction pédagogique, un suivi utilisateur et une logique Free/Premium.

Application indépendante, non affiliée à France Éducation international. Les questions sont originales et conçues pour être de niveau équivalent au TCF. Les niveaux CECRL affichés sont des estimations non officielles.

## Fonctionnalités

- Landing page produit avec accès gratuit et offre Premium
- Inscription, connexion, déconnexion et session utilisateur Streamlit
- Mots de passe hashés avec `passlib[bcrypt]`, avec fallback PBKDF2 si passlib est absent
- Base SQLite locale dans `data/tcf_coach.db`
- Dashboard: score moyen, derniers examens, progression par compétence, niveau estimé, erreurs fréquentes et recommandations
- Mode entraînement par compétence et niveau
- Examen blanc court avec temps limité, correction en fin d'épreuve et sauvegarde
- Expression écrite avec correction IA optionnelle
- Paywall MVP: limites gratuites et message de montée en gamme
- Stripe optionnel, sans bloquer l'app si les variables sont absentes
- OpenAI ou Azure OpenAI optionnels, sans bloquer l'app si les clés sont absentes

## Installation

```bash
pip install -r requirements.txt
```

## Lancement local

```bash
streamlit run app.py
```

Puis ouvrir l'URL affichée par Streamlit, généralement `http://localhost:8501`.

## Configuration

Copier `.env.example` si vous utilisez un chargeur d'environnement local, ou définir les variables dans Streamlit Cloud.

### IA optionnelle

OpenAI standard:

```bash
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4.1-mini
```

Azure OpenAI:

```bash
AZURE_OPENAI_ENDPOINT=https://...
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_DEPLOYMENT=...
AZURE_OPENAI_API_VERSION=2024-10-21
```

Sans ces variables, la correction écrite IA affiche un état désactivé proprement.

### Stripe optionnel

```bash
STRIPE_SECRET_KEY=sk_live_or_test...
STRIPE_PRICE_ID=price_...
APP_BASE_URL=http://localhost:8501
```

Sans Stripe, la page Premium affiche `Paiement bientôt disponible`.

## Structure projet

```text
app.py
modules/auth.py
modules/db.py
modules/paywall.py
modules/scoring.py
modules/questions.py
modules/ai_tools.py
modules/ui.py
modules/exam_engine.py
data/questions.json
data/tcf_blueprint.json
scripts/generate_questions.py
.env.example
requirements.txt
README.md
```

## Données

`data/questions.json` contient 300 questions originales converties au schéma MVP:

- 100 compréhension orale
- 100 structure de la langue
- 100 compréhension écrite

Chaque question contient `id`, `skill`, `level`, `difficulty_score`, `type`, `prompt`, `context`, `choices`, `correct_answer`, `explanation`, `estimated_time_seconds` et `tags`.

`data/tcf_blueprint.json` décrit les compétences, niveaux et types de questions cibles pour guider l'expansion de la banque.

## Génération de questions

Le script `scripts/generate_questions.py` prépare le pipeline IA pour générer de nouvelles questions originales si `OPENAI_API_KEY` est disponible.

```bash
python scripts/generate_questions.py
```

Objectif produit: étendre progressivement la banque à 1000 questions, avec une bonne répartition par compétence.

## Roadmap

- Brancher un vrai checkout Stripe et un webhook Premium
- Ajouter une page administrateur pour gérer les questions
- Générer au moins 100 questions A2 supplémentaires
- Ajouter des audios réels pour la compréhension orale
- Améliorer le modèle de scoring avec pondération par difficulté
- Export PDF des rapports d'examen
- Plans de révision personnalisés via IA

## Tests manuels recommandés

- `streamlit run app.py` démarre
- Inscription et connexion fonctionnent
- Le dashboard s'affiche après connexion
- Un utilisateur gratuit est limité par les quotas quotidiens
- L'entraînement sauvegarde les tentatives
- L'examen blanc sauvegarde le résultat
- L'expression écrite reste utilisable sans clé IA
- La page Premium reste utilisable sans Stripe
