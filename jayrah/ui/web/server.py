import os
import pathlib
from typing import Optional

import click
import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

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

# Mount static files directory for serving images and other assets
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Also mount images directory if it exists
images_dir = os.path.join(os.path.dirname(__file__), "images")
if os.path.exists(images_dir):
    app.mount("/images", StaticFiles(directory=images_dir), name="images")


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


def get_app_state() -> WebAppState:
    """Dependency function to get the application state"""
    # Use FastAPI's app.state to store application state
    if not hasattr(app.state, "jayrah_state"):
        initialize_app_state()
    return app.state.jayrah_state


def initialize_app_state(user_config=None):
    """Initialize the application state"""
    app.state.jayrah_state = WebAppState(user_config)


@app.get("/api/issues")
def get_issues(
    q: Optional[str] = Query(None), state: WebAppState = Depends(get_app_state)
):
    if not state.issues:
        raise HTTPException(
            status_code=503, detail="No issues available - check Jira configuration"
        )
    issues = state.issues
    if q:
        issues = filter_issues_by_text(issues, q)
    return [get_row_data_for_issue(issue) for issue in issues]


@app.get("/api/issue/{key}")
def get_issue_detail(key: str, state: WebAppState = Depends(get_app_state)):
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
def get_config(state: WebAppState = Depends(get_app_state)):
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


@app.get("/api/boards")
def get_boards(state: WebAppState = Depends(get_app_state)):
    """Get list of available boards from configuration"""
    try:
        boards = state.config.get("boards", [])
        # Extract board names and descriptions
        board_list = []
        for board in boards:
            if isinstance(board, dict) and "name" in board:
                board_list.append(
                    {
                        "name": board["name"],
                        "description": board.get("description", board["name"]),
                        "jql": board.get("jql", ""),
                    }
                )
        return {"boards": board_list}
    except Exception as e:
        print(f"Error getting boards: {e}")
        return {"boards": []}


@app.post("/api/boards/{board_name}/switch")
def switch_board(board_name: str, state: WebAppState = Depends(get_app_state)):
    """Switch to a different board and reload issues"""
    try:
        # Import here to avoid circular imports
        from jayrah.ui import boards

        # Get the new board's JQL and order_by
        jql, order_by = boards.check(board_name, state.config)
        if not jql:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid board or missing JQL: {board_name}",
            )

        # Search for issues with the new board's JQL
        result = state.jayrah_obj.jira.search_issues(jql=jql, max_results=100)
        new_issues = result.get("issues", []) if result else []

        # Update the state with new issues
        state.issues = new_issues

        print(
            f"Switched to board '{board_name}' with {len(new_issues)} issues using JQL: {jql}"
        )

        return {
            "success": True,
            "board_name": board_name,
            "issue_count": len(new_issues),
            "jql": jql,
        }
    except Exception as e:
        print(f"Error switching board: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error switching board: {str(e)}"
        ) from e


@app.post("/api/refresh")
def refresh_issues(state: WebAppState = Depends(get_app_state)):
    """Refresh issues by clearing cache and reloading from Jira"""
    try:
        # Clear the Jira cache
        state.jayrah_obj.jira.cache.clear()

        # Use the default board's JQL if available, otherwise get recent issues
        if state.config.get("boards") and len(state.config["boards"]) > 0:
            jql = state.config["boards"][0].get(
                "jql", "updated >= -30d ORDER BY updated DESC"
            )
        else:
            jql = "updated >= -30d ORDER BY updated DESC"  # Default: issues updated in last 30 days

        # Fetch fresh issues from Jira (use_cache=False to bypass cache)
        result = state.jayrah_obj.jira.search_issues(jql=jql, max_results=100)
        new_issues = result.get("issues", []) if result else []

        # Update the state with new issues
        state.issues = new_issues

        print(f"Refreshed {len(new_issues)} issues from Jira using JQL: {jql}")

        return {
            "success": True,
            "issue_count": len(new_issues),
            "jql": jql,
        }
    except Exception as e:
        print(f"Error refreshing issues: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error refreshing issues: {str(e)}"
        ) from e


@click.command()
@click.option("--host", default="127.0.0.1", help="Host address to bind.")
@click.option("--port", default=8000, type=int, help="Port to bind.")
@click.option("--reload", is_flag=True, default=False, help="Enable auto-reload.")
@click.option("--workers", default=1, type=int, help="Number of worker processes.")
@click.option("--log-level", default="info", help="Logging level.")
@click.option(
    "--reloads-dirs",
    default=None,
    type=str,
    help="Comma-separated list of directories to watch for reloads.",
)
def cli(host, port, reload, workers, log_level, reloads_dirs=None):
    initialize_app_state()
    if reloads_dirs:
        reloads_dirs = reloads_dirs.split(",")
        reload = True
    try:
        uvicorn.run(
            "jayrah.ui.web.server:app",
            host=host,
            port=port,
            reload=reload,
            workers=workers,
            log_level=log_level,
            reload_dirs=reloads_dirs,
        )
    except KeyboardInterrupt:
        print("Server stopped by user.")


def main():
    cli.main(auto_envvar_prefix="JAYRAH_WEB", obj=None)
