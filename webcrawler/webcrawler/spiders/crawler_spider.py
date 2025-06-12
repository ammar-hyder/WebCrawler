import scrapy
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import json
import os
import time


class CrawlerSpider(scrapy.Spider):
    name = "crawler_spider"
    MAX_PAGES = 10  # Maximum number of pages to crawl

    def __init__(self, start_url=None, *args, **kwargs):
        super(CrawlerSpider, self).__init__(*args, **kwargs)
        # This makes the class variables instance variables to prevent issues with
        # concurrent spiders (if needed in the future)
        self.visited = set()  # Set to track visited URLs
        self.results = []  # List to store the extracted data

        if start_url:
            self.start_urls = [start_url]
            parsed_domain = urlparse(start_url).netloc
            self.allowed_domains = [parsed_domain]
        else:
            self.start_urls = [
                "https://en.wikipedia.org/wiki/Web_scraping",
                "https://en.wikipedia.org/wiki/Scrapy"
            ]
            self.allowed_domains = ["wikipedia.org"]

        # Initialize the output file
        self.output_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                                        "crawled_data.json")
        # Create empty file if it doesn't exist
        with open(self.output_file, "w", encoding="utf-8") as f:
            json.dump([], f)

        self.logger.info(f"Spider initialized with start URL: {self.start_urls[0]}")
        self.logger.info(f"Results will be saved to: {self.output_file}")

    def parse(self, response):
        # Check if max pages reached
        if len(self.visited) >= self.MAX_PAGES:
            self.logger.info(f"Maximum number of pages ({self.MAX_PAGES}) reached. Stopping crawler.")
            # Close the spider gracefully
            self.crawler.engine.close_spider(self, reason='max_pages_reached')
            return

        url = response.url

        if url in self.visited:
            return  # Skip already visited URLs

        self.visited.add(url)
        self.logger.info(f"Crawling URL: {url} [{len(self.visited)}/{self.MAX_PAGES}]")

        # Extract info directly from Scrapy response
        page_data = {
            "url": url,
            "title": response.css('title::text').get() or "No title",
            "text": ' '.join(response.css('body ::text').getall()),
            "images": [],
            "links": [],
            "word_count": len(' '.join(response.css('body ::text').getall()).split()),
            "image_count": 0
        }

        # Extract image URLs
        for img in response.css('img[src]'):
            src = urljoin(url, img.attrib.get('src', ''))
            if src:
                page_data["images"].append(src)
                page_data["image_count"] += 1

        # Extract valid internal links
        for link in response.css('a[href]'):
            href = urljoin(url, link.attrib.get('href', ''))
            if self.is_valid_url(href):
                page_data["links"].append(href)
                # Only queue new requests if we haven't reached the limit
                if len(self.visited) < self.MAX_PAGES:
                    yield scrapy.Request(href, callback=self.parse)

        self.results.append(page_data)
        self.save_results()  # Save results after each page

    def is_valid_url(self, url):
        """Check if URL is valid and in the allowed domains."""
        try:
            parsed = urlparse(url)
            # Make sure it's http or https and in the allowed domain
            return (parsed.scheme in ["http", "https"] and
                    any(domain in parsed.netloc for domain in self.allowed_domains))
        except Exception:
            return False

    def save_results(self):
        """Save results to a JSON file."""
        try:
            with open(self.output_file, "w", encoding="utf-8") as f:
                json.dump(self.results, f, indent=2, ensure_ascii=False)
                # Ensure data is written to disk
                f.flush()
                os.fsync(f.fileno())
            self.logger.info(f"Crawling results saved to {self.output_file} ({len(self.results)} pages)")
        except Exception as e:
            self.logger.error(f"Error saving results: {e}")

    def closed(self, reason):
        """Called when the spider is closed."""
        # Make sure results are saved when spider closes
        self.save_results()
        self.logger.info(
            f"Spider closed: {reason}. Final count: {len(self.visited)} pages visited, {len(self.results)} pages saved.")

        # Extra safety - wait a moment to ensure file operations complete
        time.sleep(0.5)