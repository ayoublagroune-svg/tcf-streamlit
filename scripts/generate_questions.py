"""Optional pipeline for generating original TCF-style questions with AI.

The Streamlit app does not depend on this script. It is a starting point for
expanding data/questions.json when OPENAI_API_KEY is configured.
"""

import json
import os
from pathlib import Path


PROMPT = """
Génère des questions originales de préparation TCF, de niveau équivalent à
l'examen, sans copier de contenu officiel. Les questions doivent respecter le
niveau CECRL indiqué, avoir 4 choix, une seule bonne réponse, une explication
pédagogique et un contexte réaliste.
"""


def main():
    if not os.getenv("OPENAI_API_KEY"):
        print("OPENAI_API_KEY absente: génération désactivée.")
        return
    try:
        from openai import OpenAI
    except ImportError:
        print("Installez openai pour utiliser ce script.")
        return

    client = OpenAI()
    response = client.chat.completions.create(
        model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        temperature=0.4,
        messages=[
            {"role": "system", "content": "Tu produis uniquement du JSON valide."},
            {"role": "user", "content": PROMPT + "\nGénère 10 questions B2 de compréhension écrite au schéma de l'app."},
        ],
    )
    output_path = Path("data/generated_questions_preview.json")
    output_path.write_text(response.choices[0].message.content, encoding="utf-8")
    print(f"Aperçu écrit dans {output_path}")


if __name__ == "__main__":
    main()
