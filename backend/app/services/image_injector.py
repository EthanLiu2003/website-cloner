import re

FALLBACK_SVG = (
    "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' "
    "width='400' height='300'%3E%3Crect fill='%23f0f0f0' width='400' "
    "height='300'/%3E%3Ctext x='50%25' y='50%25' text-anchor='middle' "
    "dy='.3em' fill='%23999' font-family='sans-serif'%3EImage%3C/text%3E%3C/svg%3E"
)

_MARKER_PATTERN = re.compile(r'__IMG_PLACEHOLDER_\d+__')


def inject_images(html: str, downloaded_images: dict) -> str:
    """Replace __IMG_PLACEHOLDER_N__ markers with base64 data URIs."""
    for marker_id, data_uri in downloaded_images.items():
        html = html.replace(marker_id, data_uri)

    # Replace any remaining unmatched markers with SVG fallback
    html = _MARKER_PATTERN.sub(FALLBACK_SVG, html)
    return html
