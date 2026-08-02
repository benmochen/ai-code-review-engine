from fastapi import APIRouter, Depends, HTTPException, Request, Header
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.config import get_settings
from app.core.security import verify_webhook_signature
from app.models.models import Repository, Review, ReviewStatus

from app.core.queue import get_queue
from app.workers.jobs import process_review

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
settings = get_settings()

REVIEWABLE_ACTIONS = {"opened", "synchronize", "reopened"}


@router.post("/github")
async def github_webhook(
    request: Request,
    x_github_event: str = Header(None),
    x_hub_signature_256: str = Header(None),
    db: Session = Depends(get_db),
):
    # 1. raw body for signature (given)
    raw_body = await request.body() # bytes

    # 2. verify signature (given)
    if settings.github_webhook_secret:
        if not verify_webhook_signature(raw_body, x_hub_signature_256, settings.github_webhook_secret):
            raise HTTPException(status_code=401, detail="Invalid webhook signature")

    # 3. parse json (given)
    payload = await request.json() 

    # --- YOUR PART FROM HERE ---
    # 4. if event is "ping", return a pong message
    if x_github_event == "ping":
        return {"message": "pong"}

    # 5. if event is not "pull_request", ignore it
    if x_github_event != "pull_request":
        return {"message": "Ignored event"}

    # 6. get action from payload; if not in REVIEWABLE_ACTIONS, ignore
    action = payload.get("action")
    if action not in REVIEWABLE_ACTIONS:
        return {"message": f"Ignored action: {action}"}


    # 7. extract pr and repo data from payload:
    pr = payload["pull_request"]
    repo_data = payload["repository"]

    # 8. look up the Repository in our db by its github id
    #    (repo_data["id"] is GitHub's id; match it against Repository.github_id)
    #    if not found, return a "not registered" message
    repo = db.query(Repository).filter(Repository.github_id == repo_data["id"]).first()
    if not repo:
        return {"message": "Repository not registered"}
    
    # 9. create a Review row and return it 
    review = Review(
    repository_id=repo.id,
    pr_number=pr["number"],
    pr_title=pr["title"],
    pr_url=pr["html_url"],
    status=ReviewStatus.PENDING,
    )
    db.add(review)
    db.commit()
    db.refresh(review)
    # Enqueue the slow work (fetch diff + analyze) to run off the request path.
    # The webhook returns immediately; a worker picks this up.
    try:
        queue = get_queue()
        job = queue.enqueue(process_review, review.id)
        job_id = job.id
    except Exception:
        # If Redis is down, don't lose the review — leave it PENDING for retry.
        job_id = None

    return {
        "message": "Review created",
        "review_id": review.id,
        "pr_number": review.pr_number,
        "job_id": job_id,
    }