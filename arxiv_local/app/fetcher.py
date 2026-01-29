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

def get_announcement_date(published_dt: datetime.datetime) -> datetime.date:
    """
    Calculates the ArXiv announcement date based on the published/submission timestamp.
    Logic (approximate based on 14:00 EST / 19:00 UTC cutoff):
    - Submissions < 19:00 UTC are considered 'same day' batch (effectively).
    - Submissions >= 19:00 UTC are 'next day' batch.
    
    Then mapping batch day to announcement:
    - Mon batch (Fri 19:00 - Mon 19:00) -> Tue
    - Tue batch (Mon 19:00 - Tue 19:00) -> Wed
    - Wed batch (Tue 19:00 - Wed 19:00) -> Thu
    - Thu batch (Wed 19:00 - Thu 19:00) -> Fri
    - Fri batch (Thu 19:00 - Fri 19:00) -> Mon
    
    Simplified Logic for date `d` (where d is date of timestamp if < 19:00, else date+1):
    - Mon -> Tue (+1)
    - Tue -> Wed (+1)
    - Wed -> Thu (+1)
    - Thu -> Fri (+1)
    - Fri -> Mon (+3)
    - Sat -> Tue (+3) (Sat covers Fri post-cutoff)
    - Sun -> Tue (+2) (Sun covers Fri post-cutoff/Mon pre-cutoff)
    """
    # 1. Apply Cutoff
    # Check time component. 19:00 UTC = 14:00 EST (Standard).
    # We use 19:00 as a hard cutoff.
    cutoff_time = datetime.time(19, 0, 0)
    
    base_date = published_dt.date()
    if published_dt.time() >= cutoff_time:
        base_date += datetime.timedelta(days=1)
        
    # 2. Map to Announcement Day
    weekday = base_date.weekday() # 0=Mon, 6=Sun
    
    if weekday == 0: # Mon -> Tue
        return base_date + datetime.timedelta(days=1)
    elif weekday == 1: # Tue -> Wed
        return base_date + datetime.timedelta(days=1)
    elif weekday == 2: # Wed -> Thu
        return base_date + datetime.timedelta(days=1)
    elif weekday == 3: # Thu -> Fri
        return base_date + datetime.timedelta(days=1)
    elif weekday == 4: # Fri -> Mon
        return base_date + datetime.timedelta(days=3)
    elif weekday == 5: # Sat -> Tue
        return base_date + datetime.timedelta(days=3)
    elif weekday == 6: # Sun -> Tue
        return base_date + datetime.timedelta(days=2)
    
    return base_date # Should not reach

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
    updated_count = 0
    
    for entry in feed.entries:
        # Check for version to filter updates if desired
        # entry.id is like http://arxiv.org/abs/2101.00001v1
        if not entry.id.endswith('v1'):
            continue

        # Arxiv ID is usually like http://arxiv.org/abs/2101.00001v1
        # We want just 2101.00001
        paper_id = entry.id.split('/abs/')[-1].split('v')[0]
        
        # Parse timestamp (UTC)
        pub_dt = dateutil.parser.parse(entry.published)
        if pub_dt.tzinfo is None:
            # Assume UTC if not specified, though feed usually has it
            pub_dt = pub_dt.replace(tzinfo=datetime.timezone.utc)
        else:
            pub_dt = pub_dt.astimezone(datetime.timezone.utc)
            
        announcement_date = get_announcement_date(pub_dt)
        
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

        # Check if exists
        existing_paper = db.query(models.Paper).filter(models.Paper.id == paper_id).first()
        if existing_paper:
            # Check if we need to update the date (Fixing DB)
            if existing_paper.published_date != announcement_date:
                existing_paper.published_date = announcement_date
                updated_count += 1
            continue

        new_paper = models.Paper(
            id=paper_id,
            title=title,
            authors=authors,
            abstract=abstract,
            published_date=announcement_date,
            updated_date=upd_date,
            arxiv_category=primary_cat,
            link=entry.link
        )
        
        db.add(new_paper)
        new_count += 1
    
    db.commit()
    print(f"Fetched {len(feed.entries)} entries. Added {new_count} new papers. Updated dates for {updated_count} papers.")
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
