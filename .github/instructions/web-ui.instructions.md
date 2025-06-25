---
applyTo: '**/ui/web/**'
---

# Web UI Development Instructions

## Development Workflow

The Jayrah web UI is built with FastAPI backend and vanilla HTML/CSS/JavaScript frontend.

### Running the Web Server

Use the Makefile command for development:
```bash
make web
```

This starts the web server with:
- **Auto-reload enabled**: Changes to files automatically restart the server
- **Reload directory**: Watches `./jayrah/ui/web` for changes
- **Hot reload**: No need to manually kill/restart the server during development

### File Structure

- `jayrah/ui/web/server.py` - FastAPI backend server
- `jayrah/ui/web/index.html` - Frontend HTML/CSS/JavaScript (single page app)

### Key Features Implemented

- **Full screen layout**: Uses entire viewport with responsive design
- **Horizontal scrolling**: Issue list table scrolls horizontally by default
- **Custom fields support**: Displays Jira custom fields same as TUI
- **Markdown rendering**: Converts Jira markup to HTML using marked.js
- **Real-time search**: Debounced search with backend filtering
- **Professional UI**: Inbox-style layout matching TUI workflow

### Development Notes

- **No manual restarts needed**: Thanks to `--reload`, just save files and refresh browser
- **Shared logic**: Common functions moved to `jayrah/ui/shared_helpers.py` to avoid circular imports
- **Config compatibility**: Uses same `~/.config/jayrah/config.yaml` as TUI
- **API endpoints**: 
  - `/api/issues` - List issues with optional search
  - `/api/issue/{key}` - Get issue details with custom fields config
  - `/api/config` - Get configuration including custom fields
- Always use make web which does auto reload and hot reload

### Testing Changes

1. Make changes to `server.py` or `index.html`
2. Save the file (uvicorn will auto-reload)
3. Refresh browser at http://127.0.0.1:8000
4. No need to kill/restart the server process

### External Dependencies

- **marked.js**: Loaded from CDN for Jira markdown → HTML conversion
- **FastAPI**: Backend framework
- **Uvicorn**: ASGI server with hot reload capability
