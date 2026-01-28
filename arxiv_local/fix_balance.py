from arxiv_local.app.database import database, models

db = database.SessionLocal()
papers = db.query(models.Paper).all()
count = 0

for p in papers:
    modified = False
    
    # Check Title
    if p.title and p.title.count('$') % 2 != 0:
        p.title += "$"
        modified = True
    
    # Check Abstract
    if p.abstract and p.abstract.count('$') % 2 != 0:
        p.abstract += " $" # Add space to avoid merging with last word
        modified = True

    # Check Authors
    if p.authors and p.authors.count('$') % 2 != 0:
        p.authors += "$"
        modified = True
    
    if modified:
        count += 1
        print(f"Fixed unbalanced math in paper {p.id}")

db.commit()
db.close()
print(f"Total fixed: {count}")
