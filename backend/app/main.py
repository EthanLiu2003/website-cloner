from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
from dotenv import load_dotenv
from anthropic import AsyncAnthropic
from .scraper import WebScraper
from pydantic import BaseModel
from fastapi import BackgroundTasks
import uuid
from typing import Dict
from fastapi.responses import HTMLResponse
import asyncio


#load environment (security)
load_dotenv()

app = FastAPI(title = "Website Cloner API")

#Middleware to handle same-origin policy so that frontend and backend can interact
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

scraper = WebScraper()

@app.get("/")
def read_root():
    return {"message": "Website Cloner API running"}

#Check server
@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "environment_loaded": True,
        "test_var": os.getenv("TEST_VAR", "not_set")
    }

#Claude API call
@app.get("/test-ai")
async def test_ai():
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return {"Error": "API key not configured"}
    try:
        client = AsyncAnthropic(api_key = api_key)
        response = await client.messages.create(
            model = "claude-sonnet-4-20250514",
            max_tokens = 100,
            messages = [{"role": "user", "content": "Say hello, confirm you're working!"}]
        )
        return {"ai_status": "working", "response": response.content[0].text}
    except Exception as e:
        return{"error": str(e)}

# Add new test endpoints
@app.get("/test-scrape-simple")
async def test_scrape_simple():
    try:
        result = await asyncio.wait_for(scraper.scrape("https://httpbin.org/html"), timeout=15.0)
        return {"success": True, "result": result}
    except Exception as e:
        return {"success": False, "error": str(e)}

    
#WebScraping
@app.get("/test-scrape")
async def test_scrape():
    try:
        result = await scraper.scrape("https://example.com")
        return result
    except Exception as e:
        return {"error": str(e)}

#CloneEndpoint
class CloneRequest(BaseModel):
    url:str

#Keeping track of jobs
jobs: Dict[str, dict] = {}
cloned_sites: Dict[str, str] = {}

@app.post("/api/clone")
async def start_clone(request: CloneRequest, background_tasks: BackgroundTasks):
    job_id = str(uuid.uuid4())
    jobs[job_id] = {"status": "started", "progress": 0}
    background_tasks.add_task(process_clone_job, job_id, request.url)
    return{"job_id": job_id, "status": "started"}

async def process_clone_job(job_id: str, url: str):
    try:
        jobs[job_id] = {"status": "scraping", "progress": 30, "message": "Scraping website..."}
        
        # Add timeout for scraping
        try:
            scrape_result = await asyncio.wait_for(scraper.scrape(url), timeout=30.0)
            scraping_method = scrape_result.get('scraping_method', 'unknown')
            session_info = f" (Session: {scrape_result.get('session_id', 'N/A')})" if scraping_method == 'hyperbrowser_cloud' else ""
        except asyncio.TimeoutError:
            jobs[job_id] = {"status": "error", "error": "Scraping timed out after 30 seconds"}
            return
        except Exception as e:
            jobs[job_id] = {"status": "error", "error": f"Scraping failed: {str(e)}"}
            return

        jobs[job_id] = {"status": "generating", "progress": 70, "message": "Generating clone..."}

        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            jobs[job_id] = {"status": "error", "error": "API key not configured"}
            return
        
        try:
            client = AsyncAnthropic(api_key=api_key)
            design_context = scrape_result.get('design_context', {})
            image_analysis = scrape_result.get('image_analysis', {})
            prompt = f"""
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

            **KEY IMAGES TO RECREATE:**
            {chr(10).join([f"- {img['imageType'].title()}: {img['width']}x{img['height']}px ({img['aspectRatio']} ratio) - {img['placeholder']}" 
                        for img in image_analysis.get('key_images', [])[:10]])}

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
            - Position images correctly within their containers

            3. **Visual Hierarchy**: Ensure image placeholders maintain the visual weight of originals:
            - Large hero images should be visually prominent
            - Product images should be clean and professional
            - Icons should be subtle but functional

            4. **Responsive Images**: Make all image placeholders responsive and properly sized

            Generate a complete HTML document that recreates the visual impact of the original website, with professional-looking image placeholders that match the detected image types and dimensions.
            """

            response = await asyncio.wait_for(
                client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=10000,
                    messages=[{
                        "role": "user",
                        "content": prompt
                    }]
                ),
                timeout=180.0
            )

            cloned_html = response.content[0].text
            
            jobs[job_id] = {"status": "completed", "progress": 100, "message": "Clone completed!"}
            cloned_sites[job_id] = cloned_html
            
        except asyncio.TimeoutError:
            jobs[job_id] = {"status": "error", "error": "AI generation timed out after 60 seconds"}
            return
        except Exception as e:
            jobs[job_id] = {"status": "error", "error": f"AI generation failed: {str(e)}"}
            return
            
    except Exception as e:
        jobs[job_id] = {"status": "error", "error": f"Unexpected error: {str(e)}"}

@app.get("/api/status/{job_id}")
async def get_status(job_id: str):
    if job_id not in jobs:
        return {"error": "Job not found"}
    job_status = jobs[job_id].copy()
    if job_status.get("status") == "completed" and job_id in cloned_sites:
        job_status["result_url"] = f"/api/preview/{job_id}"
    return job_status

@app.get("/api/preview/{job_id}", response_class=HTMLResponse)
async def get_cloned_website(job_id: str):
    if job_id not in cloned_sites:
        return HTMLResponse(content="<h1>Cloned website not found</h1>", status_code=404)
    
    return HTMLResponse(content=cloned_sites[job_id])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
