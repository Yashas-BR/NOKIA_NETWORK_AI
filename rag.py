import pathlib, json
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

DOCS_DIR = pathlib.Path("docs")
THRESHOLD = 0.10  # minimum similarity to return a doc

_vectorizer = None
_matrix = None
_docs = []

def _load():
    global _vectorizer, _matrix, _docs
    _docs = []
    for p in sorted(DOCS_DIR.glob("*.md")):
        text = p.read_text(encoding="utf-8")
        _docs.append({"name": p.stem, "text": text, "path": str(p)})
    if not _docs: return
    _vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1,2))
    _matrix = _vectorizer.fit_transform([d["text"] for d in _docs])

def retrieve(query, top_k=2):
    if _vectorizer is None: _load()
    if not _docs: return []
    qv = _vectorizer.transform([query])
    sims = cosine_similarity(qv, _matrix)[0]
    ranked = sorted(enumerate(sims), key=lambda x: -x[1])
    results = []
    for idx, score in ranked[:top_k]:
        if score >= THRESHOLD:
            results.append({"doc": _docs[idx]["name"], "score": round(float(score),4),
                             "excerpt": _docs[idx]["text"][:600], "full": _docs[idx]["text"]})
    return results

def reload(): _load()
