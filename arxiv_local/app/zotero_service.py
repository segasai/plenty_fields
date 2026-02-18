import os
from pyzotero import zotero
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

ZOTERO_USER_ID = os.getenv("ZOTERO_USER_ID")
ZOTERO_API_KEY = os.getenv("ZOTERO_API_KEY")
ZOTERO_COLLECTION_ID = os.getenv("ZOTERO_COLLECTION_ID")

def get_zotero_client():
    if not ZOTERO_USER_ID or not ZOTERO_API_KEY:
        return None
    return zotero.Zotero(ZOTERO_USER_ID, 'user', ZOTERO_API_KEY)

def add_arxiv_paper(paper):
    """
    Adds an ArXiv paper to Zotero.
    'paper' is a Paper model instance.
    """
    try:
        zot = get_zotero_client()
        if not zot:
            return {"status": "error", "message": "Zotero credentials not configured in .env"}

        # Prepare item metadata
        template = zot.item_template('journalArticle')
        template['title'] = paper.title
        template['abstractNote'] = paper.abstract
        template['url'] = paper.link
        template['publicationTitle'] = "arXiv"
        template['date'] = str(paper.published_date)
        template['extra'] = f"arXiv: {paper.id}"
        
        # Authors
        authors_list = paper.authors.split(", ")
        template['creators'] = []
        for author in authors_list:
            # Simple splitting of name into first/last if possible
            parts = author.rsplit(" ", 1)
            if len(parts) == 2:
                template['creators'].append({
                    "creatorType": "author",
                    "firstName": parts[0],
                    "lastName": parts[1]
                })
            else:
                template['creators'].append({
                    "creatorType": "author",
                    "firstName": "",
                    "lastName": author
                })

        # Add to collection if specified
        if ZOTERO_COLLECTION_ID:
            template['collections'] = [ZOTERO_COLLECTION_ID]

        # Create the item
        print(f"Adding paper {paper.id} to Zotero...")
        resp = zot.create_items([template])
        print(f"Zotero response: {resp}")
        
        if isinstance(resp, dict) and 'success' in resp and resp['success']:
            return {"status": "success", "zotero_id": resp['success']['0']}
        elif isinstance(resp, list) and len(resp) > 0:
            # Sometimes pyzotero returns a list of created items
            return {"status": "success", "zotero_id": resp[0].get('key', 'unknown')}
        else:
            error_msg = str(resp)
            return {"status": "error", "message": f"Zotero API error: {error_msg}"}
    except Exception as e:
        print(f"Error adding to Zotero: {str(e)}")
        return {"status": "error", "message": f"Internal error: {str(e)}"}
