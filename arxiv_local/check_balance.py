from arxiv_local.app.database import database, models

db = database.SessionLocal()
papers = db.query(models.Paper).all()

for p in papers:
    # Check Title
    if p.title and p.title.count('$') % 2 != 0:
        print(f"Unbalanced $ in Title: {p.id} - {p.title}")
    
    # Check Abstract
    if p.abstract and p.abstract.count('$') % 2 != 0:
        print(f"Unbalanced $ in Abstract: {p.id}")

    # Check Authors
    if p.authors and p.authors.count('$') % 2 != 0:
        print(f"Unbalanced $ in Authors: {p.id}")
