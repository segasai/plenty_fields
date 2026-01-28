import feedparser
import datetime
from sqlalchemy.orm import Session
from .database import models
import dateutil.parser

ARXIV_API_URL = "http://export.arxiv.org/api/query?"

# Categories to fetch
CATEGORIES = [
    "astro-ph", "astro-ph.GA", "astro-ph.CO", "astro-ph.EP", 
    "astro-ph.HE", "astro-ph.IM", "astro-ph.SR"
]

def fetch_papers(db: Session, max_results=500):
    # Construct query for all astro-ph categories
    # cat:astro-ph* covers subcategories usually, but being explicit is safe
    search_query = "cat:astro-ph*" 
    
    # Sort by submittedDate descending to get latest
    # Increased max_results to cover more history (approx 50-75 papers/day -> 500 covers ~1 week, 1000 ~2 weeks)
    query_url = f"{ARXIV_API_URL}search_query={search_query}&start=0&max_results={max_results}&sortBy=submittedDate&sortOrder=descending"
    
    print(f"Fetching from: {query_url}")
    feed = feedparser.parse(query_url)

    new_count = 0
    
    for entry in feed.entries:
        # Arxiv ID is usually like http://arxiv.org/abs/2101.00001v1
        # We want just 2101.00001
        paper_id = entry.id.split('/abs/')[-1].split('v')[0]
        
        # Check if exists
        existing_paper = db.query(models.Paper).filter(models.Paper.id == paper_id).first()
        if existing_paper:
            continue

        # Parse date
        pub_date = dateutil.parser.parse(entry.published).date()
        
        # Adjust Weekend dates to Monday
        # 5 = Saturday, 6 = Sunday
        if pub_date.weekday() == 5:
            pub_date += datetime.timedelta(days=2)
        elif pub_date.weekday() == 6:
            pub_date += datetime.timedelta(days=1)
            
        upd_date = dateutil.parser.parse(entry.updated).date()
        
        # Authors
        authors = ", ".join([a.name for a in entry.authors])
        
        # Category
        # entry.tags is a list of dicts [{'term': 'astro-ph.CO', ...}, ...]
        primary_cat = entry.arxiv_primary_category['term'] if 'arxiv_primary_category' in entry else entry.tags[0]['term']

        # Ensure balanced $ to prevent MathJax bleeding
        title = entry.title.replace('\n', ' ')
        if title.count('$') % 2 != 0:
            title += "$"
            
        abstract = entry.summary.replace('\n', ' ')
        if abstract.count('$') % 2 != 0:
            abstract += " $"

        new_paper = models.Paper(
            id=paper_id,
            title=title,
            authors=authors,
            abstract=abstract,
            published_date=pub_date,
            updated_date=upd_date,
            arxiv_category=primary_cat,
            link=entry.link
        )
        
        db.add(new_paper)
        new_count += 1
    
    db.commit()
    print(f"Fetched {len(feed.entries)} entries. Added {new_count} new papers.")
    return new_count

def cleanup_old_papers(db: Session, days_to_keep: int = 90):
    """
    Removes papers older than days_to_keep, unless they are liked.
    """
    cutoff_date = datetime.date.today() - datetime.timedelta(days=days_to_keep)
    print(f"Running cleanup: Pruning unliked papers older than {cutoff_date}...")
    
    # 1. Identify liked papers (never delete these)
    liked_ids_query = db.query(models.Interaction.paper_id).filter(models.Interaction.is_liked == True)
    
    # 2. Delete papers that are OLD and NOT in the liked list
    # Note: .delete() with synchronization logic
    deleted_count = db.query(models.Paper).filter(
        models.Paper.published_date < cutoff_date,
        models.Paper.id.notin_(liked_ids_query)
    ).delete(synchronize_session=False)
    
    db.commit()
    print(f"Cleanup complete. Deleted {deleted_count} old papers.")
    return deleted_count
