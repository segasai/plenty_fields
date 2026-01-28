from fastapi import FastAPI, Depends, Request, Form, BackgroundTasks
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from .database import models, database
from . import fetcher, recommender
import datetime

models.Base.metadata.create_all(bind=database.engine)

app = FastAPI()

app.mount("/static", StaticFiles(directory="arxiv_local/app/static"), name="static")
templates = Jinja2Templates(directory="arxiv_local/app/templates")

# Dependency
def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request, date: str = None, db: Session = Depends(get_db)):
    # 1. Determine Target Date
    if date:
        try:
            target_date = datetime.datetime.strptime(date, "%Y-%m-%d").date()
        except ValueError:
            target_date = datetime.date.today()
    else:
        # Default to the most recent date in DB or today
        last_paper = db.query(models.Paper).order_by(models.Paper.published_date.desc()).first()
        target_date = last_paper.published_date if last_paper else datetime.date.today()

    # 2. Mark this date as Viewed
    viewed_entry = db.query(models.ViewedDate).filter(models.ViewedDate.date == target_date).first()
    if not viewed_entry:
        viewed_entry = models.ViewedDate(date=target_date)
        db.add(viewed_entry)
        db.commit()

    # 3. Fetch History for Sidebar (Dates with papers)
    # Get all unique published dates descending
    available_dates_query = db.query(models.Paper.published_date).distinct().order_by(models.Paper.published_date.desc()).limit(60).all()
    available_dates = [d[0] for d in available_dates_query]
    
    # Get all viewed dates
    viewed_dates_query = db.query(models.ViewedDate.date).all()
    viewed_dates_set = {d[0] for d in viewed_dates_query}

    # Construct history list: [(date, is_viewed, is_active), ...]
    history = []
    for d in available_dates:
        history.append({
            "date": d,
            "is_viewed": d in viewed_dates_set,
            "is_active": d == target_date
        })

    # 4. Fetch papers for the target date
    papers = db.query(models.Paper).filter(models.Paper.published_date == target_date).all()
    
    # Sort papers based on recommendation score (descending)
    papers.sort(key=lambda x: x.score or 0, reverse=True)

    # Get likes for these papers
    paper_ids = [p.id for p in papers]
    likes = db.query(models.Interaction).filter(
        models.Interaction.paper_id.in_(paper_ids),
        models.Interaction.is_liked == True
    ).all()
    liked_ids = {l.paper_id for l in likes}

    prev_date = target_date - datetime.timedelta(days=1)
    next_date = target_date + datetime.timedelta(days=1)

    return templates.TemplateResponse("index.html", {
        "request": request,
        "papers": papers,
        "current_date": target_date,
        "prev_date": prev_date,
        "next_date": next_date,
        "liked_ids": liked_ids,
        "history": history
    })

# --- Background Tasks ---
def task_fetch_and_score():
    """Runs fetch then immediately trains the model."""
    db = database.SessionLocal()
    try:
        print("Starting background fetch...")
        # Fetching 2000 papers covers approx 3-4 weeks of history
        fetcher.fetch_papers(db, max_results=2000)
        
        # Cleanup old papers (keep 90 days)
        fetcher.cleanup_old_papers(db, days_to_keep=90)
        
        print("Fetch complete. Starting scoring...")
        recommender.train_and_score(db)
        print("Background task complete.")
    finally:
        db.close()

def task_train_only():
    """Runs only the training/scoring."""
    db = database.SessionLocal()
    try:
        recommender.train_and_score(db)
    finally:
        db.close()

@app.post("/fetch")
async def trigger_fetch(background_tasks: BackgroundTasks):
    # We don't need the dependency db here, the task creates its own
    background_tasks.add_task(task_fetch_and_score)
    return RedirectResponse(url="/", status_code=303)

@app.post("/like/{paper_id}")
async def like_paper(paper_id: str, db: Session = Depends(get_db)):
    interaction = db.query(models.Interaction).filter(models.Interaction.paper_id == paper_id).first()
    if interaction:
        interaction.is_liked = not interaction.is_liked
    else:
        interaction = models.Interaction(paper_id=paper_id, is_liked=True)
        db.add(interaction)
    
    db.commit()
    return {"status": "success", "is_liked": interaction.is_liked}

@app.post("/train")
async def train_model(background_tasks: BackgroundTasks):
    background_tasks.add_task(task_train_only)
    return {"status": "Training started"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8001)
