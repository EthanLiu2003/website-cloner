from urllib.parse import urljoin, urlparse
from typing import List
from ..config import settings


class CrawlerService:
    def extract_internal_links(self, html_links: list, base_url: str) -> List[str]:
        """Filter and normalize internal links."""
        parsed_base = urlparse(base_url)
        internal = set()

        for link in html_links:
            href = link.get('href', '')
            if not href or href.startswith('#') or href.startswith('mailto:') or href.startswith('javascript:'):
                continue

            full_url = urljoin(base_url, href)
            parsed = urlparse(full_url)

            # Same domain only
            if parsed.netloc == parsed_base.netloc:
                # Normalize: remove fragment, keep path
                clean = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                if clean.endswith('/'):
                    clean = clean[:-1]
                internal.add(clean)

        return list(internal)

    async def crawl(self, scraper, start_url: str, max_depth: int = None, max_pages: int = None) -> List[str]:
        """BFS crawl to discover pages."""
        max_depth = max_depth or settings.max_crawl_depth
        max_pages = max_pages or settings.max_crawl_pages

        visited = set()
        to_visit = [(start_url, 0)]  # (url, depth)
        discovered = []

        while to_visit and len(discovered) < max_pages:
            url, depth = to_visit.pop(0)

            normalized = url.rstrip('/')
            if normalized in visited:
                continue
            visited.add(normalized)
            discovered.append(url)

            if depth >= max_depth:
                continue

            # Scrape page to find links
            try:
                result = await scraper.scrape(url)
                raw_links = result.get('internal_links', [])
                links = self.extract_internal_links(raw_links, url)
                for link in links:
                    norm_link = link.rstrip('/')
                    if norm_link not in visited:
                        to_visit.append((link, depth + 1))
            except Exception:
                continue

        return discovered


crawler_service = CrawlerService()
