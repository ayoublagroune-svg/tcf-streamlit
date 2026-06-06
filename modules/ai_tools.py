import os


def detect_ai_available():
    openai_ready = bool(os.getenv("OPENAI_API_KEY"))
    azure_ready = all(
        os.getenv(name)
        for name in ("AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_API_KEY", "AZURE_OPENAI_DEPLOYMENT")
    )
    return openai_ready or azure_ready


def _client():
    try:
        from openai import AzureOpenAI, OpenAI
    except ImportError:
        return None, None

    if all(os.getenv(name) for name in ("AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_API_KEY", "AZURE_OPENAI_DEPLOYMENT")):
        return AzureOpenAI(
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21"),
        ), os.getenv("AZURE_OPENAI_DEPLOYMENT")
    if os.getenv("OPENAI_API_KEY"):
        return OpenAI(api_key=os.getenv("OPENAI_API_KEY")), os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    return None, None


def correct_writing(prompt, text):
    if not detect_ai_available():
        return {
            "available": False,
            "estimated_level": "Non estimé",
            "feedback": "Correction IA désactivée: aucune clé OpenAI ou Azure OpenAI n'est configurée.",
        }
    client, model = _client()
    if not client:
        return {"available": False, "estimated_level": "Non estimé", "feedback": "Package OpenAI non installé."}

    response = client.chat.completions.create(
        model=model,
        temperature=0.2,
        messages=[
            {
                "role": "system",
                "content": (
                    "Tu es correcteur TCF. Donne un feedback concis en français avec: grammaire, vocabulaire, "
                    "cohérence, structure, niveau CECRL estimé et version améliorée."
                ),
            },
            {"role": "user", "content": f"Sujet: {prompt}\n\nProduction:\n{text[:6000]}"},
        ],
    )
    feedback = response.choices[0].message.content
    return {"available": True, "estimated_level": "À lire dans le feedback", "feedback": feedback}


def generate_revision_plan(stats):
    weak = stats.get("frequent_errors", [])
    if not weak:
        return ["Passer un examen blanc court.", "Revoir les connecteurs logiques.", "Faire une production écrite B2."]
    return [f"Travailler {name} avec 10 questions ciblées." for name, _count in weak]


def generate_targeted_questions(*_args, **_kwargs):
    return []
