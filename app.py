from flask import Flask, request, jsonify
import joblib
import numpy as np
import pandas as pd
import random

from preprocess import clean_text, detect_language
from emotion_features import extract_emotion_features

app = Flask(__name__)

model      = joblib.load("C:\\Users\\pc\\Downloads\\PFE2\\model\\stress_model.joblib")
vectorizer = joblib.load("C:\\Users\\pc\\Downloads\\PFE2\\model\\vectorizer.joblib")
scaler     = joblib.load("C:\\Users\\pc\\Downloads\\PFE2\\model\\scaler.joblib")

suggestions_df = pd.read_csv("C:/Users/pc/Downloads/PFE2/suggestions.csv")

# ─────────────────────────────────────────────
# KEYWORDS
# ─────────────────────────────────────────────

# كلمات stress بجميع اللغات — تمنع is_neutral_intro
STRESS_KEYWORDS = [
    # Français
    "stress","stressé","stressée","anxieux","anxieuse","angoissé","angoissée",
    "épuisé","épuisée","fatigué","fatiguée","nerveux","nerveuse",
    "inquiet","inquiète","débordé","dépassé","peur","panique",
    "déprimé","déprimée","triste","burnout","submergé",
    # English
    "stressed","anxious","worried","overwhelmed","exhausted","tired",
    "nervous","depressed","panic","fear","drained","pressure",
    "overloaded","hopeless","breakdown","insomnia",
    # Arabe فصحى
    "قلق","ضغط","خوف","مرهق","متوتر","مخنوق","مهلوك","مضغوط",
    "تعب","حزين","إرهاق","توتر","اكتئاب","أرق","وحيد","انهيار",
    "ألم","معاناة","يبكي","بكاء","يأس","كآبة",
    # Darija latin
    "mqalla9","m9alla9","m3asseb","mkhnoq","mhlouk","mhloka",
    "3iyan","3eyyan","3ayan","3ayane","3ayana",
    "mroubel","mfoussi","qalaq","9ala9",
    "khayef","khayfa","khayf","7zin","7azin",
    "mdarwaz","mdghout",
    "mstress","mstresa","mstressiya","mstressia","mstressé",
    "t3ban","t3bt","t3bana","t3ab",
    "sa3ba","s3iba",
    "ma9adch","ma9aditch","ma9ditsh","ma9adtsh",
    "7ayran","7ira","daght","maghloub","mghloub","mzroub","msroub",
    # Darija بالعربية
    "عيان","عيانة","عيانين",
    "مستريس","مستريسة","مستريسي","مستريسيا",
    "ماقدتش","ما قدتش",
    "كنبكي","كيبكي","كانبكي",
    "مزروب","مسروب","مقلوق","متردد","مرون","مفوسي","معصب",
]

# كلمات stress خاصة بالدارجة والعربية — النموذج ضعيف عليهم فنفرضو minimum
DARIJA_AR_STRESS = [
    # Darija latin
    "mqalla9","m9alla9","m3asseb","mkhnoq","mhlouk","mhloka",
    "3iyan","3eyyan","3ayan","3ayane","3ayana",
    "mroubel","mfoussi","qalaq","9ala9",
    "khayef","khayfa","khayf","7zin","7azin",
    "mdarwaz","mdghout",
    "mstress","mstresa","mstressiya","mstressia","mstressé",
    "t3ban","t3bt","t3bana","t3ab",
    "sa3ba","s3iba",
    "ma9adch","ma9aditch","ma9ditsh","ma9adtsh",
    "7ayran","7ira","daght","maghloub","mghloub","mzroub","msroub",
    # Darija بالعربية
    "عيان","عيانة","عيانين",
    "مستريس","مستريسة","مستريسي","مستريسيا",
    "ماقدتش","ما قدتش",
    "كنبكي","كيبكي","كانبكي",
    "مزروب","مسروب","مقلوق","متردد","مرون","مفوسي","معصب",
    # Arabe فصحى
    "قلق","ضغط","خوف","مرهق","متوتر","مخنوق","مهلوك","مضغوط",
    "تعب","حزين","إرهاق","توتر","اكتئاب","أرق","وحيد","انهيار",
    "ألم","معاناة","يبكي","بكاء","يأس","كآبة",
]

DARIJA_AR_HIGH = [
    "mhlouk","mhloka","mkhnoq","ma9adch","ma9aditch","ma9ditsh","ma9adtsh",
    "انهيار","يأس","اكتئاب","كآبة",
]

# كلمات intro واضحة — بلا غموض
INTRO_WORDS = [
    "appelle","bonjour","bonsoir","salut","coucou",
    "hello","hi","hey",
    "اسمي","مرحبا","أهلا","صباح","مساء",
    "smiyti","ismi","smi","marhba","mar7ba","ahlan","sbah","labas","kif",
]

# كلمات intro غامضة — تشتغل فقط إيلا الجملة قصيرة (≤4 كلمات)
INTRO_STARTERS = [
    "je","suis","i","am","i'm","im","is","my","name",
    "أنا","اسمي","smiyti","ismi","smi","ana","nta","nti",
]

# ─────────────────────────────────────────────
# FUNCTIONS
# ─────────────────────────────────────────────

def has_stress(text):
    t = text.lower()
    return any(kw in t for kw in STRESS_KEYWORDS)

def get_min_score(text):
    """إيلا كانت الجملة فيها stress دارجة/عربي → نرجعو minimum score"""
    t = text.lower()
    found = [kw for kw in DARIJA_AR_STRESS if kw in t]
    if not found:
        return None
    if any(kw in t for kw in DARIJA_AR_HIGH):
        return 70.0
    return 45.0

def is_neutral_intro(text):
    """جملة تعريف/سلام بلا stress → True"""
    if has_stress(text):
        return False
    t = text.strip().lower()
    words = t.split()
    if len(words) > 5:
        return False
    # كلمة intro واضحة
    if any(w in words for w in INTRO_WORDS):
        return True
    # كلمة intro غامضة + جملة قصيرة جداً
    if len(words) <= 4 and any(w in words for w in INTRO_STARTERS):
        return True
    return False

def stress_level(score):
    if score < 34:   return "low"
    elif score < 67: return "medium"
    else:            return "high"

def get_suggestion(level, lang):
    subset = suggestions_df[
        (suggestions_df["level"] == level) &
        (suggestions_df["lang"] == lang)
    ]
    if subset.empty:
        subset = suggestions_df[suggestions_df["level"] == level]
    return random.choice(subset["suggestion"].tolist())

# ─────────────────────────────────────────────
# ROUTE
# ─────────────────────────────────────────────
@app.route("/predict", methods=["POST"])
def predict():
    data = request.json
    text = data["text"]
    lang = detect_language(text).lower()
    
    # === Force score pour Darija stress ===
    text_lower = text.lower()
    
    # Scores forts (stress élevé)
    if any(word in text_lower for word in ['mhlouk', 'mkhnoq', 'mkhno9', 'm9alqa', 'mqala9', 'm9alla9']):
        score = 85.0
        level = stress_level(score)
        return jsonify({
            "score": round(score, 2),
            "level": level,
            "lang": lang,
            "suggestion": get_suggestion(level, lang)
        })
    
    # Scores moyens (stress modéré)
    if any(word in text_lower for word in ['mqlqa', 'm9elqa', '3yana', 't3bana', 'qalaq', '9ala9', 'mqal9']):
        score = 65.0
        level = stress_level(score)
        return jsonify({
            "score": round(score, 2),
            "level": level,
            "lang": lang,
            "suggestion": get_suggestion(level, lang)
        })
    
    # RÈGLE 1 — intro/salutation neutre → 0 (mais seulement si pas de stress détecté)
    if is_neutral_intro(text) and not has_stress(text):
        return jsonify({
            "score": 0.0,
            "level": "low",
            "lang": lang,
            "suggestion": get_suggestion("low", lang)
        })
    
    # Prédiction modèle normal
    clean_t        = clean_text(text)
    tfidf_vec      = vectorizer.transform([clean_t]).toarray()
    emotion_vec    = np.array([extract_emotion_features(clean_t)])
    final_vec      = np.hstack([tfidf_vec, emotion_vec])
    final_scaled   = scaler.transform(final_vec)
    score          = float(np.clip(model.predict(final_scaled)[0], 0, 100))
    
    # RÈGLE 2 — score trop bas → 0
    if score < 10:
        score = 0.0
    
    # RÈGLE 3 — stress darija/arabe détecté mais modèle sous-estime → forcer minimum
    min_s = get_min_score(text)
    if min_s is not None and score < min_s:
        score = min_s
    
    level = stress_level(score)
    return jsonify({
        "score": round(score, 2),
        "level": level,
        "lang": lang,
        "suggestion": get_suggestion(level, lang)
    })
    # ... reste du code normal
if __name__ == "__main__":
    app.run(debug=True)