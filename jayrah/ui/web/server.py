import os
import pathlib
from typing import Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from jayrah import config as jayrah_config
from jayrah.config import defaults
from jayrah.ui.shared_helpers import filter_issues_by_text, get_row_data_for_issue
from jayrah.ui.tui.base import JayrahAppMixin

app = FastAPI()

# Allow CORS for local frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class WebAppState(JayrahAppMixin):
    def __init__(self, user_config=None):
        # Load configuration the same way as CLI
        if user_config is None:
            config_file = pathlib.Path(defaults.CONFIG_FILE)
            flag_config = {}  # No CLI flags for web
            wconfig = jayrah_config.make_config(flag_config, config_file)
        else:
            wconfig = user_config

        JayrahAppMixin.__init__(self, wconfig)
        try:
            # Use the default board's JQL if available, otherwise get recent issues
            if wconfig.get("boards") and len(wconfig["boards"]) > 0:
                jql = wconfig["boards"][0].get(
                    "jql", "updated >= -30d ORDER BY updated DESC"
                )
            else:
                jql = "updated >= -30d ORDER BY updated DESC"  # Default: issues updated in last 30 days

            result = self.jayrah_obj.jira.search_issues(jql=jql, max_results=100)
            self.issues = result.get("issues", []) if result else []
            print(f"Loaded {len(self.issues)} issues from Jira using JQL: {jql}")
        except Exception as e:
            print(f"Error loading issues: {e}")
            self.issues = []


# Initialize with proper config loading
state = WebAppState()


@app.get("/api/issues")
def get_issues(q: Optional[str] = Query(None)):
    if not state.issues:
        raise HTTPException(
            status_code=503, detail="No issues available - check Jira configuration"
        )
    issues = state.issues
    if q:
        issues = filter_issues_by_text(issues, q)
    return [get_row_data_for_issue(issue) for issue in issues]


@app.get("/api/issue/{key}")
def get_issue_detail(key: str):
    if not state.issues:
        raise HTTPException(status_code=503, detail="No issues available")
    for issue in state.issues:
        if issue["key"] == key:
            # Include custom fields config for the frontend
            return {
                "issue": issue,
                "custom_fields": state.config.get("custom_fields", []),
            }
    return {"error": "Not found"}


@app.get("/api/config")
def get_config():
    """Get configuration including custom fields for the frontend"""
    jira_url = None
    try:
        # Get Jira server URL from config
        jira_url = state.config.get("jira_server")
    except Exception:
        pass

    return {
        "custom_fields": state.config.get("custom_fields", []),
        "jira_base_url": jira_url,
    }


@app.get("/")
def serve_index():
    return FileResponse(os.path.join(os.path.dirname(__file__), "index.html"))


def main():
    # Initialize the app state
    uvicorn.run(app, host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
