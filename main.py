from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import httpx
import os
from openai import OpenAI
from fastapi.middleware.cors import CORSMiddleware

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
HEADERS = {"PRIVATE-TOKEN": GITLAB_TOKEN}

client = OpenAI()

class MRRequest(BaseModel):
    project_id: int
    source_branch: str
    target_branch: str
    new_branch_name: str
    mr_title: str
    mr_description: str = ""

async def create_branch_if_not_exists(project_id, branch_name, ref_branch):
    async with httpx.AsyncClient() as client_http:
        # Check branch existence
        resp = await client_http.get(
            f"https://gitlab.com/api/v4/projects/{project_id}/repository/branches/{branch_name}",
            headers=HEADERS,
        )
        if resp.status_code == 404:
            # Branch does not exist, create it
            create_resp = await client_http.post(
                f"https://gitlab.com/api/v4/projects/{project_id}/repository/branches",
                headers=HEADERS,
                json={"branch": branch_name, "ref": ref_branch},
            )
            if create_resp.status_code not in (200, 201):
                raise Exception(f"Branch creation failed: {create_resp.text}")
        elif resp.status_code != 200:
            raise Exception(f"Error checking branch: {resp.text}")

async def create_merge_request(project_id, source_branch, target_branch, title, description):
    async with httpx.AsyncClient() as client_http:
        mr_resp = await client_http.post(
            f"https://gitlab.com/api/v4/projects/{project_id}/merge_requests",
            headers=HEADERS,
            json={
                "source_branch": source_branch,
                "target_branch": target_branch,
                "title": title,
                "description": description,
            },
        )
        if mr_resp.status_code not in (200, 201):
            raise Exception(f"MR creation failed: {mr_resp.text}")
        return mr_resp.json()

async def get_mr_changes(project_id, mr_iid):
    async with httpx.AsyncClient() as client_http:
        diff_resp = await client_http.get(
            f"https://gitlab.com/api/v4/projects/{project_id}/merge_requests/{mr_iid}/changes",
            headers=HEADERS,
        )
        if diff_resp.status_code != 200:
            raise Exception(f"Failed to fetch MR changes: {diff_resp.text}")
        return diff_resp.json().get("changes", [])

async def post_mr_comment(project_id, mr_iid, comment):
    async with httpx.AsyncClient() as client_http:
        comment_resp = await client_http.post(
            f"https://gitlab.com/api/v4/projects/{project_id}/merge_requests/{mr_iid}/notes",
            headers=HEADERS,
            json={"body": comment},
        )
        if comment_resp.status_code not in (200, 201):
            raise Exception(f"Failed to post comment: {comment_resp.text}")
        return comment_resp.json()

async def generate_code_review(diff_text: str) -> str:
    if not diff_text.strip():
        return "No code changes to review."

    system_prompt = "You are a senior software engineer performing a code review. Provide detailed, constructive feedback."
    prompt = f"Review the following git diff:\n{diff_text}\nProvide suggestions, point out bugs, and best practices."

    try:
        response = await client.chat.completions.acreate(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            max_tokens=500,
            temperature=0.3,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Error generating review: {str(e)}"

@app.post("/create-branch-mr/")
async def create_branch_and_mr(data: MRRequest):
    try:
        # Step 1: Create branch if it doesn't exist
        await create_branch_if_not_exists(data.project_id, data.new_branch_name, data.source_branch)

        # Step 2: Create MR from new branch to target branch
        mr = await create_merge_request(
            data.project_id,
            data.new_branch_name,
            data.target_branch,
            data.mr_title,
            data.mr_description,
        )

        mr_iid = mr["iid"]

        # Step 3: Fetch changes (diff) from MR
        changes = await get_mr_changes(data.project_id, mr_iid)
        if not changes:
            return {"message": "No changes detected in MR."}

        # Step 4: Generate review comments for each file diff
        reviews = []
        for change in changes:
            diff_text = change.get("diff", "")
            file_path = change.get("new_path") or change.get("old_path")
            if diff_text.strip():
                review = await generate_code_review(diff_text)
                reviews.append(f"### Review for `{file_path}`\n{review}")

        review_comment = "### 🤖 AI Code Review\n\n" + "\n\n".join(reviews)

        # Step 5: Post the review comment on the MR
        await post_mr_comment(data.project_id, mr_iid, review_comment)

        return {
            "message": "Merge Request created and AI review posted successfully.",
            "merge_request_url": mr["web_url"],
            "ai_review": review_comment,
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
