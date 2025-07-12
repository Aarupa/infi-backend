import requests
from bs4 import BeautifulSoup
import json
import tldextract
from urllib.parse import urljoin, urlparse
import trafilatura
from time import sleep
from requests.exceptions import RequestException
import os

visited = set()

def get_domain(url):
    ext = tldextract.extract(url)
    return f"{ext.domain}.{ext.suffix}"

def is_same_domain(base, target):
    return urlparse(base).netloc in urlparse(target).netloc

def clean_text(text):
    return ' '.join(text.strip().split())

def fetch_with_retries(url, headers, retries=3, timeout=10):
    for i in range(retries):
        try:
            return requests.get(url, timeout=timeout, headers=headers)
        except RequestException:
            if i == retries - 1:
                raise
            sleep(2)

def generate_description(url):
    downloaded = trafilatura.fetch_url(url)
    result = trafilatura.extract(downloaded, include_comments=False, include_tables=False)
    return clean_text(result[:500]) if result else "No meaningful description available."

def scrape_page(url, headers):
    if url in visited:
        return None
    visited.add(url)
    print(f"Scraping: {url}")
    try:
        response = fetch_with_retries(url, headers)
        soup = BeautifulSoup(response.text, 'html.parser')

        title_tag = soup.find('title') or soup.find('h1') or soup.find('h2')
        section_title = clean_text(title_tag.text) if title_tag else urlparse(url).path.strip('/').replace('-', ' ').title()

        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc and meta_desc.get("content"):
            description = clean_text(meta_desc["content"])
        else:
            description = generate_description(url)

        return {
            "url": url,
            "section_title": section_title,
            "description": description,
            "text": clean_text(soup.get_text())
        }

    except Exception as e:
        print(f"Error scraping {url}: {e}")
        return None

def get_all_links(base_url, max_depth=2, max_pages=50):
    to_visit = [(base_url, 0)]
    found_links = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }

    while to_visit and len(found_links) < max_pages:
        current_url, depth = to_visit.pop(0)
        print(f"Visiting: {current_url} | Depth: {depth}")
        if depth > max_depth:
            continue

        try:
            res = fetch_with_retries(current_url, headers)
            soup = BeautifulSoup(res.text, 'html.parser')

            links = set()
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if href.startswith(("mailto:", "tel:", "#", "javascript:")):
                    continue

                joined_url = urljoin(current_url, href)
                if is_same_domain(base_url, joined_url) and joined_url not in visited:
                    links.add(joined_url)

            for link in links:
                to_visit.append((link, depth + 1))
                found_links.append(link)

            sleep(1)

        except Exception as e:
            print(f"Failed to fetch links from {current_url}: {e}")

    return list(set(found_links))

def save_to_jsonl(data_list, output_file="website_guide.jsonl"):
    with open(output_file, "w", encoding='utf-8') as f:
        for entry in data_list:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

def build_website_guide(base_url, output_file=None):
    print("call the function")
    if not output_file:
        domain = get_domain(base_url)
        output_file = f"{domain}_guide.jsonl"
    
    print(f"Starting scan for: {base_url}")
    all_links = get_all_links(base_url)
    all_links = list(set([base_url] + all_links))
    print(f"Total pages to process: {len(all_links)}")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }

    data = []
    for link in all_links:
        entry = scrape_page(link, headers)
        if entry:
            data.append(entry)

    save_to_jsonl(data, output_file)
    print(f"Website guide saved to {output_file}")
    return output_file