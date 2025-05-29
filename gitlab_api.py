import os
import httpx
from dotenv import load_dotenv
import os
load_dotenv()  

GITLAB_TOKEN = os.getenv("GITLAB_TOKEN")
GITLAB_API_URL = os.getenv("GITLAB_API_URL", "https://gitlab.com/api/v4")
headers_gitlab = {"PRIVATE-TOKEN": GITLAB_TOKEN}
print(f"GITLAB_TOKEN: {GITLAB_TOKEN}")


async def create_branch(project_id: int, source_branch: str, new_branch_name: str):
    url = f"{GITLAB_API_URL}/projects/{project_id}/repository/branches"
    payload = {"branch": new_branch_name, "ref": source_branch}
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, headers=headers_gitlab, json=payload)
        resp.raise_for_status()
        return resp.json()


async def create_merge_request(project_id: int, source_branch: str, target_branch: str, title: str, description: str):
    url = f"{GITLAB_API_URL}/projects/{project_id}/merge_requests"
    payload = {
        "source_branch": source_branch,
        "target_branch": target_branch,
        "title": title,
        "description": description
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, headers=headers_gitlab, json=payload)
        resp.raise_for_status()
        return resp.json()


async def get_mr_diff(project_id: int, mr_iid: int):
    url = f"{GITLAB_API_URL}/projects/{project_id}/merge_requests/{mr_iid}/changes"
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=headers_gitlab)
        resp.raise_for_status()
        return resp.json()


async def post_gitlab_mr_comment(project_id: int, mr_iid: int, comment: str):
    url = f"{GITLAB_API_URL}/projects/{project_id}/merge_requests/{mr_iid}/notes"
    payload = {"body": comment}
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, headers=headers_gitlab, json=payload)
        resp.raise_for_status()
        return resp.json()



async def create_feature_branch_and_mr(project_id: int, source_branch: str, feature_branch: str, title: str, description: str):
    # Create the feature branch
    branch = await create_branch(project_id, source_branch, feature_branch)
    
    # Create the merge request from feature_branch to source_branch
    mr = await create_merge_request(project_id, feature_branch, source_branch, title, description)
    
    return mr
