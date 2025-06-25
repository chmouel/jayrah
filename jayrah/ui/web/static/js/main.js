let allIssues = [];
let selectedRow = null;
let jiraBaseUrl = null;
let availableBoards = [];
let currentBoard = null;

// Layout state management
const LAYOUT_STATES = {
  HORIZONTAL: "layout-horizontal",
  VERTICAL: "layout-vertical",
};

let currentLayoutState = LAYOUT_STATES.HORIZONTAL;

// View state management
const VIEW_STATES = {
  BOTH: "view-both",
  LIST_ONLY: "view-list-only",
  DETAILS_ONLY: "view-details-only",
};

const VIEW_ICONS = {
  [VIEW_STATES.BOTH]: `
                <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
                    <rect x="1" y="2" width="6" height="12" rx="1" stroke="currentColor" stroke-width="1" fill="none"/>
                    <rect x="9" y="4" width="6" height="10" rx="1" stroke="currentColor" stroke-width="1" fill="none"/>
                    <rect x="2" y="3" width="4" height="1" fill="currentColor"/>
                    <rect x="2" y="5" width="4" height="1" fill="currentColor"/>
                    <rect x="2" y="7" width="3" height="1" fill="currentColor"/>
                    <rect x="10" y="5" width="4" height="1" fill="currentColor"/>
                    <rect x="10" y="7" width="4" height="1" fill="currentColor"/>
                    <rect x="10" y="9" width="3" height="1" fill="currentColor"/>
                </svg>
            `,
  [VIEW_STATES.LIST_ONLY]: `
                <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
                    <rect x="2" y="2" width="12" height="12" rx="1" stroke="currentColor" stroke-width="1" fill="none"/>
                    <rect x="3" y="3" width="10" height="1" fill="currentColor"/>
                    <rect x="3" y="5" width="10" height="1" fill="currentColor"/>
                    <rect x="3" y="7" width="8" height="1" fill="currentColor"/>
                    <rect x="3" y="9" width="10" height="1" fill="currentColor"/>
                    <rect x="3" y="11" width="7" height="1" fill="currentColor"/>
                </svg>
            `,
  [VIEW_STATES.DETAILS_ONLY]: `
                <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
                    <rect x="4" y="2" width="8" height="12" rx="1" stroke="currentColor" stroke-width="1" fill="none"/>
                    <rect x="5" y="3" width="6" height="1" fill="currentColor"/>
                    <rect x="5" y="5" width="6" height="1" fill="currentColor"/>
                    <rect x="5" y="7" width="4" height="1" fill="currentColor"/>
                    <rect x="5" y="9" width="6" height="1" fill="currentColor"/>
                    <rect x="5" y="11" width="5" height="1" fill="currentColor"/>
                </svg>
            `,
};

const VIEW_TITLES = {
  [VIEW_STATES.BOTH]:
    "Showing both panels - click or press T to show list only",
  [VIEW_STATES.LIST_ONLY]:
    "Showing list only - click or press T to show details only",
  [VIEW_STATES.DETAILS_ONLY]:
    "Showing details only - click or press T to show both panels",
};

const LAYOUT_ICONS = {
  [LAYOUT_STATES.HORIZONTAL]: `
                <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
                    <rect x="1" y="3" width="6" height="10" rx="1" stroke="currentColor" stroke-width="1" fill="none"/>
                    <rect x="9" y="3" width="6" height="10" rx="1" stroke="currentColor" stroke-width="1" fill="none"/>
                    <rect x="2" y="4" width="4" height="1" fill="currentColor"/>
                    <rect x="2" y="6" width="4" height="1" fill="currentColor"/>
                    <rect x="2" y="8" width="3" height="1" fill="currentColor"/>
                    <rect x="10" y="4" width="4" height="1" fill="currentColor"/>
                    <rect x="10" y="6" width="4" height="1" fill="currentColor"/>
                    <rect x="10" y="8" width="4" height="1" fill="currentColor"/>
                    <rect x="10" y="10" width="3" height="1" fill="currentColor"/>
                </svg>
            `,
  [LAYOUT_STATES.VERTICAL]: `
                <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
                    <rect x="3" y="1" width="10" height="6" rx="1" stroke="currentColor" stroke-width="1" fill="none"/>
                    <rect x="3" y="9" width="10" height="6" rx="1" stroke="currentColor" stroke-width="1" fill="none"/>
                    <rect x="4" y="2" width="8" height="1" fill="currentColor"/>
                    <rect x="4" y="4" width="6" height="1" fill="currentColor"/>
                    <rect x="4" y="10" width="8" height="1" fill="currentColor"/>
                    <rect x="4" y="12" width="6" height="1" fill="currentColor"/>
                    <line x1="4" y1="7.5" x2="12" y2="7.5" stroke="currentColor" stroke-width="1"/>
                </svg>
            `,
};

const LAYOUT_TITLES = {
  [LAYOUT_STATES.HORIZONTAL]:
    "Layout: horizontal (side by side) - click or press V to switch to vertical",
  [LAYOUT_STATES.VERTICAL]:
    "Layout: vertical (top/bottom) - click or press V to switch to horizontal",
};

let currentViewState = VIEW_STATES.BOTH;

// Cookie-based state management
const STATE_COOKIES = {
  LAYOUT: "jayrah_layout_state",
  VIEW: "jayrah_view_state",
  BOARD: "jayrah_current_board",
  SEARCH_VISIBLE: "jayrah_search_visible",
  SEARCH_QUERY: "jayrah_search_query",
};

// Cookie utility functions
function setCookie(name, value, days = 30) {
  const expires = new Date();
  expires.setTime(expires.getTime() + days * 24 * 60 * 60 * 1000);
  document.cookie = `${name}=${encodeURIComponent(value)}; expires=${expires.toUTCString()}; path=/; SameSite=Lax`;
}

function getCookie(name) {
  const nameEQ = name + "=";
  const ca = document.cookie.split(";");
  for (let i = 0; i < ca.length; i++) {
    let c = ca[i];
    while (c.charAt(0) === " ") c = c.substring(1, c.length);
    if (c.indexOf(nameEQ) === 0) {
      return decodeURIComponent(c.substring(nameEQ.length, c.length));
    }
  }
  return null;
}

function deleteCookie(name) {
  document.cookie = `${name}=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;`;
}

// Comprehensive state persistence
function saveUIState() {
  setCookie(STATE_COOKIES.LAYOUT, currentLayoutState);
  setCookie(STATE_COOKIES.VIEW, currentViewState);

  if (currentBoard) {
    setCookie(STATE_COOKIES.BOARD, currentBoard);
  }

  const searchContainer = document.getElementById("search-container");
  if (searchContainer) {
    setCookie(
      STATE_COOKIES.SEARCH_VISIBLE,
      searchContainer.classList.contains("visible"),
    );
  }

  const searchInput = document.getElementById("search");
  if (searchInput && searchInput.value.trim()) {
    setCookie(STATE_COOKIES.SEARCH_QUERY, searchInput.value.trim());
  } else {
    deleteCookie(STATE_COOKIES.SEARCH_QUERY);
  }
}

function restoreUIState() {
  // Restore layout state
  const savedLayout = getCookie(STATE_COOKIES.LAYOUT);
  if (savedLayout && Object.values(LAYOUT_STATES).includes(savedLayout)) {
    currentLayoutState = savedLayout;
  }

  // Restore view state
  const savedViewState = getCookie(STATE_COOKIES.VIEW);
  if (savedViewState && Object.values(VIEW_STATES).includes(savedViewState)) {
    currentViewState = savedViewState;
  }

  // Restore board (will be applied when boards are loaded)
  const savedBoard = getCookie(STATE_COOKIES.BOARD);
  if (savedBoard) {
    currentBoard = savedBoard;
  }

  // Restore search visibility
  const searchVisible = getCookie(STATE_COOKIES.SEARCH_VISIBLE);
  if (searchVisible === "true") {
    setTimeout(() => {
      const searchContainer = document.getElementById("search-container");
      if (searchContainer && !searchContainer.classList.contains("visible")) {
        searchContainer.classList.add("visible");
        const searchInput = document.getElementById("search");
        if (searchInput) {
          searchInput.focus();
        }
      }
    }, 100);
  }

  // Restore search query
  const savedQuery = getCookie(STATE_COOKIES.SEARCH_QUERY);
  if (savedQuery) {
    setTimeout(() => {
      const searchInput = document.getElementById("search");
      if (searchInput) {
        searchInput.value = savedQuery;
        // Trigger search with saved query
        searchIssues();
      }
    }, 200);
  }
}

// Auto-save state on changes
function setupAutoSave() {
  // Save state periodically
  setInterval(saveUIState, 5000); // Every 5 seconds

  // Save on page unload
  window.addEventListener("beforeunload", saveUIState);

  // Save on visibility change (tab switch, etc.)
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) {
      saveUIState();
    }
  });
}

// Initialize layout state from cookies or default (legacy function - replaced by newer version)
function initializeLayoutState() {
  const savedLayout = getCookie && getCookie(STATE_COOKIES.LAYOUT);
  if (savedLayout && Object.values(LAYOUT_STATES).includes(savedLayout)) {
    currentLayoutState = savedLayout;
  }
  const container = document.getElementById("view-container");
  const layoutToggleBtn = document.getElementById("layout-toggle");
  if (container) {
    container.classList.add(currentLayoutState);
  }
  if (layoutToggleBtn) {
    layoutToggleBtn.innerHTML = LAYOUT_ICONS[currentLayoutState];
    layoutToggleBtn.title = LAYOUT_TITLES[currentLayoutState];
  }

  // Ensure panels are properly sized for the initial layout
  setTimeout(() => {
    resetPanelSizes();
  }, 100);
}

// Toggle view state
function toggleViewState() {
  const container = document.getElementById("view-container");
  const toggleBtn = document.getElementById("view-toggle");

  // Remove current state class
  container.classList.remove(currentViewState);

  // Cycle through states
  switch (currentViewState) {
    case VIEW_STATES.BOTH:
      currentViewState = VIEW_STATES.LIST_ONLY;
      break;
    case VIEW_STATES.LIST_ONLY:
      currentViewState = VIEW_STATES.DETAILS_ONLY;
      break;
    case VIEW_STATES.DETAILS_ONLY:
      currentViewState = VIEW_STATES.BOTH;
      break;
  }

  // Apply new state
  container.classList.add(currentViewState);
  toggleBtn.innerHTML = VIEW_ICONS[currentViewState];
  toggleBtn.title = VIEW_TITLES[currentViewState];

  // Save state to cookies
  saveUIState();
}

function toggleLayoutState() {
  const container = document.getElementById("view-container");
  const layoutToggleBtn = document.getElementById("layout-toggle");

  // Remove current layout class
  container.classList.remove(currentLayoutState);

  // Toggle layout state
  if (currentLayoutState === LAYOUT_STATES.HORIZONTAL) {
    currentLayoutState = LAYOUT_STATES.VERTICAL;
  } else {
    currentLayoutState = LAYOUT_STATES.HORIZONTAL;
  }

  // Apply new layout
  container.classList.add(currentLayoutState);
  if (layoutToggleBtn) {
    layoutToggleBtn.innerHTML = LAYOUT_ICONS[currentLayoutState];
    layoutToggleBtn.title = LAYOUT_TITLES[currentLayoutState];
  }

  // Reset panel sizes when switching layouts
  resetPanelSizes();

  // Save state to cookies
  saveUIState();
}

// Initialize view state from cookies or default
function initializeViewState() {
  const savedState = getCookie(STATE_COOKIES.VIEW);
  if (savedState && Object.values(VIEW_STATES).includes(savedState)) {
    currentViewState = savedState;
  }

  const container = document.getElementById("view-container");
  const toggleBtn = document.getElementById("view-toggle");

  container.classList.add(currentViewState);
  toggleBtn.innerHTML = VIEW_ICONS[currentViewState];
  toggleBtn.title = VIEW_TITLES[currentViewState];
}

// Navigation functions for keyboard shortcuts
function navigateIssueList(direction = "down") {
  const tbody = document.getElementById("issues-tbody");
  const rows = Array.from(tbody.querySelectorAll("tr")).filter(
    (row) => !row.querySelector(".loading") && !row.querySelector(".no-issues"),
  );

  if (rows.length === 0) return;

  let currentIndex = -1;
  if (selectedRow) {
    currentIndex = rows.findIndex((row) => row === selectedRow);
  }

  let newIndex;
  if (direction === "down") {
    newIndex = currentIndex + 1;
    if (newIndex >= rows.length) newIndex = 0; // Wrap to top
  } else {
    newIndex = currentIndex - 1;
    if (newIndex < 0) newIndex = rows.length - 1; // Wrap to bottom
  }

  const newRow = rows[newIndex];
  if (newRow) {
    // Extract issue key from the row
    const keyCell = newRow.querySelector("td:nth-child(2) a");
    if (keyCell) {
      const issueKey = keyCell.textContent.trim();
      selectRow(newRow, issueKey);

      // Scroll row into view
      newRow.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  }
}

function scrollDetailPanel(direction) {
  const detailContent = document.querySelector(".detail-content");
  if (!detailContent) return;

  const scrollAmount = 100; // pixels to scroll
  const currentScroll = detailContent.scrollTop;

  if (direction === "down") {
    detailContent.scrollTo({
      top: currentScroll + scrollAmount,
      behavior: "smooth",
    });
  } else {
    detailContent.scrollTo({
      top: currentScroll - scrollAmount,
      behavior: "smooth",
    });
  }
}

function openSelectedIssueInNewTab() {
  if (!selectedRow) {
    // If no row selected, try to select the first one
    const tbody = document.getElementById("issues-tbody");
    const firstRow = tbody.querySelector("tr:not(.loading):not(.no-issues)");
    if (firstRow) {
      const keyCell = firstRow.querySelector("td:nth-child(2) a");
      if (keyCell) {
        const issueKey = keyCell.textContent.trim();
        selectRow(firstRow, issueKey);
      }
    }
  }

  if (selectedRow) {
    const keyCell = selectedRow.querySelector("td:nth-child(2) a");
    if (keyCell) {
      const issueKey = keyCell.textContent.trim();
      const jiraBaseUrl = getJiraBaseUrl();
      if (jiraBaseUrl) {
        const issueUrl = `${jiraBaseUrl}/browse/${issueKey}`;
        window.open(issueUrl, "_blank");
        showNotification(`Opened ${issueKey} in new tab`);
      } else {
        showNotification("Error: Jira base URL not configured", "error");
      }
    }
  } else {
    showNotification("No issue selected", "error");
  }
}

function yankIssueUrl() {
  if (!selectedRow) {
    // If no row selected, try to select the first one
    const tbody = document.getElementById("issues-tbody");
    const firstRow = tbody.querySelector("tr:not(.loading):not(.no-issues)");
    if (firstRow) {
      const keyCell = firstRow.querySelector("td:nth-child(2) a");
      if (keyCell) {
        const issueKey = keyCell.textContent.trim();
        selectRow(firstRow, issueKey);
      }
    }
  }

  if (selectedRow) {
    const keyCell = selectedRow.querySelector("td:nth-child(2) a");
    if (keyCell) {
      const issueKey = keyCell.textContent.trim();
      const jiraBaseUrl = getJiraBaseUrl();
      if (jiraBaseUrl) {
        const issueUrl = `${jiraBaseUrl}/browse/${issueKey}`;
        navigator.clipboard
          .writeText(issueUrl)
          .then(() => {
            showNotification(`Copied ${issueKey} URL to clipboard`);
          })
          .catch(() => {
            showNotification(`Failed to copy URL for ${issueKey}`, "error");
          });
      } else {
        // Fallback: copy just the issue key
        navigator.clipboard
          .writeText(issueKey)
          .then(() => {
            showNotification(`Copied issue key ${issueKey} to clipboard`);
          })
          .catch(() => {
            showNotification(`Failed to copy issue key ${issueKey}`, "error");
          });
      }
    }
  } else {
    showNotification("No issue selected", "error");
  }
}

function editSelectedIssueLabels() {
  if (!selectedRow) {
    // If no row selected, try to select the first one
    const tbody = document.getElementById("issues-tbody");
    const firstRow = tbody.querySelector("tr:not(.loading):not(.no-issues)");
    if (firstRow) {
      const keyCell = firstRow.querySelector("td:nth-child(2) a");
      if (keyCell) {
        const issueKey = keyCell.textContent.trim();
        selectRow(firstRow, issueKey);
        // Wait for detail to load, then open label editor
        setTimeout(() => {
          editSelectedIssueLabels();
        }, 500);
        return;
      }
    }
  }

  if (selectedRow) {
    const keyCell = selectedRow.querySelector("td:nth-child(2) a");
    if (keyCell) {
      const issueKey = keyCell.textContent.trim();

      // Get current labels from the detail panel if it exists
      const detailPanel = document.getElementById("detail-panel");
      const labelTags = detailPanel.querySelectorAll(".label-tag");
      const currentLabels = Array.from(labelTags).map((tag) =>
        tag.textContent.trim(),
      );

      editLabels(issueKey, currentLabels);
    }
  } else {
    showNotification(
      "No issue selected. Use j/k to navigate or click an issue.",
      "error",
    );
  }
}

function showHelpOverlay() {
  // Remove existing overlay if it exists
  const existingOverlay = document.getElementById("help-overlay");
  if (existingOverlay) {
    existingOverlay.remove();
  }

  // Create new help overlay
  const overlay = document.createElement("div");
  overlay.id = "help-overlay";
  overlay.style.cssText = `
                position: fixed;
                top: 0;
                left: 0;
                width: 100vw;
                height: 100vh;
                background-color: rgba(0, 0, 0, 0.7);
                z-index: 10000;
                display: flex;
                align-items: center;
                justify-content: center;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                animation: fadeIn 0.2s ease;
            `;

  const helpContent = document.createElement("div");
  helpContent.style.cssText = `
                background: #ffffff;
                color: #333333;
                border: 1px solid #e1e4e8;
                border-radius: 8px;
                padding: 2rem;
                max-width: 550px;
                max-height: 80vh;
                overflow-y: auto;
                box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3);
                margin: 1rem;
            `;

  helpContent.innerHTML = `
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem; border-bottom: 1px solid #e1e4e8; padding-bottom: 1rem;">
                    <h2 style="margin: 0; color: #0366d6; font-size: 1.25rem;">🚀 Jayrah Keyboard Shortcuts</h2>
                    <button id="close-help" style="background: none; border: none; font-size: 1.5rem; cursor: pointer; color: #6a737d; padding: 0.25rem;">&times;</button>
                </div>
                
                <div style="margin-bottom: 1.5rem;">
                    <h3 style="margin: 0 0 0.75rem 0; color: #0366d6; font-size: 1rem; border-bottom: 1px solid #f1f3f4; padding-bottom: 0.5rem;">📋 Navigation</h3>
                    <div style="display: grid; grid-template-columns: auto 1fr; gap: 0.5rem 1rem; margin-bottom: 1rem;">
                        <kbd style="background: #f6f8fa; border: 1px solid #d1d5da; border-radius: 3px; padding: 0.2rem 0.4rem; font-size: 0.8rem; font-weight: bold; color: #24292e;">j</kbd>
                        <span style="color: #586069;">Move down in issue list</span>
                        <kbd style="background: #f6f8fa; border: 1px solid #d1d5da; border-radius: 3px; padding: 0.2rem 0.4rem; font-size: 0.8rem; font-weight: bold; color: #24292e;">k</kbd>
                        <span style="color: #586069;">Move up in issue list</span>
                        <kbd style="background: #f6f8fa; border: 1px solid #d1d5da; border-radius: 3px; padding: 0.2rem 0.4rem; font-size: 0.8rem; font-weight: bold; color: #24292e;">Page Down</kbd>
                        <span style="color: #586069;">Jump down ~10 issues</span>
                        <kbd style="background: #f6f8fa; border: 1px solid #d1d5da; border-radius: 3px; padding: 0.2rem 0.4rem; font-size: 0.8rem; font-weight: bold; color: #24292e;">Page Up</kbd>
                        <span style="color: #586069;">Jump up ~10 issues</span>
                        <kbd style="background: #f6f8fa; border: 1px solid #d1d5da; border-radius: 3px; padding: 0.2rem 0.4rem; font-size: 0.8rem; font-weight: bold; color: #24292e;">Home</kbd>
                        <span style="color: #586069;">Go to first issue</span>
                        <kbd style="background: #f6f8fa; border: 1px solid #d1d5da; border-radius: 3px; padding: 0.2rem 0.4rem; font-size: 0.8rem; font-weight: bold; color: #24292e;">End</kbd>
                        <span style="color: #586069;">Go to last issue</span>
                        <kbd style="background: #f6f8fa; border: 1px solid #d1d5da; border-radius: 3px; padding: 0.2rem 0.4rem; font-size: 0.8rem; font-weight: bold; color: #24292e;">J</kbd>
                        <span style="color: #586069;">Scroll detail panel down</span>
                        <kbd style="background: #f6f8fa; border: 1px solid #d1d5da; border-radius: 3px; padding: 0.2rem 0.4rem; font-size: 0.8rem; font-weight: bold; color: #24292e;">K</kbd>
                        <span style="color: #586069;">Scroll detail panel up</span>
                        <kbd style="background: #f6f8fa; border: 1px solid #d1d5da; border-radius: 3px; padding: 0.2rem 0.4rem; font-size: 0.8rem; font-weight: bold; color: #24292e;">Shift+Page Down</kbd>
                        <span style="color: #586069;">Scroll detail panel down (page)</span>
                        <kbd style="background: #f6f8fa; border: 1px solid #d1d5da; border-radius: 3px; padding: 0.2rem 0.4rem; font-size: 0.8rem; font-weight: bold; color: #24292e;">Shift+Page Up</kbd>
                        <span style="color: #586069;">Scroll detail panel up (page)</span>
                        <kbd style="background: #f6f8fa; border: 1px solid #d1d5da; border-radius: 3px; padding: 0.2rem 0.4rem; font-size: 0.8rem; font-weight: bold; color: #24292e;">Space</kbd>
                        <span style="color: #586069;">Scroll detail panel down (page)</span>
                        <kbd style="background: #f6f8fa; border: 1px solid #d1d5da; border-radius: 3px; padding: 0.2rem 0.4rem; font-size: 0.8rem; font-weight: bold; color: #24292e;">Shift+Space</kbd>
                        <span style="color: #586069;">Scroll detail panel up (page)</span>
                    </div>
                </div>
                
                <div style="margin-bottom: 1.5rem;">
                    <h3 style="margin: 0 0 0.75rem 0; color: #0366d6; font-size: 1rem; border-bottom: 1px solid #f1f3f4; padding-bottom: 0.5rem;">⚡ Actions</h3>
                    <div style="display: grid; grid-template-columns: auto 1fr; gap: 0.5rem 1rem; margin-bottom: 1rem;">
                        <kbd style="background: #f6f8fa; border: 1px solid #d1d5da; border-radius: 3px; padding: 0.2rem 0.4rem; font-size: 0.8rem; font-weight: bold; color: #24292e;">o</kbd>
                        <span style="color: #586069;">Open selected issue in new Jira tab</span>
                        <kbd style="background: #f6f8fa; border: 1px solid #d1d5da; border-radius: 3px; padding: 0.2rem 0.4rem; font-size: 0.8rem; font-weight: bold; color: #24292e;">y</kbd>
                        <span style="color: #586069;">Yank (copy) issue URL to clipboard</span>
                        <kbd style="background: #f6f8fa; border: 1px solid #d1d5da; border-radius: 3px; padding: 0.2rem 0.4rem; font-size: 0.8rem; font-weight: bold; color: #24292e;">L</kbd>
                        <span style="color: #586069;">Edit labels for selected issue</span>
                    </div>
                </div>
                
                <div style="margin-bottom: 1.5rem;">
                    <h3 style="margin: 0 0 0.75rem 0; color: #0366d6; font-size: 1rem; border-bottom: 1px solid #f1f3f4; padding-bottom: 0.5rem;">👁️ View & Navigation</h3>
                    <div style="display: grid; grid-template-columns: auto 1fr; gap: 0.5rem 1rem; margin-bottom: 1rem;">
                        <kbd style="background: #f6f8fa; border: 1px solid #d1d5da; border-radius: 3px; padding: 0.2rem 0.4rem; font-size: 0.8rem; font-weight: bold; color: #24292e;">t</kbd>
                        <span style="color: #586069;">Toggle view mode (list/detail/both)</span>
                        <kbd style="background: #f6f8fa; border: 1px solid #d1d5da; border-radius: 3px; padding: 0.2rem 0.4rem; font-size: 0.8rem; font-weight: bold; color: #24292e;">v</kbd>
                        <span style="color: #586069;">Toggle layout (horizontal/vertical)</span>
                        <kbd style="background: #f6f8fa; border: 1px solid #d1d5da; border-radius: 3px; padding: 0.2rem 0.4rem; font-size: 0.8rem; font-weight: bold; color: #24292e;">b</kbd>
                        <span style="color: #586069;">Switch board</span>
                        <kbd style="background: #f6f8fa; border: 1px solid #d1d5da; border-radius: 3px; padding: 0.2rem 0.4rem; font-size: 0.8rem; font-weight: bold; color: #24292e;">r</kbd>
                        <span style="color: #586069;">Refresh issues and clear cache</span>
                        <kbd style="background: #f6f8fa; border: 1px solid #d1d5da; border-radius: 3px; padding: 0.2rem 0.4rem; font-size: 0.8rem; font-weight: bold; color: #24292e;">/</kbd>
                        <span style="color: #586069;">Toggle search bar</span>
                    </div>
                </div>
                
                <div style="margin-bottom: 1.5rem;">
                    <h3 style="margin: 0 0 0.75rem 0; color: #0366d6; font-size: 1rem; border-bottom: 1px solid #f1f3f4; padding-bottom: 0.5rem;">❓ Help</h3>
                    <div style="display: grid; grid-template-columns: auto 1fr; gap: 0.5rem 1rem; margin-bottom: 1rem;">
                        <kbd style="background: #f6f8fa; border: 1px solid #d1d5da; border-radius: 3px; padding: 0.2rem 0.4rem; font-size: 0.8rem; font-weight: bold; color: #24292e;">?</kbd>
                        <span style="color: #586069;">Show this help overlay</span>
                        <kbd style="background: #f6f8fa; border: 1px solid #d1d5da; border-radius: 3px; padding: 0.2rem 0.4rem; font-size: 0.8rem; font-weight: bold; color: #24292e;">s</kbd>
                        <span style="color: #586069;">Show board statistics</span>
                        <kbd style="background: #f6f8fa; border: 1px solid #d1d5da; border-radius: 3px; padding: 0.2rem 0.4rem; font-size: 0.8rem; font-weight: bold; color: #24292e;">Esc</kbd>
                        <span style="color: #586069;">Close detail panel or help overlay</span>
                    </div>
                </div>
                
                <div style="padding-top: 1rem; border-top: 1px solid #e1e4e8; color: #6a737d; font-size: 0.875rem;">
                    <p style="margin: 0 0 0.5rem 0; font-weight: 600; color: #24292e;">💡 Tips:</p>
                    <ul style="margin: 0; padding-left: 1.2rem; line-height: 1.4;">
                        <li style="margin-bottom: 0.25rem;">Press '/' or click 🔍 to toggle the search bar</li>
                        <li style="margin-bottom: 0.25rem;">Use the search box to filter issues by key, summary, assignee, or status</li>
                        <li style="margin-bottom: 0.25rem;">Click on any issue to view its details</li>
                        <li style="margin-bottom: 0.25rem;">Press 'v' to toggle between horizontal (side by side) and vertical (top/bottom) layouts</li>
                        <li style="margin-bottom: 0.25rem;">Navigation wraps around (j at bottom goes to top, k at top goes to bottom)</li>
                        <li style="margin-bottom: 0.25rem;">Page Up/Down jump ~10 issues; Home/End go to first/last issue</li>
                        <li style="margin-bottom: 0.25rem;">Use Shift+Page Up/Down for fast detail panel scrolling</li>
                        <li style="margin-bottom: 0.25rem;">All shortcuts work except when typing in search box</li>
                    </ul>
                </div>
            `;

  overlay.appendChild(helpContent);
  document.body.appendChild(overlay);

  // Close on click outside or close button
  overlay.addEventListener("click", (e) => {
    if (e.target === overlay) {
      hideHelpOverlay();
    }
  });

  const closeBtn = helpContent.querySelector("#close-help");
  if (closeBtn) {
    closeBtn.addEventListener("click", hideHelpOverlay);
  }
}

function hideHelpOverlay() {
  const overlay = document.getElementById("help-overlay");
  if (overlay) {
    overlay.remove();
  }
}

function openIssueInTab(issueKey) {
  const jiraBaseUrl = getJiraBaseUrl();
  if (jiraBaseUrl) {
    const issueUrl = `${jiraBaseUrl}/browse/${issueKey}`;
    window.open(issueUrl, "_blank");
    showNotification(`Opened ${issueKey} in new tab`);
  } else {
    showNotification("Error: Jira base URL not configured", "error");
  }
}

function getJiraBaseUrl() {
  return jiraBaseUrl;
}

async function loadConfig() {
  try {
    const res = await fetch("/api/config");
    if (res.ok) {
      const config = await res.json();
      jiraBaseUrl = config.jira_base_url;
    }
  } catch (error) {
    console.error("Error loading config:", error);
  }
}

function showNotification(message, type = "success") {
  // Create a simple notification
  const notification = document.createElement("div");
  let bgColor = "var(--primary-color)";
  if (type === "success") {
    bgColor = "var(--success-color)";
  } else if (type === "error") {
    bgColor = "#dc3545"; // Red for errors
  } else if (type === "info") {
    bgColor = "var(--primary-color)"; // Blue for info
  }

  notification.style.cssText = `
                position: fixed;
                top: 20px;
                right: 20px;
                background: ${bgColor};
                color: white;
                padding: 0.75rem 1rem;
                border-radius: var(--radius);
                box-shadow: var(--shadow);
                z-index: 1000;
                font-size: 0.875rem;
                max-width: 300px;
            `;
  notification.textContent = message;

  document.body.appendChild(notification);

  // Remove after 3 seconds
  setTimeout(() => {
    if (notification.parentNode) {
      notification.parentNode.removeChild(notification);
    }
  }, 3000);
}

// Convert Jira markup to standard markdown
function convertJiraToMarkdown(text) {
  if (!text) return "";

  // Handle different text formats
  if (typeof text === "object") {
    // If it's an object, try to extract text content
    if (text.content) {
      // Handle ADF (Atlassian Document Format)
      return extractTextFromADF(text);
    } else if (text.raw) {
      text = text.raw;
    } else {
      text = JSON.stringify(text);
    }
  }

  // Convert Jira markup to standard markdown
  let markdown = text.toString();

  // Headers: h1. -> #, h2. -> ##, etc.
  markdown = markdown.replace(
    /^h([1-6])\.\s+(.+)$/gm,
    (match, level, content) => {
      return "#".repeat(parseInt(level)) + " " + content;
    },
  );

  // Bold: *text* -> **text**
  markdown = markdown.replace(/\*([^*]+)\*/g, "**$1**");

  // Italic: _text_ -> *text*
  markdown = markdown.replace(/_([^_]+)_/g, "*$1*");

  // Code blocks: {code} -> ```
  markdown = markdown.replace(
    /\{code(?::([^}]*))?\}([\s\S]*?)\{code\}/g,
    (match, lang, code) => {
      return "```" + (lang || "") + "\n" + code.trim() + "\n```";
    },
  );

  // Inline code: {{text}} -> `text`
  markdown = markdown.replace(/\{\{([^}]+)\}\}/g, "`$1`");

  // Links: [text|url] -> [text](url)
  markdown = markdown.replace(/\[([^|\]]+)\|([^\]]+)\]/g, "[$1]($2)");

  // Lists: * item -> - item (already compatible)
  // Numbers: # item -> 1. item
  markdown = markdown.replace(/^#\s+(.+)$/gm, "1. $1");

  // Line breaks: Convert \r\n or \n to proper breaks
  markdown = markdown.replace(/\r\n/g, "\n");

  return markdown;
}

// Extract text from Atlassian Document Format (ADF)
function extractTextFromADF(adf) {
  if (!adf || typeof adf !== "object") return "";

  let text = "";

  if (adf.type === "text") {
    text = adf.text || "";
    // Apply marks if present
    if (adf.marks) {
      adf.marks.forEach((mark) => {
        if (mark.type === "strong") text = `**${text}**`;
        if (mark.type === "em") text = `*${text}*`;
        if (mark.type === "code") text = `\`${text}\``;
        if (mark.type === "link") text = `[${text}](${mark.attrs?.href || ""})`;
      });
    }
  } else if (adf.type === "paragraph") {
    if (adf.content) {
      text = adf.content.map(extractTextFromADF).join("") + "\n\n";
    }
  } else if (adf.type === "heading") {
    const level = adf.attrs?.level || 1;
    if (adf.content) {
      text =
        "#".repeat(level) +
        " " +
        adf.content.map(extractTextFromADF).join("") +
        "\n\n";
    }
  } else if (adf.type === "codeBlock") {
    const lang = adf.attrs?.language || "";
    if (adf.content) {
      text =
        "```" +
        lang +
        "\n" +
        adf.content.map(extractTextFromADF).join("") +
        "\n```\n\n";
    }
  } else if (adf.type === "bulletList" || adf.type === "orderedList") {
    if (adf.content) {
      text =
        adf.content
          .map((item) => {
            const prefix = adf.type === "bulletList" ? "- " : "1. ";
            return prefix + extractTextFromADF(item);
          })
          .join("") + "\n";
    }
  } else if (adf.type === "listItem") {
    if (adf.content) {
      text = adf.content.map(extractTextFromADF).join("") + "\n";
    }
  } else if (adf.content) {
    // Recursively process content array
    text = adf.content.map(extractTextFromADF).join("");
  }

  return text;
}

// Convert markdown to HTML
function markdownToHtml(markdown) {
  if (!markdown) return "";
  return marked.parse(markdown);
}

async function fetchIssues(q = "") {
  try {
    const url = q ? `/api/issues?q=${encodeURIComponent(q)}` : "/api/issues";
    const res = await fetch(url);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (error) {
    console.error("Error fetching issues:", error);
    return [];
  }
}

async function refreshIssues() {
  try {
    // Call the refresh API endpoint to clear cache and get fresh data
    const refreshRes = await fetch("/api/refresh", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
    });

    if (!refreshRes.ok) {
      throw new Error(`Refresh failed: HTTP ${refreshRes.status}`);
    }

    // Get current search query if any
    const searchInput = document.getElementById("search");
    const query = searchInput ? searchInput.value.trim() : "";

    // Fetch issues with current search query (will get fresh data after cache clear)
    allIssues = await fetchIssues(query);

    // Re-render the table
    renderTable(allIssues);

    // Close detail panel to refresh the view
    closeDetail();

    // Auto-select first issue after refresh if any exist
    setTimeout(() => {
      if (allIssues.length > 0) {
        const tbody = document.getElementById("issues-tbody");
        const firstRow = tbody.querySelector("tr[data-issue-key]");
        if (firstRow) {
          const issueKey = firstRow.dataset.issueKey;
          selectRow(firstRow, issueKey);
          console.log("Auto-selected first issue after refresh:", issueKey);
        }
      }
    }, 100);

    console.log("Issues refreshed successfully");
  } catch (error) {
    console.error("Error refreshing issues:", error);
  }
}

async function fetchIssueDetail(key) {
  try {
    const res = await fetch(`/api/issue/${key}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    return data;
  } catch (error) {
    console.error("Error fetching issue detail:", error);
    return { error: "Failed to load issue details" };
  }
}

function formatIssueDetail(data) {
  if (data.error) {
    return `<div class="detail-section"><p style="color: var(--error-color);">Error: ${data.error}</p></div>`;
  }

  const issue = data.issue || data; // Handle both old and new format
  const customFields = data.custom_fields || [];
  const fields = issue.fields || {};
  const key = issue.key || "Unknown";
  const summary = fields.summary || "No summary";
  const description = fields.description || "No description provided";
  const status = fields.status?.name || "Unknown";
  const assignee =
    fields.assignee?.displayName || fields.assignee?.name || "Unassigned";
  const reporter =
    fields.reporter?.displayName || fields.reporter?.name || "Unknown";
  const priority = fields.priority?.name || "Unknown";
  const issueType = fields.issuetype?.name || "Unknown";
  const created = fields.created
    ? new Date(fields.created).toLocaleString()
    : "Unknown";
  const updated = fields.updated
    ? new Date(fields.updated).toLocaleString()
    : "Unknown";
  const labels = fields.labels || [];
  const components = fields.components || [];
  const fixVersions = fields.fixVersions || [];

  let html = `
                <div class="detail-section">
                    <h3><div class="detail-label">Ticket <a href="#" class="issue-key" onclick="openIssueInTab('${key}'); return false;">${key}</a></div></h3>
                    <div class="detail-field">
                        <div class="detail-label">Type:</div>
                        <div class="detail-value">${issueType}</div>
                    </div>
                    <div class="detail-field">
                        <div class="detail-label">Status:</div>

                        <div class="detail-value">
                            <span class="status-badge ${getStatusClass(status)}">${status}</span>
                            <button class="transition-edit-btn" title="Edit transitions" style="background:none;border:none;cursor:pointer;padding:0.25rem;margin-left:0.5rem;vertical-align:middle;border-radius:4px;" onmouseenter="this.style.backgroundColor='#f0f0f0'" onmouseleave="this.style.backgroundColor='transparent'">
                                <svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24" style="color:#666;">
                                    <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                                    <path d="m18.5 2.5 a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                                </svg>
                            </button>
                        </div>
                    </div>
                    <div class="detail-field">
                        <div class="detail-label">Priority:</div>
                        <div class="detail-value">${priority}</div>
                    </div>
                    <div class="detail-field">
                        <div class="detail-label">Summary:</div>
                        <div class="detail-value"><strong>${summary}</strong></div>
                    </div>
                </div>

                <div class="detail-section">
                    <h3>👥 People</h3>
                    <div class="detail-field">
                        <div class="detail-label">Assignee:</div>
                        <div class="detail-value">
                            <div class="user-avatar">
                                <div class="avatar">${getUserInitials(assignee)}</div>
                                <span>${assignee}</span>
                            </div>
                        </div>
                    </div>
                    <div class="detail-field">
                        <div class="detail-label">Reporter:</div>
                        <div class="detail-value">
                            <div class="user-avatar">
                                <div class="avatar">${getUserInitials(reporter)}</div>
                                <span>${reporter}</span>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="detail-section">
                    <h3>📅 Dates</h3>
                    <div class="detail-field">
                        <div class="detail-label">Created:</div>
                        <div class="detail-value">${created}</div>
                    </div>
                    <div class="detail-field">
                        <div class="detail-label">Updated:</div>
                        <div class="detail-value">${updated}</div>
                    </div>
                </div>
            `;

  if (labels.length > 0) {
    html += `
                    <div class="detail-section">
                        <h3>🏷️ Labels 
                            <button class="edit-label-btn" onclick="editLabels('${key}', ${JSON.stringify(labels).replace(/"/g, "&quot;")})">
                                <svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24" style="color:#666;">
                                    <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                                    <path d="m18.5 2.5 a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                                </svg>
                            </button>
                        </h3>
                        <div class="detail-labels">
                            ${labels.map((label) => `<span class="label-tag">${label}</span>`).join("")}
                        </div>
                    </div>
                `;
  } else {
    html += `
                    <div class="detail-section">
                        <h3>🏷️ Labels 
                            <button class="edit-label-btn" onclick="editLabels('${key}', [])">
                                <svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24" style="color:#666;">
                                    <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                                    <path d="m18.5 2.5 a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                                </svg>
                            </button>
                        </h3>
                        <div class="detail-labels">
                            <span style="color: var(--text-muted); font-style: italic;">No labels</span>
                        </div>
                    </div>
                `;
  }

  if (components.length > 0) {
    html += `
                    <div class="detail-section">
                        <h3>🔧 Components</h3>
                        <div class="detail-value">
                            ${components.map((comp) => comp.name || comp).join(", ")}
                        </div>
                    </div>
                `;
  }

  if (fixVersions.length > 0) {
    html += `
                    <div class="detail-section">
                        <h3>🎯 Fix Versions</h3>
                        <div class="detail-value">
                            ${fixVersions.map((ver) => ver.name || ver).join(", ")}
                        </div>
                    </div>
                `;
  }

  // Show custom fields if present
  if (customFields.length > 0) {
    let customFieldsHtml = "";
    customFields.forEach((cf) => {
      const fieldId = cf.field;
      const fieldName = cf.name || fieldId;
      const fieldType = cf.type || "string";

      if (fieldId && fields[fieldId]) {
        let value = fields[fieldId];

        // Handle different value types
        if (Array.isArray(value)) {
          value = value
            .map((v) => {
              if (typeof v === "object" && v !== null) {
                return v.value || v.name || v.displayName || JSON.stringify(v);
              }
              return v;
            })
            .filter((v) => v)
            .join(", ");
        } else if (typeof value === "object" && value !== null) {
          value =
            value.value ||
            value.name ||
            value.displayName ||
            JSON.stringify(value);
        }

        if (value) {
          // Properly escape the value for JavaScript onclick attribute
          const escapedValue = value.toString()
            .replace(/\\/g, '\\\\')  // Escape backslashes first
            .replace(/'/g, "\\'")    // Escape single quotes
            .replace(/"/g, '\\"')    // Escape double quotes
            .replace(/\r/g, '\\r')   // Escape carriage returns
            .replace(/\n/g, '\\n')   // Escape newlines
            .replace(/\t/g, '\\t');  // Escape tabs

          if (fieldType === "text") {
            customFieldsHtml += `
                                    <div class="detail-field">
                                        <div class="detail-label">${fieldName}:</div>
                                        <div class="detail-value">
                                            <div class="detail-description">${value}</div>
                                            <button class="custom-field-edit-btn" onclick="editCustomField('${fieldId}', '${fieldName}', '${fieldType}', '${escapedValue}')">✏️</button>
                                        </div>
                                    </div>
                                `;
          } else if (fieldType === "url") {
            customFieldsHtml += `
                                    <div class="detail-field">
                                        <div class="detail-label">${fieldName}:</div>
                                        <div class="detail-value">
                                            <a href="${value}" class="detail-link" target="_blank">${value}</a>
                                            <button class="custom-field-edit-btn" onclick="editCustomField('${fieldId}', '${fieldName}', '${fieldType}', '${escapedValue}')">✏️</button>
                                        </div>
                                    </div>
                                `;
          } else {
            customFieldsHtml += `
                                    <div class="detail-field">
                                        <div class="detail-label">${fieldName}:</div>
                                        <div class="detail-value">
                                            ${value}
                                            <button class="custom-field-edit-btn" onclick="editCustomField('${fieldId}', '${fieldName}', '${fieldType}', '${escapedValue}')">✏️</button>
                                        </div>
                                    </div>
                                `;
          }
        } else {
          // Show empty field with edit button for fields that don't have values yet
          customFieldsHtml += `
                                <div class="detail-field">
                                    <div class="detail-label">${fieldName}:</div>
                                    <div class="detail-value">
                                        <em>(empty)</em>
                                        <button class="custom-field-edit-btn" onclick="editCustomField('${fieldId}', '${fieldName}', '${fieldType}', '')">✏️</button>
                                    </div>
                                </div>
                            `;
        }
      }
    });

    if (customFieldsHtml) {
      html += `
                        <div class="detail-section">
                            <h3>🔧 Fields</h3>
                            ${customFieldsHtml}
                        </div>
                    `;
    }
  }

  html += `
                <div class="detail-section">
                    <h3>📝 Description</h3>
                    <div class="detail-description">${markdownToHtml(convertJiraToMarkdown(description))}</div>
                </div>

                <button class="raw-json-toggle" onclick="toggleRawJson()">
                    🔍 Show Raw JSON
                </button>
                <div class="raw-json" id="raw-json">${JSON.stringify(issue, null, 2)}</div>
            `;

  return html;
}

function toggleRawJson() {
  const rawJson = document.getElementById("raw-json");
  const button = document.querySelector(".raw-json-toggle");

  if (rawJson.style.display === "none" || rawJson.style.display === "") {
    rawJson.style.display = "block";
    button.textContent = "📋 Hide Raw JSON";
  } else {
    rawJson.style.display = "none";
    button.textContent = "🔍 Show Raw JSON";
  }
}

function getStatusClass(status) {
  const statusLower = status.toLowerCase();
  if (
    statusLower.includes("todo") ||
    statusLower.includes("new") ||
    statusLower.includes("open")
  )
    return "status-todo";
  if (statusLower.includes("progress") || statusLower.includes("doing"))
    return "status-progress";
  if (statusLower.includes("review") || statusLower.includes("qa"))
    return "status-review";
  if (
    statusLower.includes("done") ||
    statusLower.includes("closed") ||
    statusLower.includes("resolved")
  )
    return "status-done";
  return "status-default";
}

function getUserInitials(name) {
  if (!name || name === "None") return "?";
  return name
    .split(" ")
    .map((n) => n[0])
    .join("")
    .toUpperCase()
    .slice(0, 2);
}

function formatDate(dateStr) {
  if (!dateStr) return "";
  const date = new Date(dateStr);
  return date.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
  });
}

function renderTable(issues) {
  const tbody = document.getElementById("issues-tbody");

  if (issues.length === 0) {
    tbody.innerHTML =
      '<tr><td colspan="8" class="no-issues">No issues found</td></tr>';
    return;
  }

  tbody.innerHTML = issues
    .map(
      (row, index) => `
                <tr onclick="selectRow(this, '${row[1]}')" data-issue-key="${row[1]}">
                    <td><span class="issue-type">${row[0]}</span></td>
                    <td><a href="#" class="issue-key">${row[1]}</a></td>
                    <td><div class="issue-summary" title="${row[2]}">${row[2]}</div></td>
                    <td><span class="status-badge ${getStatusClass(row[3])}">${row[3]}</span></td>
                    <td>
                        <div class="user-avatar">
                            <div class="avatar">${getUserInitials(row[4])}</div>
                            <span>${row[4]}</span>
                        </div>
                    </td>
                    <td>
                        <div class="user-avatar">
                            <div class="avatar">${getUserInitials(row[5])}</div>
                            <span>${row[5]}</span>
                        </div>
                    </td>
                    <td><span class="date">${formatDate(row[6])}</span></td>
                    <td><span class="date">${formatDate(row[7])}</span></td>
                </tr>
            `,
    )
    .join("");

  updateStats(issues.length);
}

function updateStats(count) {
  document.getElementById("stats").textContent =
    `${count} issue${count !== 1 ? "s" : ""}`;
}

async function selectRow(row, key) {
  // Remove previous selection
  if (selectedRow) {
    selectedRow.classList.remove("selected");
  }

  // Select new row
  selectedRow = row;
  row.classList.add("selected");

  // Show detail panel
  const detail = await fetchIssueDetail(key);
  showDetail(key, detail);

  // Save state when issue is selected
  saveUIState();
}

function showDetail(key, detail) {
  // Store current issue key and details for custom field editing
  window.currentIssueKey = key;
  window.currentIssue = detail;
  
  const panel = document.getElementById("detail-panel");
  panel.classList.remove("empty");

  // Render status with transition icon
  let statusHtml = "";
  if (detail.fields && detail.fields.status) {
    const statusName = detail.fields.status.name;
    statusHtml = `<span class="status-label ${getStatusClass(statusName)}">${statusName}</span>`;
  }

  panel.innerHTML = `
                <div class="detail-content">
                    ${formatIssueDetail(detail)}
                </div>
            `;

  // Add event listener to transition icon
  const transitionBtn = panel.querySelector(".transition-edit-btn");
  if (transitionBtn) {
    transitionBtn.addEventListener("click", () =>
      editSelectedIssueTransition(),
    );
  }
}

function closeDetail() {
  const panel = document.getElementById("detail-panel");
  panel.classList.add("empty");
  panel.innerHTML = "";
}

// Search functionality with debouncing
let searchTimeout;
document.getElementById("search").addEventListener("input", (e) => {
  clearTimeout(searchTimeout);
  searchTimeout = setTimeout(async () => {
    const issues = await fetchIssues(e.target.value);
    renderTable(issues);
    closeDetail(); // Close detail panel when searching

    // Auto-select first issue in search results if any exist
    setTimeout(() => {
      if (issues.length > 0) {
        const tbody = document.getElementById("issues-tbody");
        const firstRow = tbody.querySelector("tr[data-issue-key]");
        if (firstRow) {
          const issueKey = firstRow.dataset.issueKey;
          selectRow(firstRow, issueKey);
          console.log("Auto-selected first search result:", issueKey);
        }
      }
    }, 100);

    // Save state when search query changes
    saveUIState();
  }, 300);
});

// Search toggle functionality
function toggleSearchBar() {
  const searchContainer = document.querySelector(".search-container");
  const searchToggle = document.getElementById("search-toggle");
  const searchInput = document.getElementById("search");

  if (searchContainer.classList.contains("visible")) {
    // Hide search
    searchContainer.classList.remove("visible");
    searchToggle.classList.remove("active");
    searchToggle.title = "Show search (Press /)";

    // Clear search if hiding
    if (searchInput.value.trim()) {
      searchInput.value = "";
      // Trigger search to show all issues
      fetchIssues().then((issues) => renderTable(issues));
      closeDetail();
    }
  } else {
    // Show search
    searchContainer.classList.add("visible");
    searchToggle.classList.add("active");
    searchToggle.title = "Hide search (Press /)";

    // Focus on search input after animation
    setTimeout(() => {
      searchInput.focus();
    }, 200);
  }

  // Save state when search visibility changes
  saveUIState();
}

// Keyboard shortcuts
document.addEventListener("keydown", (e) => {
  // Don't trigger shortcuts when typing in input fields
  if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA") {
    return;
  }

  if (e.key === "Escape") {
    // Close help overlay first, then stats modal, then board modal, then custom field modal, then search, then detail panel
    const helpOverlay = document.getElementById("help-overlay");
    const statsModal = document.getElementById("stats-modal");
    const boardModal = document.getElementById("board-modal");
    const customFieldModal = document.getElementById("custom-field-modal");
    const searchContainer = document.querySelector(".search-container");
    if (helpOverlay && helpOverlay.style.display !== "none") {
      hideHelpOverlay();
    } else if (statsModal && statsModal.style.display !== "none") {
      hideStatsModal();
    } else if (boardModal) {
      hideBoardSelector();
    } else if (customFieldModal && customFieldModal.style.display !== "none") {
      hideCustomFieldModal();
    } else if (
      searchContainer &&
      searchContainer.classList.contains("visible")
    ) {
      toggleSearchBar();
    } else {
      closeDetail();
    }
  } else if (e.key === "t") {
    toggleViewState();
  } else if (e.key === "T") {
    // Shift+T: open transition modal
    e.preventDefault();
    editSelectedIssueTransition();
  } else if (e.key.toLowerCase() === "v") {
    toggleLayoutState();
  } else if (e.key.toLowerCase() === "b") {
    showBoardSelector();
  } else if (e.key === "r") {
    refreshIssues();
  } else if (e.key === "/") {
    toggleSearchBar();
  } else if (e.key === "j") {
    e.preventDefault();
    navigateIssueList("down");
  } else if (e.key === "k") {
    e.preventDefault();
    navigateIssueList("up");
  } else if (e.key === "J") {
    e.preventDefault();
    scrollDetailPanel("down");
  } else if (e.key === "K") {
    e.preventDefault();
    scrollDetailPanel("up");
  } else if (e.key === "o" || e.key === "O") {
    e.preventDefault();
    openSelectedIssueInNewTab();
  } else if (e.key === "y" || e.key === "Y") {
    e.preventDefault();
    yankIssueUrl();
  } else if (e.key === "L") {
    e.preventDefault();
    editSelectedIssueLabels();
  } else if (e.key === "?") {
    e.preventDefault();
    showHelpOverlay();
  } else if (e.key.toLowerCase() === "s") {
    e.preventDefault();
    showStatsModal();
  } else if (e.key === "Home") {
    e.preventDefault();
    navigateToFirstIssue();
  } else if (e.key === "End") {
    e.preventDefault();
    navigateToLastIssue();
  } else if (e.key === "PageUp") {
    e.preventDefault();
    if (e.shiftKey) {
      scrollDetailPanelPage("up");
    } else {
      navigatePageUp();
    }
  } else if (e.key === "PageDown") {
    e.preventDefault();
    if (e.shiftKey) {
      scrollDetailPanelPage("down");
    } else {
      navigatePageDown();
    }
  } else if (e.key === " ") {
    e.preventDefault();
    if (e.shiftKey) {
      scrollDetailPanelPage("up");
    } else {
      scrollDetailPanelPage("down");
    }
  } else if (e.key === "/") {
    e.preventDefault();
    toggleSearchBar();
  }
});

// View toggle event listener
document
  .getElementById("view-toggle")
  .addEventListener("click", toggleViewState);

// Layout toggle event listener
document
  .getElementById("layout-toggle")
  .addEventListener("click", toggleLayoutState);

// Search toggle event listener
document
  .getElementById("search-toggle")
  .addEventListener("click", toggleSearchBar);

// Refresh button event listener
document
  .getElementById("refresh-button")
  .addEventListener("click", refreshIssues);

// Board selector event listener
document
  .getElementById("board-selector")
  .addEventListener("click", showBoardSelector);

// Help button event listener
document
  .getElementById("help-button")
  .addEventListener("click", showHelpOverlay);

// Stats button event listener
document
  .getElementById("stats")
  .addEventListener("click", showStatsModal);

// Stats modal close button event listener
document
  .getElementById("stats-modal-close")
  .addEventListener("click", hideStatsModal);

// Close stats modal when clicking outside
document
  .getElementById("stats-modal")
  .addEventListener("click", (e) => {
    if (e.target.id === "stats-modal") {
      hideStatsModal();
    }
  });

// Board management functions
async function loadBoards() {
  try {
    const res = await fetch("/api/boards");
    if (res.ok) {
      const data = await res.json();
      availableBoards = data.boards || [];
      updateBoardSelectorText();
    }
  } catch (error) {
    console.error("Error loading boards:", error);
  }
}

function updateBoardSelectorText() {
  const selector = document.getElementById("board-selector");
  if (currentBoard && selector) {
    selector.textContent = `📋 ${currentBoard}`;
  } else if (selector) {
    selector.textContent = "📋 Board";
  }
}

function showBoardSelector() {
  if (availableBoards.length === 0) {
    showNotification("No boards configured", "error");
    return;
  }

  // Remove existing modal if it exists
  const existingModal = document.getElementById("board-modal");
  if (existingModal) {
    existingModal.remove();
  }

  // Create board selection modal
  const modal = document.createElement("div");
  modal.id = "board-modal";
  modal.style.cssText = `
                position: fixed;
                top: 0;
                left: 0;
                width: 100vw;
                height: 100vh;
                background-color: rgba(0, 0, 0, 0.7);
                z-index: 10000;
                display: flex;
                align-items: center;
                justify-content: center;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                animation: fadeIn 0.2s ease;
            `;

  const modalContent = document.createElement("div");
  modalContent.style.cssText = `
                background: #ffffff;
                color: #333333;
                border: 1px solid #e1e4e8;
                border-radius: 8px;
                padding: 1.5rem;
                max-width: 400px;
                max-height: 80vh;
                overflow-y: auto;
                box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3);
                margin: 1rem;
                min-width: 300px;
            `;

  let boardsHtml = `
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; border-bottom: 1px solid #e1e4e8; padding-bottom: 1rem;">
                    <h3 style="margin: 0; color: #0366d6; font-size: 1.1rem;">📋 Select Board</h3>
                    <button id="close-board-modal" style="background: none; border: none; font-size: 1.5rem; cursor: pointer; color: #6a737d; padding: 0.25rem;">&times;</button>
                </div>
                <div style="display: flex; flex-direction: column; gap: 0.5rem;">
            `;

  availableBoards.forEach((board, index) => {
    const isSelected = board.name === currentBoard;
    boardsHtml += `
                    <button class="board-option" data-board-name="${board.name}" style="
                        background: ${isSelected ? "#f1f8ff" : "#ffffff"};
                        border: 1px solid ${isSelected ? "#0366d6" : "#e1e4e8"};
                        border-radius: 6px;
                        padding: 0.75rem;
                        cursor: pointer;
                        text-align: left;
                        transition: all 0.2s ease;
                        color: ${isSelected ? "#0366d6" : "#24292e"};
                    ">
                        <div style="font-weight: 600; margin-bottom: 0.25rem;">${board.name} ${isSelected ? "✓" : ""}</div>
                        <div style="font-size: 0.875rem; color: #6a737d;">${board.description}</div>
                    </button>
                `;
  });

  boardsHtml += "</div>";
  modalContent.innerHTML = boardsHtml;
  modal.appendChild(modalContent);
  document.body.appendChild(modal);

  // Add event listeners
  modal.addEventListener("click", (e) => {
    if (e.target === modal) {
      hideBoardSelector();
    }
  });

  document
    .getElementById("close-board-modal")
    .addEventListener("click", hideBoardSelector);

  // Add click handlers for board options
  modalContent.querySelectorAll(".board-option").forEach((button) => {
    button.addEventListener("click", () => {
      const boardName = button.getAttribute("data-board-name");
      switchToBoard(boardName);
    });

    button.addEventListener("mouseenter", () => {
      if (!button.style.backgroundColor.includes("f1f8ff")) {
        button.style.backgroundColor = "#f6f8fa";
        button.style.borderColor = "#d1d5da";
      }
    });

    button.addEventListener("mouseleave", () => {
      if (!button.style.backgroundColor.includes("f1f8ff")) {
        button.style.backgroundColor = "#ffffff";
        button.style.borderColor = "#e1e4e8";
      }
    });
  });
}

function hideBoardSelector() {
  const modal = document.getElementById("board-modal");
  if (modal) {
    modal.remove();
  }
}

async function switchToBoard(boardName) {
  try {
    hideBoardSelector();
    showNotification(`🔄 Switching to ${boardName}...`, "info");

    const res = await fetch(
      `/api/boards/${encodeURIComponent(boardName)}/switch`,
      {
        method: "POST",
      },
    );

    if (!res.ok) {
      throw new Error(`HTTP ${res.status}`);
    }

    const result = await res.json();
    currentBoard = boardName;
    updateBoardSelectorText();

    // Reload issues
    allIssues = await fetchIssues();
    renderTable(allIssues);
    closeDetail();

    // Save state when board is switched
    saveUIState();

    showNotification(
      `✅ Switched to ${boardName} (${result.issue_count} issues)`,
      "success",
    );
  } catch (error) {
    console.error("Error switching board:", error);
    showNotification(`❌ Failed to switch to ${boardName}`, "error");
  }
}

// Initial load
async function init() {
  // Initialize state management
  initializeViewState();
  initializeLayoutState();
  initializeResizer();
  setupAutoSave();

  await loadConfig(); // Load Jira base URL
  await loadBoards(); // Load available boards

  // Try to detect current board from first board in config or use default
  if (availableBoards.length > 0) {
    currentBoard = availableBoards[0].name;
    updateBoardSelectorText();
  }

  allIssues = await fetchIssues();
  renderTable(allIssues);

  // Restore UI state after initial load
  restoreUIState();

  // Auto-select first issue if no issue is currently selected and issues exist
  setTimeout(() => {
    if (!selectedRow && allIssues.length > 0) {
      const tbody = document.getElementById("issues-tbody");
      const firstRow = tbody.querySelector("tr[data-issue-key]");
      if (firstRow) {
        const issueKey = firstRow.dataset.issueKey;
        selectRow(firstRow, issueKey);
        console.log("Auto-selected first issue:", issueKey);
      }
    }
  }, 500); // Increased timeout to ensure restoreUIState completes
}

init();

// Additional navigation functions for Page Up/Down, Home/End
function navigateToFirstIssue() {
  const tbody = document.getElementById("issues-tbody");
  const firstRow = tbody.querySelector("tr:not(.loading):not(.no-issues)");
  if (firstRow) {
    const keyCell = firstRow.querySelector("td:nth-child(2) a");
    if (keyCell) {
      const issueKey = keyCell.textContent.trim();
      selectRow(firstRow, issueKey);
      firstRow.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  }
}

function navigateToLastIssue() {
  const tbody = document.getElementById("issues-tbody");
  const rows = Array.from(tbody.querySelectorAll("tr")).filter(
    (row) => !row.querySelector(".loading") && !row.querySelector(".no-issues"),
  );
  const lastRow = rows[rows.length - 1];
  if (lastRow) {
    const keyCell = lastRow.querySelector("td:nth-child(2) a");
    if (keyCell) {
      const issueKey = keyCell.textContent.trim();
      selectRow(lastRow, issueKey);
      lastRow.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  }
}

function navigatePageUp() {
  const tbody = document.getElementById("issues-tbody");
  const rows = Array.from(tbody.querySelectorAll("tr")).filter(
    (row) => !row.querySelector(".loading") && !row.querySelector(".no-issues"),
  );

  if (rows.length === 0) return;

  let currentIndex = -1;
  if (selectedRow) {
    currentIndex = rows.findIndex((row) => row === selectedRow);
  }

  // If no selection, start from the end when going up
  if (currentIndex === -1) {
    currentIndex = rows.length;
  }

  // Move up by ~10 rows (or to beginning if less than 10)
  const pageSize = Math.min(10, rows.length);
  let newIndex = Math.max(0, currentIndex - pageSize);

  const newRow = rows[newIndex];
  if (newRow) {
    const keyCell = newRow.querySelector("td:nth-child(2) a");
    if (keyCell) {
      const issueKey = keyCell.textContent.trim();
      selectRow(newRow, issueKey);
      newRow.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  }
}

function navigatePageDown() {
  const tbody = document.getElementById("issues-tbody");
  const rows = Array.from(tbody.querySelectorAll("tr")).filter(
    (row) => !row.querySelector(".loading") && !row.querySelector(".no-issues"),
  );

  if (rows.length === 0) return;

  let currentIndex = -1;
  if (selectedRow) {
    currentIndex = rows.findIndex((row) => row === selectedRow);
  }

  // If no selection, start from the beginning when going down
  if (currentIndex === -1) {
    currentIndex = -1;
  }

  // Move down by ~10 rows (or to end if less than 10)
  const pageSize = Math.min(10, rows.length);
  let newIndex = Math.min(rows.length - 1, currentIndex + pageSize);

  const newRow = rows[newIndex];
  if (newRow) {
    const keyCell = newRow.querySelector("td:nth-child(2) a");
    if (keyCell) {
      const issueKey = keyCell.textContent.trim();
      selectRow(newRow, issueKey);
      newRow.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  }
}

function scrollDetailPanelPage(direction) {
  const detailContent = document.querySelector(".detail-content");
  if (!detailContent) return;

  const containerHeight = detailContent.clientHeight;
  const scrollAmount = containerHeight * 0.8; // Scroll 80% of visible area
  const currentScroll = detailContent.scrollTop;

  if (direction === "down") {
    detailContent.scrollTo({
      top: currentScroll + scrollAmount,
      behavior: "smooth",
    });
  } else {
    detailContent.scrollTo({
      top: Math.max(0, currentScroll - scrollAmount),
      behavior: "smooth",
    });
  }
}

// Label editing functions
let labelEditModal = null;
let labelSelect = null;
let currentEditingIssue = null;

async function editLabels(issueKey, currentLabels) {
  currentEditingIssue = issueKey;

  try {
    // Fetch all available labels
    const response = await fetch("/api/labels");
    const data = await response.json();
    const allLabels = data.labels || [];

    // Show the modal
    showLabelEditModal(issueKey, currentLabels, allLabels);
  } catch (error) {
    console.error("Error fetching labels:", error);
    showNotification("Failed to load labels", "error");
  }
}

function showLabelEditModal(issueKey, currentLabels, allLabels) {
  // Remove existing modal if it exists
  if (labelEditModal) {
    labelEditModal.remove();
  }

  // Create modal
  labelEditModal = document.createElement("div");
  labelEditModal.className = "label-edit-modal";
  labelEditModal.innerHTML = `
                <div class="label-edit-content">
                    <div class="label-edit-header">
                        <h3>Edit Labels - ${issueKey}</h3>
                        <button class="label-edit-close" onclick="closeLabelEditModal()">×</button>
                    </div>
                    <div class="label-select-container">
                        <label for="label-select">Select Labels (type to search, enter to create new):</label>
                        <select id="label-select" multiple placeholder="Type to search or add labels...">
                        </select>
                    </div>
                    <div class="label-actions">
                        <button class="btn btn-secondary" onclick="closeLabelEditModal()">Cancel</button>
                        <button class="btn btn-primary" onclick="saveLabels()">Save Labels</button>
                    </div>
                </div>
            `;

  document.body.appendChild(labelEditModal);

  // Initialize Tom Select
  const selectElement = document.getElementById("label-select");
  labelSelect = new TomSelect(selectElement, {
    create: true,
    createOnBlur: true,
    highlight: true,
    persist: false,
    maxItems: null,
    valueField: "value",
    labelField: "text",
    searchField: ["text"],
    options: allLabels.map((label) => ({ value: label, text: label })),
    items: currentLabels,
    plugins: ["remove_button"],
    render: {
      option: function (data, escape) {
        return "<div>" + escape(data.text) + "</div>";
      },
      item: function (data, escape) {
        return "<div>" + escape(data.text) + "</div>";
      },
    },
    onItemAdd: function () {
      this.close();
    },
    create: function (input) {
      return {
        value: input,
        text: input,
      };
    },
  });

  // Focus on the select
  setTimeout(() => {
    labelSelect.focus();
  }, 100);

  // Close modal on escape
  const escapeHandler = (e) => {
    if (e.key === "Escape") {
      closeLabelEditModal();
      document.removeEventListener("keydown", escapeHandler);
    }
  };
  document.addEventListener("keydown", escapeHandler);

  // Close modal when clicking outside
  labelEditModal.addEventListener("click", (e) => {
    if (e.target === labelEditModal) {
      closeLabelEditModal();
    }
  });
}

function closeLabelEditModal() {
  if (labelEditModal) {
    labelEditModal.remove();
    labelEditModal = null;
  }
  if (labelSelect) {
    labelSelect.destroy();
    labelSelect = null;
  }
  currentEditingIssue = null;
}

async function saveLabels() {
  if (!labelSelect || !currentEditingIssue) {
    return;
  }

  const newLabels = labelSelect.getValue();

  try {
    const response = await fetch(`/api/issue/${currentEditingIssue}/labels`, {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ labels: newLabels }),
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const result = await response.json();
    showNotification(`Labels updated for ${currentEditingIssue}`, "success");

    // Refresh the issue detail to show updated labels
    const issueDetail = await fetchIssueDetail(currentEditingIssue);
    showDetail(currentEditingIssue, issueDetail);

    // Close the modal
    closeLabelEditModal();
  } catch (error) {
    console.error("Error saving labels:", error);
    showNotification("Failed to save labels", "error");
  }
}

function editSelectedIssueTransition() {
  if (!selectedRow) {
    showNotification(
      "No issue selected. Use j/k to navigate or click an issue.",
      "error",
    );
    return;
  }
  const keyCell = selectedRow.querySelector("td:nth-child(2) a");
  if (!keyCell) return;
  const issueKey = keyCell.textContent.trim();

  // Fetch transitions from backend
  fetch(`/api/issue/${issueKey}/transitions`)
    .then((res) => res.json())
    .then((data) => {
      showTransitionModal(issueKey, data.transitions || []);
    })
    .catch((err) => {
      showNotification("Failed to load transitions", "error");
    });
}

function showTransitionModal(issueKey, transitions) {
  // Remove existing modal
  const existing = document.getElementById("transition-modal");
  if (existing) existing.remove();

  // Modal container
  const modal = document.createElement("div");
  modal.id = "transition-modal";
  modal.style.cssText = `
                position: fixed; top:0; left:0; width:100vw; height:100vh; z-index:10001;
                background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center;
            `;

  // Modal content
  const content = document.createElement("div");
  content.style.cssText = `
                background: #fff; border-radius: 8px; padding: 1.5rem; min-width: 400px; max-width: 90vw;
                max-height: 80vh; overflow-y: auto; box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            `;

  content.innerHTML = `
                <h3 style="margin-top:0;">Select Transition for <span style="color:#0366d6;">${issueKey}</span></h3>
                <input id="transition-search" type="text" placeholder="Type to filter..." style="width:100%;margin-bottom:1rem;padding:0.5rem;">
                <table id="transition-table" style="width:100%;border-collapse:collapse;">
                    <thead>
                        <tr>
                            <th style="padding:0.5rem;border-bottom:1px solid #eee;text-align:left;">Name</th>
                            <th style="padding:0.5rem;border-bottom:1px solid #eee;text-align:left;">To Status</th>
                            <th style="padding:0.5rem;border-bottom:1px solid #eee;text-align:left;">Description</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${transitions
      .map(
        (tr) => `
                            <tr tabindex="0" data-id="${tr.id}" style="cursor:pointer;" onmouseenter="this.style.backgroundColor='#f8f9fa'" onmouseleave="this.style.backgroundColor=''">
                                <td style="padding:0.5rem;border-bottom:1px solid #f0f0f0;font-weight:500;">${tr.name}</td>
                                <td style="padding:0.5rem;border-bottom:1px solid #f0f0f0;"><span style="background:#e3f2fd;color:#1976d2;padding:0.2rem 0.5rem;border-radius:4px;font-size:0.8rem;">${tr.to.name}</span></td>
                                <td style="padding:0.5rem;border-bottom:1px solid #f0f0f0;color:#666;">${tr.to.description || "No description"}</td>
                            </tr>
                        `,
      )
      .join("")}
                    </tbody>
                </table>
                <div style="margin-top:1rem;text-align:right;">
                    <button id="close-transition-modal" style="padding:0.5rem 1rem;background:#6c757d;color:white;border:none;border-radius:4px;cursor:pointer;">Cancel</button>
                </div>
            `;

  modal.appendChild(content);
  document.body.appendChild(modal);

  // FZF-style filtering
  const searchInput = content.querySelector("#transition-search");
  const tableRows = Array.from(content.querySelectorAll("tbody tr"));
  searchInput.addEventListener("input", function () {
    const q = this.value.toLowerCase();
    tableRows.forEach((row) => {
      const text = row.textContent.toLowerCase();
      row.style.display = text.includes(q) ? "" : "none";
    });
  });

  // Keyboard navigation and selection
  let selectedIdx = 0;

  // Initialize selection for visible rows
  const visibleRows = tableRows.filter((row) => row.style.display !== "none");
  function updateVisibleSelection(visibleRows, idx) {
    tableRows.forEach((row) => {
      row.style.background = "";
    });
    if (visibleRows[idx]) {
      visibleRows[idx].style.background = "#eaf5ff";
    }
  }
  updateVisibleSelection(visibleRows, selectedIdx);

  searchInput.addEventListener("keydown", function (e) {
    const visibleRows = tableRows.filter((row) => row.style.display !== "none");
    if (visibleRows.length === 0) return;

    if (e.key === "ArrowDown") {
      selectedIdx = (selectedIdx + 1) % visibleRows.length;
      updateVisibleSelection(visibleRows, selectedIdx);
      e.preventDefault();
    } else if (e.key === "ArrowUp") {
      selectedIdx = (selectedIdx - 1 + visibleRows.length) % visibleRows.length;
      updateVisibleSelection(visibleRows, selectedIdx);
      e.preventDefault();
    } else if (e.key === "Enter") {
      if (visibleRows[selectedIdx]) {
        visibleRows[selectedIdx].click();
      }
      e.preventDefault();
    } else if (e.key === "Escape") {
      modal.remove();
      e.preventDefault();
    }
  });

  function updateVisibleSelection(visibleRows, idx) {
    tableRows.forEach((row) => {
      row.style.background = "";
    });
    if (visibleRows[idx]) {
      visibleRows[idx].style.background = "#eaf5ff";
    }
  }

  tableRows.forEach((row, i) => {
    row.addEventListener("click", function () {
      const transitionId = this.dataset.id;
      applyTransition(issueKey, transitionId);
      modal.remove();
    });
    row.addEventListener("mouseenter", function () {
      const visibleRows = tableRows.filter(
        (row) => row.style.display !== "none",
      );
      selectedIdx = visibleRows.indexOf(this);
      updateVisibleSelection(visibleRows, selectedIdx);
    });
  });

  // Close modal
  content.querySelector("#close-transition-modal").onclick = () =>
    modal.remove();
  modal.onclick = (e) => {
    if (e.target === modal) modal.remove();
  };
  searchInput.focus();
}

function applyTransition(issueKey, transitionId) {
  fetch(`/api/issue/${issueKey}/transitions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ transition_id: transitionId }),
  })
    .then((res) => {
      if (!res.ok) throw new Error("Failed to apply transition");
      return res.json();
    })
    .then((data) => {
      showNotification("Transition applied successfully", "success");
      // Refresh the issue detail to show updated status
      if (selectedRow && selectedRow.dataset.issueKey === issueKey) {
        fetchIssueDetail(issueKey).then((detail) => {
          showDetail(issueKey, detail);
        });
      }
      // Optionally refresh the issues list to show updated status
      refreshIssues();
    })
    .catch(() => showNotification("Failed to apply transition", "error"));
}

// Resizer functionality
function initializeResizer() {
  const resizer = document.getElementById("resizer");
  const issuesPanel = document.querySelector(".issues-panel");
  const detailPanel = document.querySelector(".detail-panel");
  const mainContent = document.querySelector(".main-content");

  if (!resizer || !issuesPanel || !detailPanel || !mainContent) return;

  let isResizing = false;
  let startX = 0;
  let startY = 0;
  let startLeftWidth = 0;
  let startTopHeight = 0;

  // Store panel size preferences in localStorage
  const PANEL_WIDTH_KEY = "jayrah-issues-panel-width";
  const PANEL_HEIGHT_KEY = "jayrah-issues-panel-height";

  // Load saved size preferences
  const savedWidth = localStorage.getItem(PANEL_WIDTH_KEY);
  const savedHeight = localStorage.getItem(PANEL_HEIGHT_KEY);

  if (savedWidth) {
    const width = parseFloat(savedWidth);
    if (width >= 20 && width <= 80) {
      // Ensure reasonable bounds
      issuesPanel.style.width = `${width}%`;
    }
  }

  if (savedHeight) {
    const height = parseFloat(savedHeight);
    if (height >= 20 && height <= 80) {
      // Ensure reasonable bounds
      issuesPanel.style.height = `${height}%`;
    }
  }

  resizer.addEventListener("mousedown", initResize);

  function initResize(e) {
    e.preventDefault();
    isResizing = true;
    startX = e.clientX;
    startY = e.clientY;
    startLeftWidth = issuesPanel.offsetWidth;
    startTopHeight = issuesPanel.offsetHeight;

    resizer.classList.add("resizing");
    document.body.style.userSelect = "none";

    // Set cursor based on layout
    const isVertical = document
      .getElementById("view-container")
      .classList.contains("layout-vertical");
    document.body.style.cursor = isVertical ? "row-resize" : "col-resize";

    document.addEventListener("mousemove", doResize);
    document.addEventListener("mouseup", stopResize);
  }

  function doResize(e) {
    if (!isResizing) return;

    const isVertical = document
      .getElementById("view-container")
      .classList.contains("layout-vertical");

    if (isVertical) {
      // Vertical layout - resize height
      const containerHeight = mainContent.offsetHeight;
      const resizerHeight = resizer.offsetHeight;
      const deltaY = e.clientY - startY;
      const newTopHeight = startTopHeight + deltaY;

      // Calculate percentages
      const minHeight = containerHeight * 0.2; // 20% minimum
      const maxHeight = containerHeight * 0.8; // 80% maximum

      if (newTopHeight >= minHeight && newTopHeight <= maxHeight) {
        const topPercentage = (newTopHeight / containerHeight) * 100;
        issuesPanel.style.height = `${topPercentage}%`;

        // Ensure detail panel takes remaining space
        const remainingPercentage = 100 - topPercentage;
        detailPanel.style.height = `${remainingPercentage}%`;

        // Save the preference
        localStorage.setItem(PANEL_HEIGHT_KEY, topPercentage.toString());
      }
    } else {
      // Horizontal layout - resize width
      const containerWidth = mainContent.offsetWidth;
      const resizerWidth = resizer.offsetWidth;
      const deltaX = e.clientX - startX;
      const newLeftWidth = startLeftWidth + deltaX;

      // Calculate percentages
      const minWidth = containerWidth * 0.2; // 20% minimum
      const maxWidth = containerWidth * 0.8; // 80% maximum

      if (newLeftWidth >= minWidth && newLeftWidth <= maxWidth) {
        const leftPercentage = (newLeftWidth / containerWidth) * 100;
        issuesPanel.style.width = `${leftPercentage}%`;

        // Save the preference
        localStorage.setItem(PANEL_WIDTH_KEY, leftPercentage.toString());
      }
    }
  }

  function stopResize() {
    if (!isResizing) return;

    isResizing = false;
    resizer.classList.remove("resizing");
    document.body.style.cursor = "";
    document.body.style.userSelect = "";

    document.removeEventListener("mousemove", doResize);
    document.removeEventListener("mouseup", stopResize);
  }

  // Handle double-click to reset to 50/50
  resizer.addEventListener("dblclick", () => {
    const isVertical = document
      .getElementById("view-container")
      .classList.contains("layout-vertical");
    if (isVertical) {
      issuesPanel.style.height = "50%";
      detailPanel.style.height = "50%";
      localStorage.setItem(PANEL_HEIGHT_KEY, "50");
    } else {
      issuesPanel.style.width = "50%";
      localStorage.setItem(PANEL_WIDTH_KEY, "50");
    }
  });
}

// Reset panel sizes when switching layouts
function resetPanelSizes() {
  const issuesPanel = document.querySelector(".issues-panel");
  const detailPanel = document.querySelector(".detail-panel");
  if (!issuesPanel || !detailPanel) return;

  const isVertical = document
    .getElementById("view-container")
    .classList.contains("layout-vertical");

  if (isVertical) {
    // In vertical layout, remove any width styles and set default heights
    issuesPanel.style.width = "";
    issuesPanel.style.height = "50%";
    detailPanel.style.width = "";
    detailPanel.style.height = "50%";
  } else {
    // In horizontal layout, remove any height styles and set default width
    issuesPanel.style.height = "";
    issuesPanel.style.width = "50%";
    detailPanel.style.height = "";
    detailPanel.style.width = "";  // detail panel uses flex: 1
  }

  console.log("Panel sizes reset for layout:", isVertical ? "vertical" : "horizontal");
}

// Statistics functionality
async function fetchStats() {
  try {
    const response = await fetch("/api/stats");
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    return await response.json();
  } catch (error) {
    console.error("Error fetching stats:", error);
    return null;
  }
}

function showStatsModal() {
  const modal = document.getElementById("stats-modal");
  const modalBody = document.getElementById("stats-modal-body");

  // Show modal
  modal.style.display = "flex";

  // Load statistics
  modalBody.innerHTML = '<div class="loading">Loading statistics...</div>';

  fetchStats().then(stats => {
    if (!stats) {
      modalBody.innerHTML = '<div class="error">Failed to load statistics.</div>';
      return;
    }

    modalBody.innerHTML = renderStatsContent(stats);
  });
}

function hideStatsModal() {
  const modal = document.getElementById("stats-modal");
  modal.style.display = "none";
}

function renderStatsContent(stats) {
  const {
    total_issues,
    issue_types,
    statuses,
    assignees,
    priorities,
    components,
    labels,
    created_this_week,
    updated_this_week,
    resolution_stats
  } = stats;

  // Helper function to render a stats section
  function renderStatsSection(title, emoji, data, maxItems = 10) {
    if (!data || Object.keys(data).length === 0) {
      return `
        <div class="stats-section">
          <h3>${emoji} ${title}</h3>
          <p style="color: var(--text-muted); text-align: center; padding: 1rem;">No data available</p>
        </div>
      `;
    }

    const items = Object.entries(data)
      .slice(0, maxItems)
      .map(([name, count]) => `
        <li>
          <span class="stats-name">${name}</span>
          <span class="stats-count">${count}</span>
        </li>
      `)
      .join('');

    const hasMore = Object.keys(data).length > maxItems;
    const moreText = hasMore ? `<li style="text-align: center; color: var(--text-muted); font-style: italic;">... and ${Object.keys(data).length - maxItems} more</li>` : '';

    return `
      <div class="stats-section">
        <h3>${emoji} ${title}</h3>
        <ul class="stats-list">
          ${items}
          ${moreText}
        </ul>
      </div>
    `;
  }

  return `
    <div class="stats-summary">
      <h3>📊 Board Overview</h3>
      <div class="stats-highlight">
        <div class="highlight-item">
          <div class="highlight-number">${total_issues}</div>
          <div class="highlight-label">Total Issues</div>
        </div>
        <div class="highlight-item">
          <div class="highlight-number">${created_this_week}</div>
          <div class="highlight-label">Created This Week</div>
        </div>
        <div class="highlight-item">
          <div class="highlight-number">${updated_this_week}</div>
          <div class="highlight-label">Updated This Week</div>
        </div>
        <div class="highlight-item">
          <div class="highlight-number">${Object.keys(statuses).length}</div>
          <div class="highlight-label">Unique Statuses</div>
        </div>
      </div>
    </div>
    
    <div class="stats-grid">
      ${renderStatsSection('Issue Types', '🎯', issue_types)}
      ${renderStatsSection('Statuses', '📈', statuses)}
      ${renderStatsSection('Assignees', '👥', assignees, 8)}
      ${renderStatsSection('Priorities', '🔥', priorities)}
      ${renderStatsSection('Components', '🧩', components, 8)}
      ${renderStatsSection('Resolution Status', '✅', resolution_stats)}
    </div>
  `;
}

// Custom field editing functionality
function editCustomField(fieldId, fieldName, fieldType, currentValue) {
  // Store current issue key for the API call
  const issueKey = window.currentIssueKey;
  if (!issueKey) {
    console.error('No current issue key available');
    return;
  }
  
  showCustomFieldEditModal(fieldId, fieldName, fieldType, currentValue, issueKey);
}

function showCustomFieldEditModal(fieldId, fieldName, fieldType, currentValue, issueKey) {
  // Remove existing modal if it exists
  const existingModal = document.getElementById('custom-field-modal');
  if (existingModal) {
    existingModal.remove();
  }

  // Create modal HTML
  const modalHtml = `
    <div id="custom-field-modal" class="custom-field-edit-modal">
      <div class="custom-field-edit-content">
        <div class="custom-field-edit-header">
          <h3>Edit ${fieldName}</h3>
          <button class="custom-field-edit-close" onclick="hideCustomFieldModal()">&times;</button>
        </div>
        <div class="custom-field-form">
          <form id="custom-field-form">
            <div class="custom-field-group">
              <label for="custom-field-input" class="custom-field-label">${fieldName}:</label>
              ${renderCustomFieldInput(fieldType, currentValue)}
            </div>
            <div class="custom-field-buttons">
              <button type="button" class="custom-field-save" onclick="saveCustomField('${fieldId}', '${issueKey}')">Save</button>
              <button type="button" class="custom-field-cancel" onclick="hideCustomFieldModal()">Cancel</button>
            </div>
          </form>
        </div>
      </div>
    </div>
  `;

  // Add modal to body
  document.body.insertAdjacentHTML('beforeend', modalHtml);
  
  // Show modal
  const modal = document.getElementById('custom-field-modal');
  modal.style.display = 'flex';
  
  // Add click-outside-to-close event listener
  modal.addEventListener('click', (e) => {
    if (e.target.id === 'custom-field-modal') {
      hideCustomFieldModal();
    }
  });
  
  // Focus on input
  const input = modal.querySelector('#custom-field-input');
  if (input) {
    input.focus();
    if (input.type === 'text' || input.tagName === 'TEXTAREA') {
      input.select();
    }
  }
}

function renderCustomFieldInput(fieldType, currentValue) {
  // For HTML attributes, we need different escaping than for JavaScript strings
  const htmlEscapedValue = currentValue
    .replace(/&/g, '&amp;')     // Escape ampersands first
    .replace(/"/g, '&quot;')     // Escape double quotes for HTML attributes
    .replace(/'/g, '&#39;')      // Escape single quotes for HTML attributes
    .replace(/</g, '&lt;')       // Escape less-than signs
    .replace(/>/g, '&gt;');      // Escape greater-than signs
  
  switch (fieldType) {
    case 'text':
      return `<textarea id="custom-field-input" class="custom-field-textarea" rows="4" cols="50">${htmlEscapedValue}</textarea>`;
    case 'url':
      return `<input type="url" id="custom-field-input" class="custom-field-input" value="${htmlEscapedValue}" placeholder="https://example.com">`;
    case 'email':
      return `<input type="email" id="custom-field-input" class="custom-field-input" value="${htmlEscapedValue}" placeholder="user@example.com">`;
    case 'number':
      return `<input type="number" id="custom-field-input" class="custom-field-input" value="${htmlEscapedValue}">`;
    case 'date':
      return `<input type="date" id="custom-field-input" class="custom-field-input" value="${htmlEscapedValue}">`;
    case 'datetime':
      return `<input type="datetime-local" id="custom-field-input" class="custom-field-input" value="${htmlEscapedValue}">`;
    default:
      return `<input type="text" id="custom-field-input" class="custom-field-input" value="${htmlEscapedValue}">`;
  }
}

function hideCustomFieldModal() {
  const modal = document.getElementById('custom-field-modal');
  if (modal) {
    modal.remove();
  }
}

async function saveCustomField(fieldId, issueKey) {
  const input = document.getElementById('custom-field-input');
  if (!input) {
    console.error('Custom field input not found');
    return;
  }

  const newValue = input.value;
  
  // Get the field type from the input element or default to string
  let fieldType = 'string';
  if (input.tagName === 'TEXTAREA') {
    fieldType = 'text';
  } else if (input.type === 'url') {
    fieldType = 'url';
  } else if (input.type === 'email') {
    fieldType = 'email';
  } else if (input.type === 'number') {
    fieldType = 'number';
  } else if (input.type === 'date') {
    fieldType = 'date';
  } else if (input.type === 'datetime-local') {
    fieldType = 'datetime';
  }
  
  try {
    // Show loading feedback
    const saveButton = document.querySelector('#custom-field-modal .custom-field-save');
    const originalText = saveButton.textContent;
    saveButton.textContent = 'Saving...';
    saveButton.disabled = true;

    const response = await fetch(`/api/issue/${issueKey}/customfield`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        field_id: fieldId,
        value: newValue,
        type: fieldType
      })
    });

    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.error || `HTTP error! status: ${response.status}`);
    }

    const result = await response.json();
    console.log('Custom field updated successfully:', result);
    
    // Hide modal
    hideCustomFieldModal();
    
    // Refresh the current issue to show the updated value
    if (window.currentIssueKey) {
      const updatedDetail = await fetchIssueDetail(window.currentIssueKey);
      showDetail(window.currentIssueKey, updatedDetail);
    }
    
    // Show success message
    showNotification('Custom field updated successfully!', 'success');
    
  } catch (error) {
    console.error('Error updating custom field:', error);
    showNotification(`Error updating custom field: ${error.message}`, 'error');
    
    // Restore button state
    const saveButton = document.querySelector('#custom-field-modal .custom-field-save');
    if (saveButton) {
      saveButton.textContent = originalText;
      saveButton.disabled = false;
    }
  }
}
