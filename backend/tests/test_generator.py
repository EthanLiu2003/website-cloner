import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.generator import GeneratorService


class TestGeneratorService:
    def setup_method(self):
        self.service = GeneratorService()

    def _mock_claude_response(self, html_text):
        """Create a mock Anthropic response."""
        block = MagicMock()
        block.text = html_text
        response = MagicMock()
        response.content = [block]
        return response

    @pytest.mark.asyncio
    async def test_strips_html_code_fences(self):
        raw = "```html\n<h1>Hello</h1>\n```"
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(
            return_value=self._mock_claude_response(raw)
        )
        self.service.client = mock_client

        result = await self.service.generate_clone(
            {"screenshot_b64": "", "design_context": {}, "image_analysis": {}},
            "https://example.com",
        )
        assert result == "<h1>Hello</h1>"

    @pytest.mark.asyncio
    async def test_strips_generic_code_fences(self):
        raw = "```\n<div>Content</div>\n```"
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(
            return_value=self._mock_claude_response(raw)
        )
        self.service.client = mock_client

        result = await self.service.generate_clone(
            {"screenshot_b64": "", "design_context": {}, "image_analysis": {}},
            "https://example.com",
        )
        assert result == "<div>Content</div>"

    @pytest.mark.asyncio
    async def test_injects_downloaded_images(self):
        raw = '<img src="__IMG_PLACEHOLDER_0__">'
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(
            return_value=self._mock_claude_response(raw)
        )
        self.service.client = mock_client

        scrape_result = {
            "screenshot_b64": "",
            "design_context": {},
            "image_analysis": {},
            "downloaded_images": {
                "__IMG_PLACEHOLDER_0__": "data:image/png;base64,abc123"
            },
        }
        result = await self.service.generate_clone(scrape_result, "https://example.com")
        assert "data:image/png;base64,abc123" in result
        assert "__IMG_PLACEHOLDER_0__" not in result

    @pytest.mark.asyncio
    async def test_includes_screenshot_in_vision_request(self):
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(
            return_value=self._mock_claude_response("<p>hi</p>")
        )
        self.service.client = mock_client

        await self.service.generate_clone(
            {
                "screenshot_b64": "smallbase64data",
                "design_context": {},
                "image_analysis": {},
            },
            "https://example.com",
        )

        call_kwargs = mock_client.messages.create.call_args.kwargs
        messages = call_kwargs["messages"]
        content = messages[0]["content"]
        # First content block should be the image
        assert content[0]["type"] == "image"
        assert content[0]["source"]["data"] == "smallbase64data"

    @pytest.mark.asyncio
    async def test_skips_oversized_screenshot(self):
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(
            return_value=self._mock_claude_response("<p>hi</p>")
        )
        self.service.client = mock_client

        # 6MB screenshot should be skipped
        big_screenshot = "x" * 6_000_000
        await self.service.generate_clone(
            {
                "screenshot_b64": big_screenshot,
                "design_context": {},
                "image_analysis": {},
            },
            "https://example.com",
        )

        call_kwargs = mock_client.messages.create.call_args.kwargs
        content = call_kwargs["messages"][0]["content"]
        # Should only have the text block, no image
        assert len(content) == 1
        assert content[0]["type"] == "text"
