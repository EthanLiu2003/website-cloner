import asyncio
import json
import base64
from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, StreamingResponse
from ..schemas.clone import CloneRequest
from ..schemas.job import JobStatus
from ..services.job_manager import job_manager
from ..services.scraper import scraper_service
from ..services.generator import generator_service
from ..services.crawler import crawler_service

router = APIRouter()


@router.post("/clone")
async def start_clone(request: CloneRequest, background_tasks: BackgroundTasks):
    job = job_manager.create(request.url)
    background_tasks.add_task(
        process_clone_job, job.job_id, request.url, request.crawl, request.max_depth, request.max_pages
    )
    return {"job_id": job.job_id, "status": "started"}


async def process_clone_job(job_id: str, url: str, crawl: bool, max_depth: int, max_pages: int):
    job = job_manager.get(job_id)
    if not job:
        return

    try:
        if crawl:
            # Multi-page mode
            job.update(JobStatus.CRAWLING, 10, "Discovering pages...")
            pages = await crawler_service.crawl(scraper_service, url, max_depth, max_pages)
            job.pages_found = len(pages)

            for i, page_url in enumerate(pages):
                progress = 10 + int((i / len(pages)) * 60)
                job.update(JobStatus.SCRAPING, progress, f"Scraping page {i+1}/{len(pages)}: {page_url}")

                try:
                    scrape_result = await asyncio.wait_for(scraper_service.scrape(page_url), timeout=30.0)

                    job.update(JobStatus.GENERATING, progress + 5, f"Generating clone for page {i+1}/{len(pages)}...")
                    html = await generator_service.generate_clone(scrape_result, page_url)
                    job.html_results[page_url] = html
                    job.pages_cloned += 1

                    if i == 0:
                        job.screenshot_b64 = scrape_result.get('screenshot_b64')
                except Exception as e:
                    job.html_results[page_url] = f"<h1>Failed to clone: {page_url}</h1><p>{str(e)}</p>"

            job.complete()
        else:
            # Single page mode
            job.update(JobStatus.SCRAPING, 20, "Scraping website...")
            scrape_result = await asyncio.wait_for(scraper_service.scrape(url), timeout=60.0)
            job.screenshot_b64 = scrape_result.get('screenshot_b64')

            downloaded_count = len(scrape_result.get('downloaded_images', {}))
            if downloaded_count:
                job.update(JobStatus.SCRAPING, 40, f"Downloaded {downloaded_count} images")

            job.update(JobStatus.GENERATING, 50, "Generating clone with AI...")
            html = await generator_service.generate_clone(scrape_result, url)
            job.html_results[url] = html
            job.pages_cloned = 1
            job.pages_found = 1

            job.complete()
    except asyncio.TimeoutError:
        job.fail("Scraping timed out")
    except Exception as e:
        job.fail(f"Unexpected error: {str(e)}")


@router.get("/status/{job_id}")
async def get_status(job_id: str):
    job = job_manager.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    result = {
        "status": job.status.value,
        "progress": job.progress,
        "message": job.message,
        "pages_found": job.pages_found,
        "pages_cloned": job.pages_cloned,
    }
    if job.error:
        result["error"] = job.error
    if job.status == JobStatus.COMPLETED:
        result["result_url"] = f"/api/preview/{job_id}"
    return result


@router.get("/clone/{job_id}/stream")
async def stream_status(job_id: str):
    job = job_manager.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    async def event_generator():
        while True:
            try:
                event = await asyncio.wait_for(job.event_queue.get(), timeout=30.0)
                yield f"data: {json.dumps(event)}\n\n"
                if event.get("status") in ("completed", "error"):
                    break
            except asyncio.TimeoutError:
                yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/preview/{job_id}", response_class=HTMLResponse)
async def preview(job_id: str):
    job = job_manager.get(job_id)
    if not job or not job.html_results:
        raise HTTPException(status_code=404, detail="Clone not found")

    # Return the first (main) page
    main_html = next(iter(job.html_results.values()))
    return HTMLResponse(content=main_html)


@router.get("/preview/{job_id}/screenshot")
async def get_screenshot(job_id: str):
    job = job_manager.get(job_id)
    if not job or not job.screenshot_b64:
        raise HTTPException(status_code=404, detail="Screenshot not found")

    image_data = base64.b64decode(job.screenshot_b64)
    return StreamingResponse(
        iter([image_data]),
        media_type="image/jpeg"
    )


@router.get("/preview/{job_id}/pages")
async def list_pages(job_id: str):
    job = job_manager.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"pages": list(job.html_results.keys())}
