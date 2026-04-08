import pytest
from app.services.crawler import CrawlerService


class TestExtractInternalLinks:
    def setup_method(self):
        self.crawler = CrawlerService()
        self.base = "https://example.com"

    def test_extracts_same_domain_links(self):
        links = [
            {"href": "https://example.com/about"},
            {"href": "https://example.com/contact"},
        ]
        result = self.crawler.extract_internal_links(links, self.base)
        assert "https://example.com/about" in result
        assert "https://example.com/contact" in result

    def test_resolves_relative_links(self):
        links = [{"href": "/about"}, {"href": "/blog/post-1"}]
        result = self.crawler.extract_internal_links(links, self.base)
        assert "https://example.com/about" in result
        assert "https://example.com/blog/post-1" in result

    def test_excludes_external_links(self):
        links = [
            {"href": "https://other.com/page"},
            {"href": "https://example.com/internal"},
        ]
        result = self.crawler.extract_internal_links(links, self.base)
        assert len(result) == 1
        assert "https://example.com/internal" in result

    def test_excludes_fragment_only_links(self):
        links = [{"href": "#section"}]
        result = self.crawler.extract_internal_links(links, self.base)
        assert len(result) == 0

    def test_excludes_mailto_links(self):
        links = [{"href": "mailto:user@example.com"}]
        result = self.crawler.extract_internal_links(links, self.base)
        assert len(result) == 0

    def test_excludes_javascript_links(self):
        links = [{"href": "javascript:void(0)"}]
        result = self.crawler.extract_internal_links(links, self.base)
        assert len(result) == 0

    def test_strips_fragments_from_urls(self):
        links = [{"href": "https://example.com/page#section"}]
        result = self.crawler.extract_internal_links(links, self.base)
        assert "https://example.com/page" in result

    def test_strips_trailing_slashes(self):
        links = [{"href": "https://example.com/page/"}]
        result = self.crawler.extract_internal_links(links, self.base)
        assert "https://example.com/page" in result

    def test_deduplicates_links(self):
        links = [
            {"href": "https://example.com/page"},
            {"href": "https://example.com/page/"},
            {"href": "https://example.com/page#top"},
        ]
        result = self.crawler.extract_internal_links(links, self.base)
        assert len(result) == 1

    def test_empty_href_skipped(self):
        links = [{"href": ""}, {}]
        result = self.crawler.extract_internal_links(links, self.base)
        assert len(result) == 0

    def test_empty_input(self):
        result = self.crawler.extract_internal_links([], self.base)
        assert result == []
