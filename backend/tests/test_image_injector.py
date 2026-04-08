from app.services.image_injector import inject_images, FALLBACK_SVG


class TestInjectImages:
    def test_replaces_single_marker(self):
        html = '<img src="__IMG_PLACEHOLDER_0__">'
        images = {"__IMG_PLACEHOLDER_0__": "data:image/png;base64,abc"}
        result = inject_images(html, images)
        assert result == '<img src="data:image/png;base64,abc">'

    def test_replaces_multiple_markers(self):
        html = '<img src="__IMG_PLACEHOLDER_0__"><img src="__IMG_PLACEHOLDER_1__">'
        images = {
            "__IMG_PLACEHOLDER_0__": "data:image/png;base64,aaa",
            "__IMG_PLACEHOLDER_1__": "data:image/png;base64,bbb",
        }
        result = inject_images(html, images)
        assert "data:image/png;base64,aaa" in result
        assert "data:image/png;base64,bbb" in result

    def test_unmatched_markers_get_fallback_svg(self):
        html = '<img src="__IMG_PLACEHOLDER_5__">'
        result = inject_images(html, {})
        assert FALLBACK_SVG in result
        assert "__IMG_PLACEHOLDER_5__" not in result

    def test_matched_markers_not_replaced_with_fallback(self):
        html = '<img src="__IMG_PLACEHOLDER_0__"><img src="__IMG_PLACEHOLDER_1__">'
        images = {"__IMG_PLACEHOLDER_0__": "data:image/png;base64,real"}
        result = inject_images(html, images)
        assert "data:image/png;base64,real" in result
        assert FALLBACK_SVG in result  # placeholder 1 gets fallback

    def test_no_markers_returns_unchanged(self):
        html = "<h1>Hello World</h1>"
        result = inject_images(html, {})
        assert result == html

    def test_empty_html(self):
        result = inject_images("", {})
        assert result == ""

    def test_duplicate_markers_both_replaced(self):
        html = '__IMG_PLACEHOLDER_0__ and __IMG_PLACEHOLDER_0__'
        images = {"__IMG_PLACEHOLDER_0__": "data:image/png;base64,dup"}
        result = inject_images(html, images)
        assert result == "data:image/png;base64,dup and data:image/png;base64,dup"
