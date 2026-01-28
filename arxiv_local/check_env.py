from arxiv_local.app.database import database, models

db = database.SessionLocal()
papers = db.query(models.Paper).all()

for p in papers:
    text = (p.title or "") + " " + (p.abstract or "")
    
    if "\\begin{" in text:
        begins = text.count("\\begin{")
        ends = text.count("\\end{")
        if begins != ends:
             print(f"Unbalanced env in {p.id}: {begins} begins vs {ends} ends")

db.close()

