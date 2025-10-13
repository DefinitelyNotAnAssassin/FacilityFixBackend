from groq import Groq
from ..core.config import GROQ_API_KEY, GROQ_MODEL
import re

_client = Groq(api_key=GROQ_API_KEY)

# Tagalog -> English glossary for pests/animals
GLOSSARY = {
    "lamok": "mosquito",
    "ipis": "cockroach",
    "daga": "rat",
    "bubwit": "mouse",
    "surot": "bed bug",
    "anay": "termite",
    "langgam": "ant",
    "garapata": "tick",
    "pulgas": "flea",
    "ahas": "snake",
    "butiki": "lizard",
    "tipaklong": "grasshopper",
}

# Words the model might hallucinate/flip between
_ALL_SPECIES_EN = set(GLOSSARY.values())

_SYSTEM = (
    "You are a precise Tagalog-to-English translator for building maintenance tickets. "
    "Translate literally and do not paraphrase. "
    "Do NOT infer, guess, or replace the pest/animal species. "
    "If the Tagalog mentions a species, you MUST keep the exact species per this glossary:\n"
    + "\n".join([f"- {k} -> {v}" for k, v in GLOSSARY.items()]) +
    "\nReturn only the English translation."
)

_word = re.compile(r"[A-Za-z]+")


def _force_species(original_tl: str, eng: str) -> str:
    """If original contains a known Tagalog species, enforce the exact English term."""
    o_low = original_tl.lower()
    e_out = eng

    for tl, en in GLOSSARY.items():
        if tl in o_low:
            # If translation doesn't contain the correct term, replace any wrong species with the correct one
            e_low = e_out.lower()
            if en not in e_low:
                for wrong in _ALL_SPECIES_EN - {en}:
                    # replace whole-word wrong species with the correct one
                    e_out = re.sub(rf"\b{re.escape(wrong)}\b", en, e_out, flags=re.IGNORECASE)
                # As a backup, if still missing, and it used a generic word like 'insect'/'bug', replace it
                if en.lower() not in e_out.lower():
                    e_out = re.sub(r"\b(insect|bug|pest)\b", en, e_out, flags=re.IGNORECASE)
            # If multiple species appear, prefer the one from the glossary for this sentence
    return e_out


def translate_one(text: str) -> str:
    """Translate a single Tagalog text to English, enforcing glossary species terms."""
    try:
        resp = _client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": f"Translate to English. Output only the translation.\n\nText:\n{text}"},
            ],
            temperature=0.0,  # deterministic
            top_p=1.0,
            max_tokens=200,
        )
        out = (resp.choices[0].message.content or "").strip()
        out = _force_species(text, out)
        return out
    except Exception as e:
        print(f"[Groq] translation error: {e}")
        raise
