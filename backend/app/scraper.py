from playwright.async_api import async_playwright
import base64
import asyncio
from urllib.parse import urljoin, urlparse
import os

class WebScraper:
    async def scrape(self, url: str):
        async with async_playwright() as p:
            browser = await p.chromium.launch(
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
                await page.wait_for_timeout(8000)
                
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
                    except:
                        pass
                
                screenshot = await page.screenshot(full_page=True, type='jpeg', quality=80)
                screenshot_b64 = base64.b64encode(screenshot).decode('utf-8')

                title = await page.title()
                html = await page.content()

                design_context = await self._extract_comprehensive_design_context(page, url)
                
                image_analysis = await self._analyze_key_images(page, url)

                return {
                    "url": url,
                    "title": title,
                    "screenshot_b64": screenshot_b64,
                    "screenshot_size": len(screenshot_b64),
                    "html_size": len(html),
                    "design_context": design_context,
                    "image_analysis": image_analysis,  
                    "status": "success"
                }
            finally:
                await browser.close()

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
        for img in image_data:
            enhanced_img = img.copy()
            
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
