# Minor change for AI MR demo: Added a harmless comment to trigger AI features.

import os
import requests
from dotenv import load_dotenv
import openai

load_dotenv()

GITLAB_TOKEN = os.getenv("GITLAB_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
BASE_URL = "https://gitlab.com/api/v4"

openai.api_key = OPENAI_API_KEY

def assign_reviewers(project_id, mr_id, reviewers):
    url = f"{BASE_URL}/projects/{project_id}/merge_requests/{mr_id}/approvers"
    headers = {"PRIVATE-TOKEN": GITLAB_TOKEN}
    user_ids = [get_user_id(r) for r in reviewers]  # Implement lookup
    requests.put(url, headers=headers, json={"approver_ids": user_ids})

def get_user_id(username):
    # You can improve this using the GitLab users search API
    # Example implementation:
    url = f"{BASE_URL}/users?username={username}"
    headers = {"PRIVATE-TOKEN": GITLAB_TOKEN}
    resp = requests.get(url, headers=headers)
    if resp.status_code == 200 and resp.json():
        return resp.json()[0]["id"]
    return 1  # Dummy ID if not found

def create_feature_branch_and_mr(project_id, source_branch, feature_branch, title, description, reviewers=None):
    headers = {"PRIVATE-TOKEN": GITLAB_TOKEN}

    # 1. Create a new branch from source_branch
    branch_url = f"{BASE_URL}/projects/{project_id}/repository/branches"
    branch_data = {"branch": feature_branch, "ref": source_branch}
    branch_resp = requests.post(branch_url, headers=headers, data=branch_data)
    if branch_resp.status_code != 201:
        # If branch already exists, skip error and continue
        if "Branch already exists" not in branch_resp.text:
            return {"error": f"Branch creation failed: {branch_resp.text}"}
    # else: branch created or already exists, continue to MR creation

    # 2. Create a merge request from feature_branch to source_branch
    mr_url = f"{BASE_URL}/projects/{project_id}/merge_requests"
    mr_data = {
        "source_branch": feature_branch,
        "target_branch": source_branch,
        "title": title,
        "description": description
    }
    mr_resp = requests.post(mr_url, headers=headers, data=mr_data)
    if mr_resp.status_code != 201:
        return {"error": f"MR creation failed: {mr_resp.text}"}

    mr_info = mr_resp.json()
    mr_iid = mr_info["iid"]

    # 3. Optionally assign reviewers if provided
    if reviewers:
        assign_reviewers(project_id, mr_iid, reviewers)

    # 4. Get the MR diff for AI features
    diff_url = f"{BASE_URL}/projects/{project_id}/merge_requests/{mr_iid}/changes"
    diff_resp = requests.get(diff_url, headers=headers)
    diff_text = ""
    if diff_resp.status_code == 200:
        changes = diff_resp.json().get("changes", [])
        diff_text = "\n".join([f['diff'] for f in changes if 'diff' in f])

    # 5. Always run AI features, even if there is no diff
    # AI Code Review
    feedback = ai_code_review(diff_text)
    post_mr_comment(project_id, mr_iid, f"**AI Code Review:**\n{feedback}")

    # AI Label Suggestion
    labels = ai_suggest_labels(diff_text)
    if labels:
        assign_labels(project_id, mr_iid, labels)
        post_mr_comment(project_id, mr_iid, f"**AI Suggested Labels:** {', '.join(labels)}")

    # AI Risk Analysis
    risks = ai_risk_analysis(diff_text)
    post_mr_comment(project_id, mr_iid, f"**AI Risk Analysis:**\n{risks}")

    # AI Test Generation
    tests = ai_generate_tests(diff_text)
    post_mr_comment(project_id, mr_iid, f"**AI Suggested Unit Tests:**\n{tests}")

    return mr_info

def ai_code_review(diff_text):
    if not diff_text:
        return "No code changes detected in this merge request."
    prompt = f"Review this code diff and point out any issues or improvements:\n{diff_text}\nFeedback:"
    response = openai.Completion.create(
        engine="text-davinci-003",
        prompt=prompt,
        max_tokens=150,
        temperature=0.5,
    )
    return response.choices[0].text.strip()

def ai_suggest_labels(diff_text):
    if not diff_text:
        return ["no-changes"]
    prompt = f"Suggest up to three labels (bug, feature, docs, refactor, test) for this diff:\n{diff_text}\nLabels:"
    response = openai.Completion.create(
        engine="text-davinci-003",
        prompt=prompt,
        max_tokens=20,
        temperature=0.3,
    )
    return [l.strip() for l in response.choices[0].text.split(",") if l.strip()]

def ai_risk_analysis(diff_text):
    if not diff_text:
        return "No risks detected because there are no code changes."
    prompt = f"Analyze this code diff and describe any potential risks or high-impact areas:\n{diff_text}\nRisks:"
    response = openai.Completion.create(
        engine="text-davinci-003",
        prompt=prompt,
        max_tokens=100,
        temperature=0.5,
    )
    return response.choices[0].text.strip()

def ai_generate_tests(diff_text):
    if not diff_text:
        return "No unit tests suggested because there are no code changes."
    prompt = f"Write unit tests for the following code diff:\n{diff_text}\nUnit Tests:"
    response = openai.Completion.create(
        engine="text-davinci-003",
        prompt=prompt,
        max_tokens=150,
        temperature=0.5,
    )
    return response.choices[0].text.strip()

def post_mr_comment(project_id, mr_iid, comment):
    url = f"{BASE_URL}/projects/{project_id}/merge_requests/{mr_iid}/notes"
    headers = {"PRIVATE-TOKEN": GITLAB_TOKEN}
    data = {"body": comment}
    resp = requests.post(url, headers=headers, json=data)
    print("MR comment response:", resp.status_code, resp.text)

def assign_labels(project_id, mr_iid, labels):
    url = f"{BASE_URL}/projects/{project_id}/merge_requests/{mr_iid}"
    headers = {"PRIVATE-TOKEN": GITLAB_TOKEN}
    data = {"labels": ",".join(labels)}
    requests.put(url, headers=headers, data=data)

def ai_demo_dummy():
    """
    This is a harmless dummy function to guarantee a real code diff for AI testing.
    """
    return "AI demo"

def ai_demo_note2():
    """
    This function is for testing AI-powered code review and labeling.
    """
    print("Hello, AI-powered GitLab automation again!")

def ai_demo_note3():
    """
    This function is for testing AI-powered code review and labeling (demo 3).
    It does not affect the main application.
    """
    print("Hello from ai_demo_note3! This is another test for AI-powered MR automation.")

