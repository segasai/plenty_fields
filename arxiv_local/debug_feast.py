from arxiv_local.app.database import database, models

db = database.SessionLocal()
p = db.query(models.Paper).filter(models.Paper.id == "2601.11434").first()

if p:
    print(f"Abstract: {p.abstract}")
    print(f"Has \(: {'\(' in p.abstract}")
    print(f"Has \[: {'\[' in p.abstract}")

