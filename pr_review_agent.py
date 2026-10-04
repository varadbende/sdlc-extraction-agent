"""
REQ-6: PR review agent. Reads the open PR's diff, asks the Foundry model to
give a first-pass review against this project's own conventions, and posts
the result as a PR COMMENT -- never a review approval.

The boundary ("proposes but can never approve") is enforced two ways:
  1. This script only ever calls GitHub's "create an issue comment" endpoint.
     It never calls the "submit a pull request review" endpoint (the one
     capable of an APPROVE event) -- that code path simply does not exist
     here.
  2. Even if it did: GitHub blocks the workflow's own GITHUB_TOKEN from
     submitting an approving PR review at the platform level, specifically
     to prevent a workflow from approving its own pull request. So the
     boundary holds even if this script were changed by mistake.
"""
import json
import os
import sys

import requests
from openai import AzureOpenAI

MAX_DIFF_CHARS = 12000  # keep the prompt small and cheap; truncate a huge diff rather than skip the review


def get_pr_context() -> dict:
    with open(os.environ["GITHUB_EVENT_PATH"]) as f:
        event = json.load(f)
    pr = event["pull_request"]
    return {
        "number": pr["number"],
        "title": pr["title"],
        "repo": os.environ["GITHUB_REPOSITORY"],
    }


def review_diff(diff_text: str) -> str:
    client = AzureOpenAI(
        azure_endpoint=os.environ["AZURE_FOUNDRY_ENDPOINT"],
        api_key=os.environ["AZURE_FOUNDRY_API_KEY"],
        api_version="2024-12-01-preview",
    )
    deployment = os.environ["AZURE_FOUNDRY_DEPLOYMENT_NAME"]

    prompt = f"""You are a first-pass reviewer for a pull request on a governed data-extraction
agent project. Project conventions: a closed-vocabulary attribute dictionary (no inventing new
keys), deterministic checks preferred over LLM calls wherever possible (ADR-0003), no secrets or
API keys ever committed, and every change should be explainable by a non-engineer product manager.
You cannot approve or merge this PR -- your only job is a short, specific first-pass comment a
human reviewer can use as a starting point. If the diff looks fine, say so briefly; do not invent
issues to sound thorough.

Diff:
{diff_text}

Write a concise review comment, plain text, under 200 words."""

    response = client.chat.completions.create(
        model=deployment,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        max_tokens=400,
    )
    return response.choices[0].message.content


def post_comment(repo: str, pr_number: int, body: str) -> None:
    token = os.environ["GITHUB_TOKEN"]
    url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }
    full_body = (
        "**Automated first-pass review (REQ-6)**\n\n"
        f"{body}\n\n"
        "---\n"
        "*This is an automated comment, not an approval. This bot cannot approve or merge "
        "pull requests -- a human reviewer must supply the approval required by branch protection.*"
    )
    resp = requests.post(url, headers=headers, json={"body": full_body}, timeout=30)
    resp.raise_for_status()
    print(f"Posted review comment on PR #{pr_number}")


if __name__ == "__main__":
    with open("pr.diff") as f:
        diff_text = f.read()

    if not diff_text.strip():
        print("Empty diff -- nothing to review.")
        sys.exit(0)

    if len(diff_text) > MAX_DIFF_CHARS:
        diff_text = diff_text[:MAX_DIFF_CHARS] + "\n\n[... diff truncated for length ...]"

    context = get_pr_context()
    review_text = review_diff(diff_text)
    post_comment(context["repo"], context["number"], review_text)
