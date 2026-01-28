from arxiv_local.app.database import database, models

db = database.SessionLocal()

# Find FEAST paper
feast = db.query(models.Paper).filter(models.Paper.id == "2601.11434").first()
target_date = feast.published_date

# Get all papers on that date, sorted by Score descending (as per View)
# Wait, view sorts by score.
# So the order depends on the SCORE.
# I need to know the score of FEAST and papers around it.

papers = db.query(models.Paper).filter(models.Paper.published_date == target_date).all()
papers.sort(key=lambda x: x.score or 0, reverse=True)

# Find index of FEAST
for i, p in enumerate(papers):
    if p.id == "2601.11434":
        print(f"FEAST found at index {i}")
        if i > 0:
            prev = papers[i-1]
            print(f"Previous Paper: {prev.id} - {prev.title}")
            print(f"Prev Abstract End: {prev.abstract[-50:]}")
            print(f"Prev Authors: {prev.authors}")
            
            # Check for unclosed stuff in Prev
            combined = (prev.title or "") + (prev.authors or "") + (prev.abstract or "")
            print(f"Prev unclosed $ (odd): {combined.count('$') % 2 != 0}")
        break

db.close()
