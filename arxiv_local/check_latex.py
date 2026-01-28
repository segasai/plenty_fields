from arxiv_local.app.database import database, models

db = database.SessionLocal()
papers = db.query(models.Paper).all()

for p in papers:
    text = (p.title or "") + " " + (p.abstract or "")
    
    # Check \[ \]
    open_sq = text.count('\\\[')
    close_sq = text.count('\\\]')
    if open_sq != close_sq:
        print(f"Unbalanced \\\\[\\\\] in {p.id}: {open_sq} vs {close_sq}")

    # Check \( \)
    open_par = text.count('\\(')
    close_par = text.count('\\)')
    if open_par != close_par:
        print(f"Unbalanced \\(\\) in {p.id}: {open_par} vs {close_par}")

db.close()

