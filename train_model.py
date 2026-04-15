import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
import joblib
import os
import sys
from preprocess import clean_text
from emotion_features import extract_emotion_features

# Forcer l'encodage UTF-8 pour la console
sys.stdout.reconfigure(encoding='utf-8')

print("=" * 50)
print("Entraînement du modèle de détection de stress")
print("=" * 50)

# 1. Charger les données avec le bon encodage
print("\n📂 Chargement des données...")

# Essayer plusieurs encodages
encodings = ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']
data = None

for encoding in encodings:
    try:
        data = pd.read_csv(
            "stress_data.csv",  # Chemin relatif
            encoding=encoding,
            sep=';'
        )
        print(f"   ✓ Chargé avec encoding: {encoding}")
        break
    except Exception as e:
        print(f"   ✗ Échec avec {encoding}: {e}")

if data is None:
    print("❌ Impossible de charger le fichier avec tous les encodages!")
    exit(1)

print(f"   ✓ {len(data)} échantillons chargés")
print(f"   📋 Colonnes: {list(data.columns)}")

# 2. Nettoyer les colonnes
data.columns = data.columns.str.strip()
if 'text' in data.columns and 'label' in data.columns:
    data = data[['text', 'label']]
else:
    print("❌ Colonnes 'text' et 'label' non trouvées!")
    exit(1)

# 3. Nettoyer les données
print("\n🧹 Nettoyage des données...")
data = data.dropna(subset=['text'])
data['text'] = data['text'].astype(str).str.strip()
data = data[data['text'] != '']
print(f"   Après suppression des textes vides: {len(data)}")

data['label'] = pd.to_numeric(data['label'], errors='coerce')
data = data.dropna(subset=['label'])
print(f"   Après suppression des labels invalides: {len(data)}")

# 4. Afficher quelques échantillons pour vérifier
print("\n📝 Aperçu des données:")
for i in range(min(5, len(data))):
    print(f"   {i+1}. Texte: {data.iloc[i]['text'][:50]}... | Label: {data.iloc[i]['label']}")

# 5. Vérifier les scores
print(f"\n📊 Statistiques des scores:")
print(f"   Min: {data['label'].min()}")
print(f"   Max: {data['label'].max()}")
print(f"   Moyenne: {data['label'].mean():.1f}")
print(f"   Médiane: {data['label'].median():.1f}")

zero_count = len(data[data['label'] == 0])
print(f"   Scores = 0: {zero_count} échantillons")
print(f"   Scores > 0: {len(data) - zero_count} échantillons")

# 6. Nettoyer les textes
print("\n🧹 Nettoyage des textes...")
data["clean_text"] = data["text"].apply(clean_text)
print("   ✓ Nettoyage terminé")

# Vérifier les textes après nettoyage
print("\n📝 Aperçu après nettoyage:")
for i in range(min(3, len(data))):
    print(f"   Original: {data.iloc[i]['text'][:50]}...")
    print(f"   Nettoyé: {data.iloc[i]['clean_text'][:50]}...")
    print()

# 7. Extraire features
print("\n🔍 Extraction des features...")
print("   - TF-IDF Vectorization...")
vectorizer = TfidfVectorizer(max_features=5000, min_df=2, max_df=0.95)
X_tfidf = vectorizer.fit_transform(data["clean_text"]).toarray()
print(f"      TF-IDF features: {X_tfidf.shape[1]}")

print("   - Emotion Features (BERT + manual)...")
X_emotion_list = []
total = len(data)
for i, text in enumerate(data["clean_text"]):
    if i % 100 == 0:
        print(f"      Progression: {i}/{total}")
    X_emotion_list.append(extract_emotion_features(text))

X_emotion = np.array(X_emotion_list)
print(f"   ✓ Emotion features: {X_emotion.shape[1]}")

# 8. Fusionner
print("\n🔗 Fusion des features...")
X = np.hstack([X_tfidf, X_emotion])
y = data['label'].values
print(f"   ✓ Total features: {X.shape[1]}")

# 9. Scaling
print("\n📏 Normalisation...")
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

# 10. Split
X_train, X_test, y_train, y_test = train_test_split(
    X_scaled, y, test_size=0.2, random_state=42
)
print(f"\n📊 Split des données:")
print(f"   Train: {len(X_train)} échantillons")
print(f"   Test: {len(X_test)} échantillons")

# 11. Entraînement
print("\n🤖 Entraînement du modèle RandomForest...")

# Poids pour les échantillons (plus de poids pour les scores non-zéro)
sample_weights = np.ones(len(y_train))
# Donner plus de poids aux exemples avec stress élevé
high_stress_indices = y_train > 50
if np.sum(high_stress_indices) > 0:
    sample_weights[high_stress_indices] = 3.0
    print(f"   Poids élevé pour {np.sum(high_stress_indices)} exemples stress élevé")

zero_stress_indices = y_train == 0
if np.sum(zero_stress_indices) > 0:
    sample_weights[zero_stress_indices] = 0.5
    print(f"   Poids réduit pour {np.sum(zero_stress_indices)} exemples stress=0")

model = RandomForestRegressor(
    n_estimators=200,
    max_depth=20,
    min_samples_split=4,
    min_samples_leaf=2,
    random_state=42,
    n_jobs=-1
)
model.fit(X_train, y_train, sample_weight=sample_weights)
print("   ✓ Modèle entraîné")

# 12. Évaluation
y_pred = model.predict(X_test)
mae = np.mean(np.abs(y_test - y_pred))
print(f"\n📈 Évaluation du modèle:")
print(f"   MAE (Erreur moyenne): {mae:.2f} points")

# Afficher quelques prédictions
print("\n🔍 Comparaison prédictions/réalité (test):")
for i in range(min(10, len(y_test))):
    print(f"   Réel: {y_test[i]:.0f} → Prédit: {y_pred[i]:.1f}")

# 13. Sauvegarde
print("\n💾 Sauvegarde des modèles...")
os.makedirs("model", exist_ok=True)

joblib.dump(model, "model/stress_model.joblib")
joblib.dump(vectorizer, "model/vectorizer.joblib")
joblib.dump(scaler, "model/scaler.joblib")

print("\n✅ Modèles sauvegardés avec succès!")
print("   📁 model/stress_model.joblib")
print("   📁 model/vectorizer.joblib")
print("   📁 model/scaler.joblib")

# 14. Test rapide
print("\n🧪 Test rapide:")
test_texts = [
    "je suis très stressée aujourd'hui et je n'arrive pas à me détendre",
    "je veux manger",
    "je me sens calme et relax",
    "كنحس براسي مهلوك وماقادرش نركز",
    "aujourd'hui il fait beau",
    "je vais regarder un film",
    "أشعر بالضغط الشديد والقلق",
    "I'm feeling overwhelmed with work"
]

for text in test_texts:
    clean_t = clean_text(text)
    tfidf = vectorizer.transform([clean_t]).toarray()
    emotion = extract_emotion_features(clean_t)
    X_test_full = np.hstack([tfidf, emotion.reshape(1, -1)])
    X_scaled_test = scaler.transform(X_test_full)
    pred = model.predict(X_scaled_test)[0]
    if pred < 5:
        pred = 0
    print(f"   '{text[:40]}...' → Score: {pred:.1f}")

print("\n🎉 Entraînement terminé!")