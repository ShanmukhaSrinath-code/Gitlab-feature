from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import os
import httpx
from dotenv import load_dotenv
import openai

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

GITLAB_TOKEN = os.getenv("GITLAB_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not GITLAB_TOKEN:
    raise Exception("GITLAB_TOKEN environment variable not set!")
if not OPENAI_API_KEY:
    raise Exception("OPENAI_API_KEY environment variable not set!")

HEADERS = {"PRIVATE-TOKEN": GITLAB_TOKEN}
openai.api_key = OPENAI_API_KEY

class MergeRequestInput(BaseModel):
    project_id: int
    source_branch: str
    target_branch: str
    new_branch_name: str
    mr_title: str
    mr_description: str = ""

async def create_feature_branch_and_mr(project_id, source_branch, target_branch, new_branch_name, mr_title, mr_description=""):
    async with httpx.AsyncClient() as client:
        # Create branch
        branch_resp = await client.post(
            f"https://gitlab.com/api/v4/projects/{project_id}/repository/branches",
            headers=HEADERS,
            json={"branch": new_branch_name, "ref": source_branch}
        )
        if branch_resp.status_code not in [200, 201]:
            raise Exception(f"Branch creation failed: {branch_resp.status_code} {branch_resp.text}")

        # Commit dummy change to new branch so MR has changes
        commit_resp = await client.post(
            f"https://gitlab.com/api/v4/projects/{project_id}/repository/commits",
            headers=HEADERS,
            json={
                "branch": new_branch_name,
                "commit_message": "Add dummy file for AI review",
                "actions": [
                    {
                        "action": "create",
                        "file_path": "dummy_file_for_ai_review.txt",
                        "content": "This is a dummy file to trigger AI code review."
                    }
                ]
            }
        )
        if commit_resp.status_code not in [200, 201]:
            raise Exception(f"Commit failed: {commit_resp.status_code} {commit_resp.text}")

        # Create Merge Request
        mr_resp = await client.post(
            f"https://gitlab.com/api/v4/projects/{project_id}/merge_requests",
            headers=HEADERS,
            json={
                "source_branch": new_branch_name,
                "target_branch": target_branch,
                "title": mr_title,
                "description": mr_description,
            }
        )
        if mr_resp.status_code not in [200, 201]:
            raise Exception(f"Merge request creation failed: {mr_resp.status_code} {mr_resp.text}")

        return mr_resp.json()

async def get_mr_diff(project_id, mr_iid):
    async with httpx.AsyncClient() as client:
        diff_resp = await client.get(
            f"https://gitlab.com/api/v4/projects/{project_id}/merge_requests/{mr_iid}/changes",
            headers=HEADERS
        )
        if diff_resp.status_code != 200:
            raise Exception(f"Failed to fetch MR diff: {diff_resp.status_code} {diff_resp.text}")

        changes = diff_resp.json().get("changes", [])
        diffs = [change.get("diff", "") for change in changes]
        return "\n".join(diffs)

async def post_gitlab_mr_comment(project_id, mr_iid, comment):
    async with httpx.AsyncClient() as client:
        comment_resp = await client.post(
            f"https://gitlab.com/api/v4/projects/{project_id}/merge_requests/{mr_iid}/notes",
            headers=HEADERS,
            json={"body": comment}
        )
        if comment_resp.status_code not in [200, 201]:
            raise Exception(f"Failed to post MR comment: {comment_resp.status_code} {comment_resp.text}")
        return comment_resp.json()

async def generate_code_review(diff: str) -> str:
    if not diff.strip():
        return "No changes detected in the merge request to review."
    prompt = f"Please provide a detailed code review for the following git diff:\n{diff}\n\n" \
             "Highlight issues, suggest improvements, and give best practices."
    try:
        response = await openai.ChatCompletion.acreate(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500,
            temperature=0.3,
        )
        review_text = response.choices[0].message.content.strip()
        return review_text
    except Exception as e:
        return f"Failed to generate code review: {str(e)}"

@app.post("/create-branch-mr/")
async def create_branch_and_mr(input_data: MergeRequestInput):
    try:
        # Step 1: Create branch, commit dummy change, and MR
        mr_response = await create_feature_branch_and_mr(
            input_data.project_id,
            input_data.source_branch,
            input_data.target_branch,
            input_data.new_branch_name,
            input_data.mr_title,
            input_data.mr_description,
        )
        mr_iid = mr_response["iid"]

        # Step 2: Get MR diff
        diff = await get_mr_diff(input_data.project_id, mr_iid)

        # Step 3: Generate AI review
        review_comment = await generate_code_review(diff)

        # Step 4: Post AI review comment on GitLab MR
        await post_gitlab_mr_comment(input_data.project_id, mr_iid, review_comment)

        # Return MR info + review text
        return {
            "message": "Merge Request created and reviewed",
            "merge_request": mr_response,
            "ai_code_review": review_comment
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/ping")
def ping():
    return {"status": "ok"}
