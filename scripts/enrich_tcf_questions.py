"""Add original TCF-style questions with progressive difficulty.

The content is original and designed for training. It does not copy official
TCF items. Run from the repository root:

    python3 scripts/enrich_tcf_questions.py
"""

import json
from pathlib import Path


QUESTIONS_PATH = Path("questions.json")


def qid(section, level, index):
    prefixes = {
        "comprehension_orale": "COX",
        "structures_langue": "SLX",
        "comprehension_ecrite": "CEX",
    }
    return f"{prefixes[section]}_{level}_{index:03d}"


def make_question(section, level, index, theme, consigne, texte, choix, bonne, explication, rappel, astuce):
    return {
        "id": qid(section, level, index),
        "section": section,
        "theme": theme,
        "niveau": level,
        "consigne": consigne,
        "texte": texte,
        "choix": choix,
        "bonne_reponse": bonne,
        "explication": explication,
        "rappel_regle": rappel,
        "astuce_tcf": astuce,
    }


ORAL_SCENARIOS = [
    (
        "A2",
        "annonce_pratique",
        "Annonce : Le cours de français de ce soir est déplacé en salle 204, au deuxième étage.",
        {"A": "Le cours est annulé.", "B": "Le cours change de salle.", "C": "Le cours commence demain.", "D": "Le cours est en ligne."},
        "B",
        "L'information principale est le changement de salle.",
    ),
    (
        "A2",
        "dialogue_quotidien",
        "Dialogue : Tu peux acheter du pain en rentrant ? Je prépare le dîner mais je n'ai plus le temps de sortir.",
        {"A": "La personne demande un achat.", "B": "La personne refuse de dîner.", "C": "La personne cherche son sac.", "D": "La personne part au travail."},
        "A",
        "Acheter du pain est la demande principale.",
    ),
    (
        "B1",
        "message_vocal",
        "Message vocal : Bonjour, votre dossier est complet. Vous recevrez une réponse par courrier dans un délai de deux semaines.",
        {"A": "Le dossier manque de documents.", "B": "La réponse sera donnée immédiatement.", "C": "Le dossier est complet.", "D": "Il faut revenir demain."},
        "C",
        "Le message indique clairement que le dossier est complet.",
    ),
    (
        "B1",
        "consigne_transport",
        "Annonce dans le métro : En raison d'un incident technique, les voyageurs pour Nation sont invités à emprunter la ligne 2.",
        {"A": "Il faut changer de ligne.", "B": "La station Nation est fermée définitivement.", "C": "La ligne 2 est annulée.", "D": "Le métro circule normalement."},
        "A",
        "Les voyageurs sont orientés vers une autre ligne.",
    ),
    (
        "B2",
        "opinion_nuancee",
        "Interview : Le numérique facilite certaines démarches, mais il risque aussi d'exclure les personnes peu à l'aise avec les outils en ligne.",
        {"A": "La personne rejette totalement le numérique.", "B": "La personne présente une opinion nuancée.", "C": "La personne parle d'un loisir.", "D": "La personne annonce une panne."},
        "B",
        "Elle donne un avantage puis une limite.",
    ),
    (
        "B2",
        "implicite_oral",
        "Conversation : J'aurais aimé accepter ce poste, mais déménager si loin avec les enfants, ce n'est pas réaliste pour l'instant.",
        {"A": "La personne accepte le poste.", "B": "La personne hésite encore sans raison.", "C": "La personne refuse pour des raisons familiales.", "D": "La personne ne cherche pas de travail."},
        "C",
        "Le refus est implicite et lié à la famille.",
    ),
    (
        "C1",
        "chronique_radio",
        "Chronique : On présente souvent la ville durable comme une évidence, alors qu'elle suppose des arbitrages coûteux entre mobilité, logement et justice sociale.",
        {"A": "Le chroniqueur défend une solution simple.", "B": "Le chroniqueur souligne la complexité du sujet.", "C": "Le chroniqueur parle seulement de transports.", "D": "Le chroniqueur nie l'existence des villes."},
        "B",
        "Le mot arbitrages et l'opposition montrent une analyse complexe.",
    ),
    (
        "C1",
        "intention_locuteur",
        "Débat : Dire que la réforme est imparfaite ne signifie pas qu'il faille l'abandonner ; cela oblige surtout à en corriger les effets les plus injustes.",
        {"A": "La personne veut supprimer la réforme.", "B": "La personne demande une amélioration ciblée.", "C": "La personne refuse toute critique.", "D": "La personne change de sujet."},
        "B",
        "La critique sert à proposer une correction, pas un abandon.",
    ),
]


STRUCTURE_SCENARIOS = [
    ("A2", "prepositions", "Je vais ___ médecin demain matin.", {"A": "chez le", "B": "à la", "C": "dans le", "D": "sur le"}, "A", "On dit aller chez le médecin."),
    ("A2", "temps_present", "Tous les lundis, elle ___ au marché.", {"A": "va", "B": "ira", "C": "allait", "D": "est allée"}, "A", "Une habitude au présent demande va."),
    ("A2", "articles", "Il cherche ___ appartement près de la gare.", {"A": "un", "B": "une", "C": "des", "D": "du"}, "A", "Appartement est masculin singulier."),
    ("A2", "negation", "Je ___ connais pas cette adresse.", {"A": "ne", "B": "n'", "C": "pas", "D": "plus"}, "A", "Avec connaître, on écrit je ne connais pas."),
    ("B1", "passe_compose_imparfait", "Il ___ quand son téléphone a sonné.", {"A": "lisait", "B": "lira", "C": "lit", "D": "a lu"}, "A", "L'imparfait décrit l'action en cours interrompue."),
    ("B1", "pronoms", "Ce livre, je ___ ai parlé à mon professeur.", {"A": "lui", "B": "en", "C": "y", "D": "le"}, "B", "Parler de quelque chose devient en parler."),
    ("B1", "discours_indirect", "Elle dit qu'elle ___ demain.", {"A": "viendra", "B": "vient", "C": "venait", "D": "est venue"}, "A", "Demain renvoie au futur dans le discours indirect au présent."),
    ("B1", "condition", "S'il pleut, nous ___ la visite.", {"A": "reporterons", "B": "reportions", "C": "aurions reporté", "D": "reporter"}, "A", "Si + présent appelle souvent le futur simple."),
    ("B2", "connecteurs", "Le projet est intéressant ; ___, son coût reste difficile à justifier.", {"A": "cependant", "B": "donc", "C": "parce que", "D": "ainsi"}, "A", "Cependant marque une opposition."),
    ("B2", "subjonctif", "Il faut que chaque candidat ___ une pièce d'identité.", {"A": "présente", "B": "présentera", "C": "présentait", "D": "a présenté"}, "A", "Il faut que est suivi du subjonctif."),
    ("B2", "hypothese", "Si nous avions reçu le dossier plus tôt, nous l'___ déjà traité.", {"A": "aurions", "B": "avons", "C": "allons", "D": "étions"}, "A", "L'hypothèse irréelle du passé appelle le conditionnel passé."),
    ("B2", "relatifs", "Le rapport ___ je fais référence a été publié hier.", {"A": "auquel", "B": "lequel", "C": "duquel", "D": "qui"}, "A", "Faire référence à demande auquel."),
    ("C1", "nuance_lexicale", "La mesure a été accueillie avec ___ par les associations, qui attendent des garanties concrètes.", {"A": "circonspection", "B": "euphorie", "C": "indifférence", "D": "désinvolture"}, "A", "Circonspection signifie prudence et réserve."),
    ("C1", "concession", "___ les critiques, le dispositif sera maintenu pendant une année supplémentaire.", {"A": "En dépit de", "B": "Afin de", "C": "Grâce à", "D": "Faute de"}, "A", "En dépit de introduit une concession."),
    ("C1", "registre", "Le directeur a reconnu que les résultats étaient ___, sans toutefois parler d'échec.", {"A": "en demi-teinte", "B": "fulgurants", "C": "inexistants", "D": "triomphants"}, "A", "En demi-teinte exprime un bilan mitigé."),
    ("C1", "cause_consequence", "La concertation a été insuffisante, ___ la méfiance persistante des habitants.", {"A": "d'où", "B": "quoique", "C": "à moins que", "D": "de peur que"}, "A", "D'où introduit une conséquence."),
]


READING_SCENARIOS = [
    (
        "A2",
        "message_court",
        "Bonjour, la réunion de jeudi commencera à 10 h au lieu de 9 h. Merci de prévenir les personnes concernées.",
        {"A": "La réunion est avancée.", "B": "La réunion commence plus tard.", "C": "La réunion est annulée.", "D": "La réunion a lieu vendredi."},
        "B",
        "10 h est plus tard que 9 h.",
    ),
    (
        "A2",
        "annonce_service",
        "La piscine municipale sera fermée dimanche matin pour entretien. Elle rouvrira à 14 h.",
        {"A": "La piscine ouvre à 14 h.", "B": "La piscine ferme toute la semaine.", "C": "La piscine change d'adresse.", "D": "L'entretien est annulé."},
        "A",
        "La réouverture est annoncée à 14 h.",
    ),
    (
        "B1",
        "email_administratif",
        "Madame, votre demande a bien été enregistrée. Si aucun document complémentaire n'est nécessaire, vous recevrez une confirmation sous dix jours.",
        {"A": "La demande est refusée.", "B": "La demande est enregistrée.", "C": "La réponse est immédiate.", "D": "Tous les documents manquent."},
        "B",
        "Le message confirme l'enregistrement.",
    ),
    (
        "B1",
        "information_pratique",
        "Pour limiter l'attente, la mairie reçoit désormais les usagers uniquement sur rendez-vous, sauf pour les urgences sociales.",
        {"A": "Tout le monde peut venir sans rendez-vous.", "B": "Le rendez-vous devient la règle générale.", "C": "La mairie ferme définitivement.", "D": "Les urgences sont interdites."},
        "B",
        "Uniquement sur rendez-vous indique la règle générale.",
    ),
    (
        "B2",
        "article_court",
        "De plus en plus d'entreprises réduisent les réunions. Elles constatent que les échanges courts et préparés améliorent la concentration, même si certaines décisions complexes exigent encore une discussion approfondie.",
        {"A": "L'article condamne toute réunion.", "B": "L'article présente une évolution avec une limite.", "C": "L'article parle de vacances.", "D": "L'article affirme que les décisions simples sont impossibles."},
        "B",
        "Le texte valorise les réunions courtes mais garde une exception.",
    ),
    (
        "B2",
        "implicite_ecrit",
        "Le restaurant annonce une carte plus courte. Selon le chef, il ne s'agit pas d'une économie, mais d'une manière de mieux maîtriser la qualité des produits.",
        {"A": "Le chef veut justifier un choix stratégique.", "B": "Le chef annonce une fermeture.", "C": "Le chef critique les clients.", "D": "Le chef refuse les produits frais."},
        "A",
        "Il explique l'intention derrière la carte plus courte.",
    ),
    (
        "C1",
        "texte_argumentatif",
        "La gratuité des transports est souvent présentée comme une réponse évidente à la pollution urbaine. Pourtant, sans investissement massif dans la fréquence et la fiabilité du réseau, elle risque surtout de déplacer le problème sans modifier durablement les habitudes.",
        {"A": "Le texte soutient une mesure sans réserve.", "B": "Le texte critique la pollution sans proposer d'analyse.", "C": "Le texte nuance l'efficacité d'une mesure populaire.", "D": "Le texte affirme que les transports sont inutiles."},
        "C",
        "Le texte montre qu'une mesure séduisante peut être insuffisante.",
    ),
    (
        "C1",
        "intention_auteur",
        "En multipliant les indicateurs de performance, certaines institutions prétendent gagner en transparence. Mais lorsque ces chiffres deviennent l'objectif lui-même, ils peuvent appauvrir la décision au lieu de l'éclairer.",
        {"A": "L'auteur alerte sur un effet pervers des indicateurs.", "B": "L'auteur demande plus de chiffres partout.", "C": "L'auteur refuse toute transparence.", "D": "L'auteur décrit une procédure technique neutre."},
        "A",
        "L'auteur signale que l'outil peut produire l'effet inverse de celui attendu.",
    ),
]


DETAILS = [
    "Le message insiste sur une contrainte pratique.",
    "La précision finale limite l'interprétation possible.",
    "Le document ajoute une nuance qui élimine une réponse trop générale.",
    "L'information essentielle est donnée après une justification.",
    "La situation oppose une intention et une contrainte.",
    "Le locuteur formule une réserve sans l'exprimer de manière brutale.",
]


def enrich_text(section, text, variant):
    if variant == 0:
        return text
    if section == "structures_langue":
        return text
    detail = DETAILS[(variant - 1) % len(DETAILS)]
    return f"{text} {detail}"


def expand_scenarios(existing_count, section, scenarios, target_per_scenario=6):
    generated = []
    idx = existing_count + 1
    for level, theme, text, choices, good, explanation in scenarios:
        for variant in range(target_per_scenario):
            consigne = "Choisissez la bonne réponse." if section != "comprehension_ecrite" else "Lisez le texte et choisissez la bonne réponse."
            generated.append(
                make_question(
                    section,
                    level,
                    idx,
                    theme,
                    consigne,
                    enrich_text(section, text, variant),
                    choices,
                    good,
                    explanation,
                    "Repérez l'indice linguistique ou l'information exacte avant de choisir.",
                    "Au TCF, éliminez les réponses trop absolues ou qui déforment la nuance du document.",
                )
            )
            idx += 1
    return generated


def main():
    questions = json.loads(QUESTIONS_PATH.read_text(encoding="utf-8"))
    existing_ids = {question["id"] for question in questions}
    additions = []
    additions += expand_scenarios(300, "comprehension_orale", ORAL_SCENARIOS, target_per_scenario=6)
    additions += expand_scenarios(500, "structures_langue", STRUCTURE_SCENARIOS, target_per_scenario=1)
    additions += expand_scenarios(700, "comprehension_ecrite", READING_SCENARIOS, target_per_scenario=6)
    additions = [question for question in additions if question["id"] not in existing_ids]
    questions.extend(additions)
    QUESTIONS_PATH.write_text(json.dumps(questions, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Added {len(additions)} questions. Total: {len(questions)}")


if __name__ == "__main__":
    main()
