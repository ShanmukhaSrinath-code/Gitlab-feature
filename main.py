from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from gitlab_api import create_feature_branch_and_mr, get_mr_diff, post_gitlab_mr_comment
from openai_review import generate_code_review

app = FastAPI()

class MergeRequestInput(BaseModel):
    project_id: int
    source_branch: str
    target_branch: str
    new_branch_name: str
    mr_title: str
    mr_description: str = ""

@app.post("/create-branch-mr/")
async def create_branch_and_mr(input_data: MergeRequestInput):
    try:
        # Step 1: Create branch and merge request
        mr_response = await create_feature_branch_and_mr(
            input_data.project_id,
            input_data.source_branch,
            input_data.target_branch,
            input_data.new_branch_name,
            input_data.mr_title,
            input_data.mr_description
        )
        mr_iid = mr_response["iid"]

        # Step 2: Get diff from the merge request
        diff = await get_mr_diff(input_data.project_id, mr_iid)

        # Step 3: Send diff to OpenAI for code review
        review_comment = await generate_code_review(diff)

        # Step 4: Post review comment back to GitLab
        await post_gitlab_mr_comment(input_data.project_id, mr_iid, review_comment)

        return {"message": "Merge Request created and reviewed", "merge_request": mr_response}

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
