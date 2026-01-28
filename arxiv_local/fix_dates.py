from arxiv_local.app.database import database, models
import datetime

db = database.SessionLocal()

# Find all papers published on Sat (5) or Sun (6)
papers = db.query(models.Paper).all()
count = 0

for paper in papers:
    # 5 = Saturday, 6 = Sunday
    wd = paper.published_date.weekday()
    if wd == 5: # Sat -> Mon (+2)
        paper.published_date += datetime.timedelta(days=2)
        count += 1
    elif wd == 6: # Sun -> Mon (+1)
        paper.published_date += datetime.timedelta(days=1)
        count += 1

db.commit()
db.close()
print(f"Fixed {count} papers with weekend dates.")
