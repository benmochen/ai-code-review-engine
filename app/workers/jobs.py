"""
The review-processing job.

This is the function the worker runs for each queued job. It is a plain
module-level function (not a method) because rq serializes the reference
by import path — the worker process must be able to import it.

The job manages its OWN database session — it runs in a separate process
and cannot reuse the web request's session.
"""
import asyncio
from datetime import datetime, timezone

from app.core.database import SessionLocal
from app.core.github_client import GitHubClient
from app.models.models import Review, Repository, User, ReviewStatus


def process_review(review_id: str) -> dict:
    """Entry point invoked by the rq worker for each job."""
    db = SessionLocal()
    try:
        review = db.query(Review).filter(Review.id == review_id).first()
        if not review:
            return {"status": "error", "reason": f"Review {review_id} not found"}

        # Claim the review up front so its status is visible while the job runs
        review.status = ReviewStatus.IN_PROGRESS
        db.commit()

        # Resolve repo + owner token
        repo = db.query(Repository).filter(Repository.id == review.repository_id).first()
        owner = db.query(User).filter(User.id == repo.owner_id).first() if repo else None
        token = owner.access_token if owner else None

        # Fetch the diff from GitHub
        try:
            gh = GitHubClient(access_token=token)
            # get_pr_diff is async but rq runs jobs synchronously
            diff = asyncio.run(gh.get_pr_diff(repo.full_name, review.pr_number))
            review.diff_text = diff
        except Exception as e:
            # Commit the failure so the review isn't left stuck in progress
            review.status = ReviewStatus.FAILED
            db.commit()
            return {"status": "failed", "reason": f"diff fetch failed: {e}"}

        # TODO Week 4: run Claude analysis on `diff`, create ReviewComment rows,
        #              and post comments back to the PR via the GitHub API.

        review.status = ReviewStatus.COMPLETED
        review.completed_at = datetime.now(timezone.utc)
        db.commit()

        return {
            "status": "completed",
            "review_id": review_id,
            "diff_bytes": len(review.diff_text or ""),
        }
    finally:
        # finally, so the session closes on every path including the early returns
        db.close()