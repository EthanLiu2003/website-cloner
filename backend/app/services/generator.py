import asyncio
from anthropic import AsyncAnthropic
from ..config import settings
from .image_injector import inject_images


class GeneratorService:
    def __init__(self):
        self.client = None

    def _get_client(self):
        if not self.client:
            self.client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        return self.client

    async def generate_clone(self, scrape_result: dict, url: str) -> str:
        client = self._get_client()

        design_context = scrape_result.get('design_context', {})
        image_analysis = scrape_result.get('image_analysis', {})
        screenshot_b64 = scrape_result.get('screenshot_b64', '')
        has_downloaded_images = bool(scrape_result.get('downloaded_images'))

        # Build image instructions based on whether we have real images to inject
        if has_downloaded_images:
            image_lines = []
            for img in image_analysis.get('key_images', [])[:10]:
                marker = img.get('marker_id', '')
                alt = img.get('alt', img.get('imageType', 'image'))
                obj_fit = img.get('style', {}).get('objectFit', 'cover')
                border_radius = img.get('style', {}).get('borderRadius', '0px')
                image_lines.append(
                    f"- {img['imageType'].title()}: <img src=\"{marker}\" "
                    f"alt=\"{alt}\" style=\"width:{img['width']}px; max-width:100%; "
                    f"height:{img['height']}px; object-fit:{obj_fit}; "
                    f"border-radius:{border_radius};\">"
                )
            image_section = f"""**CRITICAL REQUIREMENTS FOR IMAGES:**

1. **Use exact placeholder markers**: For each image listed below, use an <img> tag with the EXACT src value provided. The src values are special markers that will be replaced with real images after generation.

2. **Marker format**: Each image src looks like `__IMG_PLACEHOLDER_0__`, `__IMG_PLACEHOLDER_1__`, etc. Use these EXACT strings as the src attribute. Do NOT modify them.

3. **Preserve dimensions**: Use the width/height/aspect-ratio provided for each image. Apply appropriate object-fit and any detected border-radius.

4. **For images without a marker**, use a simple colored div as fallback.

**IMAGES WITH MARKERS:**
{chr(10).join(image_lines)}"""
        else:
            image_section = f"""**KEY IMAGES TO RECREATE:**
{chr(10).join([f"- {img['imageType'].title()}: {img['width']}x{img['height']}px ({img['aspectRatio']} ratio) - {img['placeholder']}" for img in image_analysis.get('key_images', [])[:10]])}

**CRITICAL REQUIREMENTS:**

1. **Image Placeholders**: For each image type, create appropriate placeholders:
- **Logo images**: Use company name in a styled box
- **Product images**: Use attractive gradient backgrounds with "Product Image" text
- **Hero banners**: Use compelling gradient backgrounds with engaging text
- **Icons**: Use CSS shapes or emoji equivalents
- **Content images**: Use subtle background patterns

2. **Image Styling**: Match the original image dimensions and styling:
- Use the exact aspect ratios provided
- Apply border-radius, filters, and object-fit properties as detected
- Position images correctly within their containers"""

        text_prompt = f"""I've attached a screenshot of the original website. Recreate it as closely as possible in a single HTML document with inline CSS.

You are an expert web designer. Create a high-fidelity HTML clone based on this comprehensive analysis:

**ORIGINAL WEBSITE:**
URL: {url}
Title: {scrape_result.get('title', 'Unknown')}

**DESIGN ANALYSIS:**
- Typography: {design_context.get('typography', {})}
- Colors: {design_context.get('colors', {})}
- Layout: {design_context.get('structure', [])}
- Navigation: {design_context.get('navigation', [])}

**IMAGE ANALYSIS:**
- Total images: {image_analysis.get('total_images', 0)}
- Image types: {image_analysis.get('image_types', {})}
- Above fold images: {image_analysis.get('above_fold_images', 0)}

{image_section}

Generate a complete HTML document that recreates the visual impact of the original website with responsive design."""

        # Build message content - USE VISION if screenshot available
        content = []
        if screenshot_b64:
            # Truncate screenshot if too large (max ~5MB for Claude)
            if len(screenshot_b64) < 5_000_000:
                content.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": screenshot_b64
                    }
                })
        content.append({"type": "text", "text": text_prompt})

        response = await asyncio.wait_for(
            client.messages.create(
                model=settings.ai_model,
                max_tokens=settings.max_tokens,
                messages=[{"role": "user", "content": content}]
            ),
            timeout=settings.ai_timeout
        )

        html = response.content[0].text
        # Strip markdown code fences if present
        if html.startswith("```html"):
            html = html[7:]
        if html.startswith("```"):
            html = html[3:]
        if html.endswith("```"):
            html = html[:-3]
        html = html.strip()

        # Inject real images if available
        downloaded_images = scrape_result.get('downloaded_images', {})
        if downloaded_images:
            html = inject_images(html, downloaded_images)

        return html


generator_service = GeneratorService()
