from playwright.async_api import async_playwright
import base64
import asyncio
import logging
from urllib.parse import urljoin, urlparse
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from ..config import settings

logger = logging.getLogger(__name__)


class WebScraper:
    def __init__(self):
        self._browsers = []
        self._browser_semaphore = None
        self._playwright = None

    async def start(self):
        """Start browser pool."""
        self._playwright = await async_playwright().start()
        self._browser_semaphore = asyncio.Semaphore(settings.browser_pool_size)
        for _ in range(settings.browser_pool_size):
            browser = await self._playwright.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-blink-features=AutomationControlled',
                    '--disable-web-security',
                    '--disable-features=VizDisplayCompositor',
                    '--disable-dev-shm-usage',
                    '--no-first-run',
                    '--disable-extensions',
                    '--disable-default-apps'
                ]
            )
            self._browsers.append(browser)

    async def stop(self):
        """Stop browser pool."""
        for browser in self._browsers:
            try:
                await browser.close()
            except Exception:
                pass
        self._browsers.clear()
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None

    async def _get_browser(self):
        """Get an available browser from the pool."""
        if not self._browsers:
            # Fallback: start a single browser if pool not initialized
            await self.start()
        await self._browser_semaphore.acquire()
        # Round-robin: use the first browser (they're all equivalent)
        return self._browsers[0] if self._browsers else None

    def _release_browser(self):
        """Release a browser back to the pool."""
        if self._browser_semaphore:
            self._browser_semaphore.release()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((TimeoutError, ConnectionError)),
    )
    async def scrape(self, url: str):
        browser = await self._get_browser()
        try:
            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                extra_http_headers={
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                }
            )

            page = await context.new_page()

            await page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined,
                });

                window.chrome = {
                    runtime: {}
                };

                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5],
                });
            """)

            try:
                await page.goto(url, wait_until='domcontentloaded', timeout=45000)
                await page.wait_for_timeout(3000)

                page_content = await page.content()
                if any(keyword in page_content.lower() for keyword in [
                    'checking your browser', 'cloudflare', 'security check',
                    'please wait', 'verifying', 'ddos protection'
                ]):
                    print("Detected security check, waiting longer...")
                    await page.wait_for_timeout(10000)

                    try:
                        await page.wait_for_selector('body', timeout=15000)
                        await page.wait_for_load_state('networkidle', timeout=15000)
                    except Exception:
                        pass

                screenshot = await page.screenshot(full_page=True, type='jpeg', quality=80)
                screenshot_b64 = base64.b64encode(screenshot).decode('utf-8')

                title = await page.title()
                html = await page.content()

                design_context = await self._extract_comprehensive_design_context(page, url)
                image_analysis = await self._analyze_key_images(page, url)
                internal_links = await self._scrape_links(page, url)

                downloaded_images = await self._download_images(
                    page, image_analysis.get('key_images', [])
                )

                return {
                    "url": url,
                    "title": title,
                    "screenshot_b64": screenshot_b64,
                    "screenshot_size": len(screenshot_b64),
                    "html_size": len(html),
                    "design_context": design_context,
                    "image_analysis": image_analysis,
                    "internal_links": internal_links,
                    "downloaded_images": downloaded_images,
                    "status": "success"
                }
            finally:
                await context.close()
        finally:
            self._release_browser()

    async def _scrape_links(self, page, url: str):
        """Extract all internal links from the page."""
        links = await page.evaluate(f"""
        () => {{
            const baseUrl = '{url}';
            const links = [];
            document.querySelectorAll('a[href]').forEach(a => {{
                links.push({{
                    href: a.href,
                    text: a.textContent.trim().substring(0, 100)
                }});
            }});
            return links;
        }}
        """)
        return links

    async def _analyze_key_images(self, page, url):

        image_data = await page.evaluate(f"""
        () => {{
            const images = [];
            const baseUrl = '{url}';

            document.querySelectorAll('img').forEach((img, index) => {{
                const rect = img.getBoundingClientRect();
                const style = getComputedStyle(img);

                // Only analyze visible, significant images
                if (rect.width > 50 && rect.height > 50 && rect.top < window.innerHeight + 500) {{

                    // Determine image type/purpose
                    let imageType = 'unknown';
                    const src = img.src.toLowerCase();
                    const alt = (img.alt || '').toLowerCase();
                    const className = (img.className || '').toLowerCase();

                    if (alt.includes('logo') || className.includes('logo') || src.includes('logo')) {{
                        imageType = 'logo';
                    }} else if (alt.includes('product') || className.includes('product') || src.includes('product')) {{
                        imageType = 'product';
                    }} else if (rect.width > 800 || rect.height > 400) {{
                        imageType = 'hero';
                    }} else if (className.includes('icon') || rect.width < 100) {{
                        imageType = 'icon';
                    }} else {{
                        imageType = 'content';
                    }}

                    images.push({{
                        src: img.src,
                        alt: img.alt || '',
                        width: rect.width,
                        height: rect.height,
                        aspectRatio: (rect.width / rect.height).toFixed(2),
                        position: {{
                            top: rect.top,
                            left: rect.left
                        }},
                        style: {{
                            objectFit: style.objectFit,
                            borderRadius: style.borderRadius,
                            filter: style.filter
                        }},
                        imageType: imageType,
                        isAboveFold: rect.top < window.innerHeight,
                        className: img.className || '',
                        parentTag: img.parentElement ? img.parentElement.tagName.toLowerCase() : 'unknown'
                    }});
                }}
            }});

            images.sort((a, b) => {{
                if (a.imageType === 'logo' && b.imageType !== 'logo') return -1;
                if (b.imageType === 'logo' && a.imageType !== 'logo') return 1;
                if (a.isAboveFold && !b.isAboveFold) return -1;
                if (b.isAboveFold && !a.isAboveFold) return 1;
                return (b.width * b.height) - (a.width * a.height);
            }});

            return images.slice(0, 20); // Top 20 most important images
        }}
        """)

        enhanced_images = []
        for index, img in enumerate(image_data):
            enhanced_img = img.copy()
            enhanced_img['marker_id'] = f"__IMG_PLACEHOLDER_{index}__"

            if img['imageType'] == 'logo':
                enhanced_img['placeholder'] = f"Logo placeholder ({img['width']}x{img['height']}px)"
                enhanced_img['placeholder_style'] = "background: #f0f0f0; display: flex; align-items: center; justify-content: center; font-weight: bold; color: #666;"
            elif img['imageType'] == 'product':
                enhanced_img['placeholder'] = f"Product image ({img['aspectRatio']} ratio)"
                enhanced_img['placeholder_style'] = "background: linear-gradient(135deg, #f5f5f5 0%, #e0e0e0 100%); display: flex; align-items: center; justify-content: center; color: #999;"
            elif img['imageType'] == 'hero':
                enhanced_img['placeholder'] = f"Hero banner ({img['width']}x{img['height']}px)"
                enhanced_img['placeholder_style'] = "background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); display: flex; align-items: center; justify-content: center; color: white; font-size: 24px;"
            elif img['imageType'] == 'icon':
                enhanced_img['placeholder'] = f"Icon ({img['width']}x{img['height']}px)"
                enhanced_img['placeholder_style'] = "background: #e8e8e8; border-radius: 50%; display: flex; align-items: center; justify-content: center; color: #666;"
            else:
                enhanced_img['placeholder'] = f"Image ({img['aspectRatio']} ratio)"
                enhanced_img['placeholder_style'] = "background: #f8f8f8; display: flex; align-items: center; justify-content: center; color: #aaa;"

            enhanced_images.append(enhanced_img)

        return {
            "total_images": len(image_data),
            "key_images": enhanced_images,
            "image_types": {
                "logos": len([img for img in image_data if img['imageType'] == 'logo']),
                "products": len([img for img in image_data if img['imageType'] == 'product']),
                "heroes": len([img for img in image_data if img['imageType'] == 'hero']),
                "icons": len([img for img in image_data if img['imageType'] == 'icon']),
                "content": len([img for img in image_data if img['imageType'] == 'content'])
            },
            "above_fold_images": len([img for img in image_data if img['isAboveFold']])
        }

    async def _download_images(self, page, images: list) -> dict:
        """Download images from the page and return as base64 data URIs."""
        if not settings.enable_image_download or not images:
            return {}

        # Deduplicate by src URL
        seen_srcs = {}
        unique_images = []
        for img in images[:settings.max_image_count]:
            src = img.get('src', '')
            if not src or src.startswith('data:'):
                continue
            if src not in seen_srcs:
                seen_srcs[src] = img['marker_id']
                unique_images.append(img)
            else:
                # Map duplicate to same marker that will get the data
                pass

        downloaded = {}
        total_bytes = 0

        async def download_one(img: dict) -> tuple:
            src = img.get('src', '')
            marker_id = img['marker_id']
            is_svg = src.lower().endswith('.svg')

            # Try canvas approach first (images already in DOM)
            if not is_svg:
                try:
                    data_uri = await page.evaluate("""
                    (src) => {
                        return new Promise((resolve, reject) => {
                            const img = new Image();
                            img.crossOrigin = 'anonymous';
                            img.onload = () => {
                                try {
                                    const canvas = document.createElement('canvas');
                                    canvas.width = img.naturalWidth;
                                    canvas.height = img.naturalHeight;
                                    canvas.getContext('2d').drawImage(img, 0, 0);
                                    resolve(canvas.toDataURL('image/webp', 0.8));
                                } catch(e) {
                                    reject(e.message);
                                }
                            };
                            img.onerror = () => reject('load failed');
                            img.src = src;
                            setTimeout(() => reject('timeout'), 6000);
                        });
                    }
                    """, src)
                    if data_uri:
                        return (marker_id, data_uri)
                except Exception:
                    pass

            # Fallback: fetch via Playwright's request context
            try:
                response = await page.request.get(src)
                if response.ok:
                    body = await response.body()
                    content_type = response.headers.get('content-type', 'image/png')
                    if ';' in content_type:
                        content_type = content_type.split(';')[0].strip()
                    b64 = base64.b64encode(body).decode('utf-8')
                    return (marker_id, f"data:{content_type};base64,{b64}")
            except Exception as e:
                logger.debug(f"Failed to download image {src}: {e}")

            return (marker_id, None)

        # Download concurrently with timeout
        tasks = [
            asyncio.wait_for(
                download_one(img),
                timeout=settings.image_download_timeout
            )
            for img in unique_images
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, Exception):
                continue
            marker_id, data_uri = result
            if not data_uri:
                continue

            # Estimate size (base64 data URIs)
            uri_size = len(data_uri)
            if uri_size > settings.max_image_size_bytes:
                logger.debug(f"Skipping {marker_id}: {uri_size} bytes exceeds limit")
                continue
            if total_bytes + uri_size > settings.max_total_image_bytes:
                logger.debug(f"Total image size limit reached, stopping downloads")
                break
            total_bytes += uri_size
            downloaded[marker_id] = data_uri

        # Map duplicates to the same data URI
        for img in images[:settings.max_image_count]:
            src = img.get('src', '')
            marker = img['marker_id']
            if marker not in downloaded and src in seen_srcs:
                original_marker = seen_srcs[src]
                if original_marker in downloaded:
                    downloaded[marker] = downloaded[original_marker]

        logger.info(f"Downloaded {len(downloaded)}/{len(unique_images)} images ({total_bytes} bytes)")
        return downloaded

    async def _extract_comprehensive_design_context(self, page, url):
        """Extract comprehensive design information for LLM"""

        context = await page.evaluate(f"""
        () => {{
            const url = '{url}';
            const getComputedStyle = window.getComputedStyle;
            const body = document.body;
            const html = document.documentElement;

            const layoutInfo = {{
                bodyDisplay: getComputedStyle(body).display,
                bodyWidth: body.scrollWidth,
                bodyHeight: body.scrollHeight,
                viewportWidth: window.innerWidth,
                viewportHeight: window.innerHeight
            }};

            const colors = new Set();
            const backgroundColors = new Set();
            const textColors = new Set();

            document.querySelectorAll('*').forEach(el => {{
                const style = getComputedStyle(el);
                if (style.backgroundColor && style.backgroundColor !== 'rgba(0, 0, 0, 0)') {{
                    backgroundColors.add(style.backgroundColor);
                    colors.add(style.backgroundColor);
                }}
                if (style.color) {{
                    textColors.add(style.color);
                    colors.add(style.color);
                }}
                if (style.borderColor && style.borderColor !== 'rgba(0, 0, 0, 0)') {{
                    colors.add(style.borderColor);
                }}
            }});

            const fonts = new Set();
            const headings = [];

            document.querySelectorAll('h1, h2, h3, h4, h5, h6').forEach(h => {{
                const style = getComputedStyle(h);
                fonts.add(style.fontFamily);
                headings.push({{
                    tag: h.tagName.toLowerCase(),
                    text: h.textContent.trim().substring(0, 100),
                    fontSize: style.fontSize,
                    fontWeight: style.fontWeight,
                    color: style.color,
                    fontFamily: style.fontFamily,
                    marginTop: style.marginTop,
                    marginBottom: style.marginBottom
                }});
            }});

            const bodyFont = getComputedStyle(body).fontFamily;
            fonts.add(bodyFont);

            const navigation = [];
            document.querySelectorAll('nav, .nav, .navbar, .navigation, .menu').forEach(nav => {{
                const links = Array.from(nav.querySelectorAll('a')).map(a => ({{
                    text: a.textContent.trim(),
                    href: a.href,
                    isInternal: a.href.startsWith(url) || a.href.startsWith('/')
                }}));

                if (links.length > 0) {{
                    navigation.push({{
                        element: nav.tagName + (nav.className ? '.' + nav.className.split(' ').join('.') : ''),
                        links: links.slice(0, 10),
                        style: {{
                            backgroundColor: getComputedStyle(nav).backgroundColor,
                            padding: getComputedStyle(nav).padding,
                            position: getComputedStyle(nav).position
                        }}
                    }});
                }}
            }});

            // Layout structure
            const layoutStructure = [];
            const mainContainers = document.querySelectorAll('main, .main, .container, .wrapper, .content, header, footer, .header, .footer');

            mainContainers.forEach(container => {{
                const rect = container.getBoundingClientRect();
                const style = getComputedStyle(container);

                layoutStructure.push({{
                    tag: container.tagName.toLowerCase(),
                    className: container.className,
                    dimensions: {{
                        width: rect.width,
                        height: rect.height,
                        top: rect.top
                    }},
                    style: {{
                        display: style.display,
                        flexDirection: style.flexDirection,
                        justifyContent: style.justifyContent,
                        alignItems: style.alignItems,
                        gridTemplateColumns: style.gridTemplateColumns,
                        padding: style.padding,
                        margin: style.margin,
                        backgroundColor: style.backgroundColor
                    }}
                }});
            }});

            const contentStructure = {{
                paragraphs: document.querySelectorAll('p').length,
                images: document.querySelectorAll('img').length,
                buttons: Array.from(document.querySelectorAll('button, .button, .btn')).map(btn => ({{
                    text: btn.textContent.trim(),
                    style: {{
                        backgroundColor: getComputedStyle(btn).backgroundColor,
                        color: getComputedStyle(btn).color,
                        borderRadius: getComputedStyle(btn).borderRadius,
                        padding: getComputedStyle(btn).padding
                    }}
                }})).slice(0, 5),
                forms: document.querySelectorAll('form').length,
                lists: document.querySelectorAll('ul, ol').length
            }};

            const responsiveInfo = {{
                hasViewportMeta: !!document.querySelector('meta[name="viewport"]'),
                hasMediaQueries: Array.from(document.styleSheets).some(sheet => {{
                    try {{
                        return Array.from(sheet.cssRules || []).some(rule =>
                            rule.type === CSSRule.MEDIA_RULE
                        );
                    }} catch(e) {{ return false; }}
                }}),
                flexboxUsage: Array.from(document.querySelectorAll('*')).filter(el =>
                    getComputedStyle(el).display === 'flex'
                ).length,
                gridUsage: Array.from(document.querySelectorAll('*')).filter(el =>
                    getComputedStyle(el).display === 'grid'
                ).length
            }};

            return {{
                layout: layoutInfo,
                colors: {{
                    all: Array.from(colors).slice(0, 15),
                    backgrounds: Array.from(backgroundColors).slice(0, 8),
                    text: Array.from(textColors).slice(0, 5)
                }},
                typography: {{
                    fonts: Array.from(fonts).slice(0, 5),
                    headings: headings.slice(0, 8),
                    bodyFont: bodyFont
                }},
                navigation: navigation.slice(0, 3),
                structure: layoutStructure.slice(0, 10),
                content: contentStructure,
                responsive: responsiveInfo
            }};
        }}
        """)

        return context


scraper_service = WebScraper()
