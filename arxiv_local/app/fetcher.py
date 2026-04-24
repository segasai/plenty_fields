import feedparser
import datetime
from zoneinfo import ZoneInfo
from sqlalchemy.orm import Session
from .database import models
import dateutil.parser

ARXIV_API_URL = "http://export.arxiv.org/api/query?"

# Categories to fetch
CATEGORIES = [
    "astro-ph", "astro-ph.GA", "astro-ph.CO", "astro-ph.EP", 
    "astro-ph.HE", "astro-ph.IM", "astro-ph.SR"
]

ARXIV_ANNOUNCEMENT_TZ = ZoneInfo("America/New_York")
ARXIV_CUTOFF_TIME_ET = datetime.time(14, 0, 0)

def get_announcement_date(published_dt: datetime.datetime) -> datetime.date:
    """
    Calculates the arXiv announcement date from the API submission timestamp.

    arXiv returns submission timestamps in UTC, but the announcement cutoff is
    14:00 US Eastern Time with DST applied. We therefore convert to ET first,
    assign the submission to the correct cutoff bucket, roll weekend buckets
    forward to Monday, then map that bucket to the next announcement day.
    """
    if published_dt.tzinfo is None:
        published_dt = published_dt.replace(tzinfo=datetime.timezone.utc)

    published_dt_et = published_dt.astimezone(ARXIV_ANNOUNCEMENT_TZ)
    cutoff_bucket_date = published_dt_et.date()

    if published_dt_et.time() >= ARXIV_CUTOFF_TIME_ET:
        cutoff_bucket_date += datetime.timedelta(days=1)

    while cutoff_bucket_date.weekday() >= 5:
        cutoff_bucket_date += datetime.timedelta(days=1)

    if cutoff_bucket_date.weekday() == 4:
        return cutoff_bucket_date + datetime.timedelta(days=3)

    return cutoff_bucket_date + datetime.timedelta(days=1)

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
