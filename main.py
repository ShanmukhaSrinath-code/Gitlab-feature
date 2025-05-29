from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import os
import httpx
from dotenv import load_dotenv
from openai_review import generate_code_review  # use updated async function

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
if not GITLAB_TOKEN:
    raise Exception("GITLAB_TOKEN environment variable not set!")

HEADERS = {"PRIVATE-TOKEN": GITLAB_TOKEN}

class MergeRequestInput(BaseModel):
    project_id: int
    source_branch: str
    target_branch: str
    new_branch_name: str
    mr_title: str
    mr_description: str = ""

async def create_feature_branch_and_mr(project_id, source_branch, target_branch, new_branch_name, mr_title, mr_description=""):
    async with httpx.AsyncClient() as client:
        branch_resp = await client.post(
            f"https://gitlab.com/api/v4/projects/{project_id}/repository/branches",
            headers=HEADERS,
            json={"branch": new_branch_name, "ref": source_branch}
        )
        if branch_resp.status_code not in [200, 201]:
            raise Exception(f"Branch creation failed: {branch_resp.status_code} {branch_resp.text}")

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

@app.post("/create-branch-mr/")
async def create_branch_and_mr(input_data: MergeRequestInput):
    try:
        mr_response = await create_feature_branch_and_mr(
            input_data.project_id,
            input_data.source_branch,
            input_data.target_branch,
            input_data.new_branch_name,
            input_data.mr_title,
            input_data.mr_description,
        )
        mr_iid = mr_response["iid"]
        diff = await get_mr_diff(input_data.project_id, mr_iid)
        review_comment = await generate_code_review(diff)
        await post_gitlab_mr_comment(input_data.project_id, mr_iid, review_comment)

        return {"message": "Merge Request created and reviewed", "merge_request": mr_response}

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
