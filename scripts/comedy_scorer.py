#!/usr/bin/env python3
"""Ella M Comedy Scorer — ML model for scoring one-minute comedy sets.

Approach:
1. Sentence embeddings (all-MiniLM-L6-v2, 384-dim, CPU-friendly)
2. Feature engineering (word count, sentiment, punctuation patterns)
3. Gradient Boosting classifier on combined features
4. Cross-validated evaluation

Trained on 225 Kill Tony sets with Tony scores 1-5.
"""

import json
import re
import warnings
from pathlib import Path

import numpy as np
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.model_selection import cross_val_predict, StratifiedKFold
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sentence_transformers import SentenceTransformer

warnings.filterwarnings("ignore")

DATA_PATH = Path("/root/freaktown/training_data/kill_tony_sets.jsonl")
MODEL_DIR = Path("/root/freaktown/models")
MODEL_DIR.mkdir(exist_ok=True)


# ── Feature Engineering ─────────────────────────────────────────────

def extract_features(text: str) -> dict:
    """Extract hand-crafted features from a comedy set transcript."""
    words = text.split()
    word_count = len(words)
    sentences = [s.strip() for s in re.split(r'[.!?]+', text) if s.strip()]
    
    return {
        "word_count": word_count,
        "sentence_count": len(sentences),
        "avg_word_length": np.mean([len(w) for w in words]) if words else 0,
        "avg_sentence_length": word_count / max(1, len(sentences)),
        "question_marks": text.count("?"),
        "exclamation_marks": text.count("!"),
        "ellipsis": text.count("..."),
        "has_swear_words": int(bool(re.search(r'\b(fuck|shit|damn|ass|bitch|hell|crap)\b', text.lower()))),
        "swear_count": len(re.findall(r'\b(fuck|shit|damn|ass|bitch|hell|crap)\b', text.lower())),
        "has_I_statement": int(bool(re.search(r'\bI\b', text))),
        "has_you_statement": int(bool(re.search(r'\byou\b', text.lower()))),
        "has_specific_number": int(bool(re.search(r'\d+', text))),
        "comma_count": text.count(","),
        "dash_count": text.count("-") + text.count("—"),
        "quote_count": text.count('"'),
        "has_dialogue": int(bool(re.search(r'"[^"]*"', text))),
        "unique_word_ratio": len(set(w.lower() for w in words)) / max(1, word_count),
        "long_word_ratio": len([w for w in words if len(w) > 6]) / max(1, word_count),
        "short_word_ratio": len([w for w in words if len(w) <= 3]) / max(1, word_count),
    }


# ── Data Loading ────────────────────────────────────────────────────

def load_data():
    """Load Kill Tony sets and extract features + embeddings."""
    print("Loading Kill Tony data...")
    data = []
    with open(DATA_PATH) as f:
        for line in f:
            data.append(json.loads(line))
    
    print(f"Loaded {len(data)} sets")
    
    # Filter to sets with valid transcripts and scores
    valid = [d for d in data if d['transcript'] and d['tony_score'] in [1, 2, 3, 4, 5]]
    print(f"Valid sets: {len(valid)}")
    
    texts = [d['transcript'] for d in valid]
    labels = [d['tony_score'] for d in valid]
    
    # Extract hand-crafted features
    print("Extracting features...")
    feat_dicts = [extract_features(t) for t in texts]
    feature_names = list(feat_dicts[0].keys())
    hand_features = np.array([[d[k] for k in feature_names] for d in feat_dicts], dtype=float)
    
    # Generate sentence embeddings
    print("Generating sentence embeddings (this takes a minute)...")
    st_model = SentenceTransformer('all-MiniLM-L6-v2')
    embeddings = st_model.encode(texts, show_progress_bar=True, batch_size=32)
    print(f"Embeddings shape: {embeddings.shape}")
    
    # Combine features
    scaler = StandardScaler()
    hand_scaled = scaler.fit_transform(hand_features)
    X = np.hstack([hand_scaled, embeddings])
    
    print(f"Final feature matrix: {X.shape}")
    
    return X, np.array(labels), texts, feature_names, st_model, scaler


# ── Model Training ──────────────────────────────────────────────────

def train_and_evaluate(X, y, texts):
    """Train multiple models and cross-validate."""
    print("\n" + "=" * 60)
    print("  MODEL TRAINING & EVALUATION")
    print("=" * 60)
    
    models = {
        "Logistic Regression": Pipeline([
            ("scaler", StandardScaler()),
            ("clf", LogisticRegression(max_iter=1000, C=1.0))
        ]),
        "Random Forest": RandomForestClassifier(
            n_estimators=200, max_depth=10, min_samples_leaf=3, random_state=42
        ),
        "Gradient Boosting": GradientBoostingClassifier(
            n_estimators=200, max_depth=4, learning_rate=0.1, 
            min_samples_leaf=3, random_state=42
        ),
    }
    
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    best_score = 0
    best_model_name = ""
    
    for name, model in models.items():
        print(f"\n--- {name} ---")
        
        # Cross-validated predictions
        y_pred = cross_val_predict(model, X, y, cv=cv)
        
        # Report
        accuracy = np.mean(y_pred == y)
        print(f"Accuracy: {accuracy:.3f}")
        print(f"\nClassification Report:")
        print(classification_report(y, y_pred, zero_division=0))
        
        if accuracy > best_score:
            best_score = accuracy
            best_model_name = name
    
    # Train best model on full data
    print(f"\n{'=' * 60}")
    print(f"  BEST MODEL: {best_model_name} ({best_score:.3f})")
    print(f"{'=' * 60}")
    
    best_model = models[best_model_name]
    best_model.fit(X, y)
    
    return best_model, best_model_name


def train_binary_classifier(X, y):
    """Train binary hit/miss classifier (4-5 vs 1-2)."""
    print("\n" + "=" * 60)
    print("  BINARY CLASSIFIER (HIT vs MISS)")
    print("=" * 60)
    
    # Binary labels: 4-5 = hit (1), 1-2 = miss (0), 3 = excluded
    binary_mask = np.isin(y, [1, 2, 4, 5])
    X_bin = X[binary_mask]
    y_bin = np.array([1 if v >= 4 else 0 for v in y[binary_mask]])
    
    print(f"Hit sets: {np.sum(y_bin == 1)} | Miss sets: {np.sum(y_bin == 0)}")
    
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    
    model = GradientBoostingClassifier(
        n_estimators=150, max_depth=4, learning_rate=0.1,
        min_samples_leaf=3, random_state=42
    )
    
    y_pred = cross_val_predict(model, X_bin, y_bin, cv=cv)
    accuracy = np.mean(y_pred == y_bin)
    
    print(f"Binary accuracy: {accuracy:.3f}")
    print(classification_report(y_bin, y_pred, target_names=["MISS", "HIT"]))
    
    model.fit(X_bin, y_bin)
    return model


# ── Scoring ─────────────────────────────────────────────────────────

class ComedyScorer:
    """Score a comedy set using the trained ML model."""
    
    def __init__(self, model, st_model, scaler, feature_names):
        self.model = model
        self.st_model = st_model
        self.scaler = scaler
        self.feature_names = feature_names
    
    def score(self, text: str) -> dict:
        """Score a comedy set. Returns predicted score + confidence."""
        # Hand features
        features = extract_features(text)
        hand_vec = np.array([[features[k] for k in self.feature_names]])
        hand_scaled = self.scaler.transform(hand_vec)
        
        # Embedding
        embedding = self.st_model.encode([text])
        
        # Combined
        X = np.hstack([hand_scaled, embedding])
        
        # Predict
        prediction = self.model.predict(X)[0]
        probabilities = self.model.predict_proba(X)[0]
        confidence = float(max(probabilities))
        
        # Map to rating
        score_map = {1: "1/5", 2: "2/5", 3: "3/5", 4: "4/5", 5: "5/5"}
        
        return {
            "score": prediction,
            "score_label": score_map.get(prediction, str(prediction)),
            "confidence": confidence,
            "probabilities": {
                score_map.get(i, str(i)): float(p) 
                for i, p in zip(self.model.classes_, probabilities)
            },
            "features": features,
        }
    
    def score_ella_sets(self):
        """Score all 20 Ella M sets."""
        sets_path = Path("/root/freaktown/ella_sets.md")
        content = sets_path.read_text()
        
        import re
        blocks = re.split(r'## \d+\.', content)[1:]
        
        results = []
        for block in blocks:
            lines = block.strip().split('\n')
            title = lines[0].strip().strip('"')
            text_lines = []
            for line in lines[1:]:
                if line.startswith('---') or line.startswith('>') or line.startswith('Topics:'):
                    continue
                if line.strip():
                    text_lines.append(line.strip())
            text = ' '.join(text_lines)
            
            result = self.score(text)
            result['title'] = title
            result['text'] = text[:100] + "..."
            results.append(result)
        
        return results


# ── Main ────────────────────────────────────────────────────────────

def main():
    # Load data
    X, y, texts, feature_names, st_model, scaler = load_data()
    
    # Train models
    best_model, best_name = train_and_evaluate(X, y, texts)
    binary_model = train_binary_classifier(X, y)
    
    # Save scorer
    scorer = ComedyScorer(best_model, st_model, scaler, feature_names)
    
    # Score Ella's sets
    print("\n" + "=" * 60)
    print("  ELLA M SETS — ML ASSESSMENT")
    print("=" * 60)
    
    results = scorer.score_ella_sets()
    
    for r in results:
        print(f"\n  {r['title']}")
        print(f"    ML Score: {r['score_label']} (confidence: {r['confidence']:.1%})")
        print(f"    Probabilities: {r['probabilities']}")
    
    # Save results
    # Convert numpy types for JSON serialization
    def convert(obj):
        if isinstance(obj, (np.integer,)): return int(obj)
        if isinstance(obj, (np.floating,)): return float(obj)
        if isinstance(obj, np.ndarray): return obj.tolist()
        return obj
    
    clean_results = []
    for r in results:
        cr = {k: convert(v) for k, v in r.items()}
        clean_results.append(cr)
    
    with open(MODEL_DIR / "ella_scores.json", "w") as f:
        json.dump(clean_results, f, indent=2)
    
    # Save model info
    summary = {
        "model": best_name,
        "features": len(feature_names) + 384,  # hand + embedding
        "training_samples": len(y),
        "label_distribution": {int(k): int(v) for k, v in zip(*np.unique(y, return_counts=True))},
    }
    with open(MODEL_DIR / "model_info.json", "w") as f:
        json.dump(summary, f, indent=2)
    
    print(f"\nModel saved to {MODEL_DIR}")
    
    # Feature importance (for tree-based models)
    if hasattr(best_model, 'feature_importances_'):
        importances = best_model.feature_importances_
        top_n = 20
        top_idx = np.argsort(importances)[-top_n:][::-1]
        print(f"\nTop {top_n} features:")
        for i, idx in enumerate(top_idx):
            name = feature_names[idx] if idx < len(feature_names) else f"embedding_{idx - len(feature_names)}"
            print(f"  {i+1:2d}. {name:<30} {importances[idx]:.4f}")


if __name__ == "__main__":
    main()
