# authapp/scrap_task.py
import logging
import requests
from bs4 import BeautifulSoup
from urllib.parse import urldefrag, urljoin
from celery import shared_task
from django.utils import timezone
from .models import ScrapedPage

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # Ensure debug logs are captured

def is_valid_page(url):
    allowed_extensions = ('.php', '.html', '.htm', '')
    disallowed_extensions = (
        '.jpg', '.jpeg', '.png', '.gif', '.svg', '.ico',
        '.pdf', '.zip', '.rar', '.mp4', '.mp3', '.wav',
        '.css', '.js', '.json', '.xml'
    )
    lower_url = url.lower()
    if any(lower_url.endswith(ext) for ext in disallowed_extensions):
        return False
    if '.' in lower_url:
        return any(lower_url.endswith(ext) for ext in allowed_extensions)
    return True

@shared_task(bind=True, max_retries=3, time_limit=600)
def crawl_website(self, base_url, max_pages=2):
    """
    Celery task to crawl a website and store results in database.
    Now hard stops after scraping max_pages pages.
    """
    logger.debug(f"[TASK START] Crawl started at {timezone.now()} for: {base_url}")

    priority_keywords = [
        'about', 'who-we-are', 'vision-mission', 'the-founder', 'nature-education',
        'history', 'our-story', 'objectives', 'values', 'our-projects',
        'volunteer', 'impact', 'our-work', 'what-we-do', 'why-gmt'
    ]
    
    visited = set()
    to_visit = []
    scraped_count = 0

    def normalize_url(url):
        return urldefrag(urljoin(base_url, url)).url.rstrip('/')

    def scrape_and_store(url):
        nonlocal scraped_count
        if scraped_count >= max_pages:
            return []  # Stop scraping if limit reached

        try:
            if ScrapedPage.objects.filter(url=url).exists():
                logger.debug(f"[DB CHECK] Already exists: {url}")
                return []

            response = requests.get(
                url, timeout=10,
                headers={"User-Agent": "Mozilla/5.0"}
            )

            if 'text/html' not in response.headers.get('Content-Type', ''):
                logger.debug(f"[SKIP] Non-HTML content: {url}")
                return []

            soup = BeautifulSoup(response.text, 'html.parser')
            title = soup.title.string.strip() if soup.title else "No Title"
            text = ' '.join(soup.stripped_strings)[:10000]

            is_priority = any(keyword in url.lower() for keyword in priority_keywords)

            # Save to database
            ScrapedPage.objects.create(
                url=url,
                base_url=base_url,
                title=title[:255],
                content=text,
                is_priority=is_priority,
                scraped_at=timezone.now()
            )

            scraped_count += 1
            logger.debug(f"[DB SAVE] Page #{scraped_count} saved: {title} | {url}")

            if scraped_count >= max_pages:
                logger.debug("[STOP] Reached max_pages, not collecting more links.")
                return []

            new_links = []
            for tag in soup.find_all('a', href=True):
                link = normalize_url(tag['href'])
                if (link.startswith(base_url) and 
                    is_valid_page(link) and 
                    link not in visited):
                    new_links.append(link)
            
            return new_links

        except Exception as e:
            logger.error(f"[ERROR] Scraping {url}: {str(e)}")
            return []

    try:
        logger.debug(f"[CRAWL INIT] Visiting base URL: {base_url}")
        visited.add(base_url)
        to_visit.extend(scrape_and_store(base_url))

        while to_visit:
            if scraped_count >= max_pages:
                logger.debug("[STOP LOOP] Max pages reached, ending crawl.")
                break

            url = to_visit.pop(0)
            if url not in visited:
                visited.add(url)
                new_links = scrape_and_store(url)
                if scraped_count >= max_pages:
                    break
                to_visit.extend(
                    link for link in new_links 
                    if link not in visited and link not in to_visit
                )

        logger.debug(f"[TASK END] Crawl finished at {timezone.now()} | Total pages scraped: {scraped_count}")
        total_rows = ScrapedPage.objects.count()
        logger.debug(f"[DB COUNT] Total rows in ScrapedPage: {total_rows}")
        print(f"[DB COUNT] Total rows in ScrapedPage: {total_rows}")
        return {
            "status": "success",
            "pages_scraped": scraped_count,
            "base_url": base_url
        }

    except Exception as e:
        logger.error(f"[TASK FAIL] Crawl failed: {str(e)}")
        self.retry(exc=e, countdown=10)
