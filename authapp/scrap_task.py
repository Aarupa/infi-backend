import logging
import requests
from bs4 import BeautifulSoup
from urllib.parse import urldefrag, urljoin
from celery import shared_task
from django.utils import timezone
from .models import ScrapedPage  # Make sure this matches your model name

logger = logging.getLogger(__name__)


def is_valid_page(url):
    allowed_extensions = ('.php', '.html', '.htm', '')  # Allow these
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
def crawl_website(self, base_url, max_pages=30):
    """
    Celery task to crawl a website and store results in database
    Args:
        base_url: Starting URL (e.g., "https://example.org")
        max_pages: Maximum number of pages to scrape
    """
    priority_keywords = [
        'about', 'who-we-are', 'vision-mission', 'the-founder', 'nature-education',
        'history', 'our-story', 'objectives', 'values', 'our-projects',
        'volunteer', 'impact', 'our-work', 'what-we-do', 'why-gmt'
    ]
    
    visited = set()
    to_visit = []
    scraped_count = 0

    def normalize_url(url):
        """Normalize URL to prevent duplicate visits"""
        return urldefrag(urljoin(base_url, url)).url.rstrip('/')

    def scrape_and_store(url):
        """Scrape individual page and store in database"""
        nonlocal scraped_count
        try:
            # Skip if already processed
            if ScrapedPage.objects.filter(url=url).exists():
                logger.info(f"[SKIP] Already exists: {url}")
                return []

            # Fetch page
            response = requests.get(
                url, 
                timeout=10, 
                headers={"User-Agent": "Mozilla/5.0"}
            )
            
            if 'text/html' not in response.headers.get('Content-Type', ''):
                logger.info(f"[SKIP] Non-HTML content: {url}")
                return []

            # Parse content
            soup = BeautifulSoup(response.text, 'html.parser')
            title = soup.title.string.strip() if soup.title else "No Title"
            text = ' '.join(soup.stripped_strings)[:10000]  # Limit content length

            # Determine if priority page
            is_priority = any(
                keyword in url.lower() 
                for keyword in priority_keywords
            )

            # Save to database
            ScrapedPage.objects.create(
                url=url,
                base_url=base_url,
                title=title[:255],  # Ensure title fits in CharField
                content=text,
                is_priority=is_priority,
                last_scraped=timezone.now()
            )
            
            scraped_count += 1
            logger.info(f"[SCRAPED] {scraped_count}/{max_pages}: {url}")

            # Extract new links
            new_links = []
            for tag in soup.find_all('a', href=True):
                link = normalize_url(tag['href'])
                if (link.startswith(base_url) and 
                    is_valid_page(link) and 
                    link not in visited):
                    new_links.append(link)
            
            return new_links

        except Exception as e:
            logger.error(f"Error scraping {url}: {str(e)}")
            return []

    # Main crawling logic
    try:
        logger.info(f"Starting crawl: {base_url}")
        visited.add(base_url)
        to_visit.extend(scrape_and_store(base_url))

        while to_visit and scraped_count < max_pages:
            url = to_visit.pop(0)
            if url not in visited:
                visited.add(url)
                new_links = scrape_and_store(url)
                to_visit.extend(
                    link for link in new_links 
                    if link not in visited and link not in to_visit
                )

        logger.info(f"Crawl completed. Pages scraped: {scraped_count}")
        return {
            "status": "success",
            "pages_scraped": scraped_count,
            "base_url": base_url
        }

    except Exception as e:
        logger.error(f"Crawl failed: {str(e)}")
        self.retry(exc=e, countdown=60)  # Retry after 60 seconds