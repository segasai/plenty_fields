from sqlalchemy.orm import Session
from .database import models
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

def train_and_score(db: Session):
    print("Starting recommendation training...")
    
    # 1. Get all papers to build vocabulary (or just recent ones to save memory)
    # For a local tool, 10k-20k papers is manageable. 
    # Let's limit to last 30 days for vocabulary to keep it fast, or all if small.
    all_papers = db.query(models.Paper).all()
    if not all_papers:
        print("No papers to train on.")
        return

    # 2. Get liked papers
    liked_interactions = db.query(models.Interaction).filter(models.Interaction.is_liked == True).all()
    liked_ids = {i.paper_id for i in liked_interactions}
    
    if not liked_ids:
        print("No liked papers to build profile. Skipping.")
        return

    # Prepare corpus
    # We combine title and abstract
    corpus = [f"{p.title} {p.abstract}" for p in all_papers]
    paper_id_to_idx = {p.id: i for i, p in enumerate(all_papers)}
    
    # 3. Vectorize
    vectorizer = TfidfVectorizer(stop_words='english', max_features=5000)
    tfidf_matrix = vectorizer.fit_transform(corpus)
    
    # 4. Build User Profile
    # Get indices of liked papers
    liked_indices = [paper_id_to_idx[pid] for pid in liked_ids if pid in paper_id_to_idx]
    
    if not liked_indices:
        return

    # User vector is the mean of liked paper vectors
    user_vector = np.asarray(tfidf_matrix[liked_indices].mean(axis=0))
    
    # 5. Calculate Similarity for ALL papers
    # cosine_similarity expects 2D arrays
    scores = cosine_similarity(user_vector, tfidf_matrix).flatten()
    
    # 6. Update DB
    for i, paper in enumerate(all_papers):
        paper.score = float(scores[i])
    
    db.commit()
    print("Recommendation scores updated.")
