import os
import pathlib
from typing import Optional

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


@app.get("/api/labels")
def get_all_labels(state: WebAppState = Depends(get_app_state)):
    """Get all available labels for completion"""
    try:
        # Get all labels from Jira
        all_labels = state.jayrah_obj.jira.get_labels()

        # Apply label excludes filter if configured
        if label_excludes := state.config.get("label_excludes"):
            import re

            labels_excludes_re = re.compile(label_excludes.strip())
            all_labels = [
                label
                for label in all_labels
                if label and not labels_excludes_re.match(label)
            ]

        return {"labels": all_labels}
    except Exception as e:
        print(f"Error getting labels: {e}")
        return {"labels": []}


@app.put("/api/issue/{key}/labels")
def update_issue_labels(
    key: str, labels_data: dict, state: WebAppState = Depends(get_app_state)
):
    """Update issue labels"""
    try:
        new_labels = labels_data.get("labels", [])

        # Update the issue with new labels
        state.jayrah_obj.jira.update_issue(key, {"labels": new_labels})

        # Update the local cache with new label data
        for issue in state.issues:
            if issue["key"] == key:
                issue["fields"]["labels"] = new_labels
                break

        return {
            "success": True,
            "message": f"Labels updated for {key}",
            "labels": new_labels,
        }
    except Exception as e:
        print(f"Error updating labels: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error updating labels: {str(e)}"
        ) from e


@app.get("/api/issue/{key}/transitions")
def get_issue_transitions(key: str, state: WebAppState = Depends(get_app_state)):
    """Get available transitions for an issue"""
    try:
        transitions_data = state.jayrah_obj.jira.get_transitions(key)
        return transitions_data
    except Exception as e:
        print(f"Error getting transitions for {key}: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error getting transitions: {str(e)}"
        ) from e


@app.post("/api/issue/{key}/transitions")
def apply_issue_transition(
    key: str, transition_data: dict, state: WebAppState = Depends(get_app_state)
):
    """Apply a transition to an issue"""
    try:
        transition_id = transition_data.get("transition_id")
        if not transition_id:
            raise HTTPException(status_code=400, detail="transition_id is required")

        # Apply the transition
        result = state.jayrah_obj.jira.transition_issue(key, transition_id)

        # Update the local cache - refresh the specific issue
        try:
            # Fetch fresh issue data to get updated status
            updated_issue_data = state.jayrah_obj.jira.get_issue(key)
            # Update in local cache
            for i, issue in enumerate(state.issues):
                if issue["key"] == key:
                    state.issues[i] = updated_issue_data
                    break
        except Exception as cache_error:
            print(f"Warning: Could not update local cache: {cache_error}")

        return {
            "success": True,
            "message": f"Transition applied to {key}",
            "result": result,
        }
    except Exception as e:
        print(f"Error applying transition to {key}: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error applying transition: {str(e)}"
        ) from e


@app.get("/api/stats")
def get_stats(state: WebAppState = Depends(get_app_state)):
    """Get detailed statistics about the current board's issues"""
    if not state.issues:
        return {
            "total_issues": 0,
            "issue_types": {},
            "statuses": {},
            "assignees": {},
            "priorities": {},
            "components": {},
            "labels": {},
            "created_this_week": 0,
            "updated_this_week": 0,
            "resolution_stats": {},
            "trend_created": [],
            "trend_closed": [],
            "overdue_issues_count": 0,
            "overdue_issues": [],
            "stuck_issues_count": 0,
            "stuck_issues": [],
            "high_priority_issues_count": 0,
            "high_priority_issues": [],
            "blocked_issues_count": 0,
            "blocked_issues": [],
            "top_labels": [],
            "top_components": [],
        }

    from collections import Counter, defaultdict
    from datetime import datetime, timedelta

    # Initialize counters
    issue_types = defaultdict(int)
    statuses = defaultdict(int)

    assignees = defaultdict(int)
    priorities = defaultdict(int)
    components = defaultdict(int)
    labels = defaultdict(int)
    resolutions = defaultdict(int)

    # Date calculations for recent activity
    week_ago = datetime.now() - timedelta(days=7)
    created_this_week = 0
    updated_this_week = 0

    # For trends
    weeks_back = 4
    now = datetime.now()
    week_bins = [
        (now - timedelta(days=7 * i)).isocalendar()[:2]
        for i in range(weeks_back, 0, -1)
    ]
    trend_created = [0] * weeks_back
    trend_closed = [0] * weeks_back

    overdue_issues = []
    stuck_issues = []
    high_priority_issues = []
    blocked_issues = []

    for issue in state.issues:
        fields = issue.get("fields", {})
        # Issue types
        issue_type = fields.get("issuetype", {}).get("name", "Unknown")
        issue_types[issue_type] += 1

        # Statuses
        status = fields.get("status", {}).get("name", "Unknown")
        statuses[status] += 1

        # Assignees
        assignee = fields.get("assignee")
        if assignee:
            assignee_name = assignee.get("displayName", assignee.get("name", "Unknown"))
        else:
            assignee_name = "Unassigned"
        assignees[assignee_name] += 1

        # Priorities
        priority = fields.get("priority")
        if priority:
            priority_name = priority.get("name", "Unknown")
            priorities[priority_name] += 1
        else:
            priority_name = None

        # Components
        components_list = fields.get("components", [])
        if components_list:
            for component in components_list:
                comp_name = component.get("name", "Unknown")
                components[comp_name] += 1
        else:
            components["No Component"] += 1

        # Labels
        labels_list = fields.get("labels", [])
        if labels_list:
            for label in labels_list:
                labels[label] += 1
        else:
            labels["No Labels"] += 1

        # Resolution
        resolution = fields.get("resolution")
        if resolution:
            resolution_name = resolution.get("name", "Unresolved")
        else:
            resolution_name = "Unresolved"
        resolutions[resolution_name] += 1

        # Recent activity
        try:
            created_str = fields.get("created", "")
            if created_str:
                created_date = datetime.fromisoformat(
                    created_str.replace("Z", "+00:00")
                )
                if created_date.replace(tzinfo=None) > week_ago:
                    created_this_week += 1
                # Trend: created
                for i, (y, w) in enumerate(week_bins):
                    if created_date.isocalendar()[:2] == (y, w):
                        trend_created[i] += 1
                        break

            updated_str = fields.get("updated", "")
            if updated_str:
                updated_date = datetime.fromisoformat(
                    updated_str.replace("Z", "+00:00")
                )
                if updated_date.replace(tzinfo=None) > week_ago:
                    updated_this_week += 1

            # Overdue: due date in the past
            due_str = fields.get("duedate")
            if due_str:
                due_date = datetime.fromisoformat(due_str)
                if due_date < now and (
                    not resolution or resolution_name == "Unresolved"
                ):
                    overdue_issues.append(
                        {
                            "key": issue.get("key"),
                            "summary": fields.get("summary", ""),
                        }
                    )

            # Stuck: not updated in >7 days
            if updated_str:
                updated_date = datetime.fromisoformat(
                    updated_str.replace("Z", "+00:00")
                )
                if updated_date.replace(tzinfo=None) < week_ago and (
                    not resolution or resolution_name == "Unresolved"
                ):
                    stuck_issues.append(
                        {
                            "key": issue.get("key"),
                            "summary": fields.get("summary", ""),
                        }
                    )

            # Closed trend: closed in week
            if resolution and "date" in resolution:
                closed_date = datetime.fromisoformat(
                    resolution["date"].replace("Z", "+00:00")
                )
                for i, (y, w) in enumerate(week_bins):
                    if closed_date.isocalendar()[:2] == (y, w):
                        trend_closed[i] += 1
                        break
        except Exception:
            pass  # Skip date parsing errors

        # High priority
        if priority_name and priority_name.lower() in (
            "high",
            "highest",
            "critical",
            "blocker",
        ):
            high_priority_issues.append(
                {
                    "key": issue.get("key"),
                    "summary": fields.get("summary", ""),
                }
            )

        # Blocked: status or label
        if status.lower() == "blocked" or "blocked" in [
            label.lower() for label in labels_list
        ]:
            blocked_issues.append(
                {
                    "key": issue.get("key"),
                    "summary": fields.get("summary", ""),
                }
            )

    # Top labels/components
    top_labels = [
        label for label, _ in Counter(labels).most_common(5) if label != "No Labels"
    ]
    top_components = [
        c for c, _ in Counter(components).most_common(5) if c != "No Component"
    ]

    return {
        "total_issues": len(state.issues),
        "issue_types": dict(
            sorted(issue_types.items(), key=lambda x: x[1], reverse=True)
        ),
        "statuses": dict(sorted(statuses.items(), key=lambda x: x[1], reverse=True)),
        "assignees": dict(sorted(assignees.items(), key=lambda x: x[1], reverse=True)),
        "priorities": dict(
            sorted(priorities.items(), key=lambda x: x[1], reverse=True)
        ),
        "components": dict(
            sorted(components.items(), key=lambda x: x[1], reverse=True)
        ),
        "labels": dict(sorted(labels.items(), key=lambda x: x[1], reverse=True)),
        "created_this_week": created_this_week,
        "updated_this_week": updated_this_week,
        "resolution_stats": dict(
            sorted(resolutions.items(), key=lambda x: x[1], reverse=True)
        ),
        "trend_created": trend_created,
        "trend_closed": trend_closed,
        "overdue_issues_count": len(overdue_issues),
        "overdue_issues": overdue_issues,
        "stuck_issues_count": len(stuck_issues),
        "stuck_issues": stuck_issues,
        "high_priority_issues_count": len(high_priority_issues),
        "high_priority_issues": high_priority_issues,
        "blocked_issues_count": len(blocked_issues),
        "blocked_issues": blocked_issues,
        "top_labels": top_labels,
        "top_components": top_components,
    }


@app.put("/api/issue/{key}/customfield")
def update_issue_custom_field(
    key: str, field_data: dict, state: WebAppState = Depends(get_app_state)
):
    """Update a custom field for an issue"""
    try:
        field_id = field_data.get("field_id")
        value = field_data.get("value")
        field_type = field_data.get("type", "string")

        if not field_id:
            raise HTTPException(status_code=400, detail="field_id is required")

        # Validate and convert value based on field type
        if field_type == "number":
            try:
                if value is None:
                    value = 0
                value_str = str(value)
                value = float(value_str) if "." in value_str else int(value_str)
            except (ValueError, TypeError) as exc:
                raise HTTPException(
                    status_code=400, detail="Invalid number format"
                ) from exc
        elif field_type == "url":
            import re

            if value and not re.match(
                r"^(https?|ftp)://[^\s/$.?#].[^\s]*$", str(value)
            ):
                raise HTTPException(status_code=400, detail="Invalid URL format")
        elif field_type in ["string", "text"]:
            value = str(value) if value is not None else ""

        # Update the issue with the new custom field value
        state.jayrah_obj.jira.update_issue(key, {field_id: value})

        # Update the local cache with new field data
        try:
            updated_issue_data = state.jayrah_obj.jira.get_issue(key)
            for i, issue in enumerate(state.issues):
                if issue["key"] == key:
                    # Update the fields in the cached issue
                    if "fields" not in state.issues[i]:
                        state.issues[i]["fields"] = {}
                    state.issues[i]["fields"][field_id] = value
                    # Also update with fresh data to ensure consistency
                    state.issues[i] = updated_issue_data
                    break
        except Exception as cache_error:
            print(f"Warning: Could not update local cache: {cache_error}")

        return {
            "success": True,
            "message": f"Custom field {field_id} updated for {key}",
            "field_id": field_id,
            "value": value,
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error updating custom field for {key}: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error updating custom field: {str(e)}"
        ) from e
