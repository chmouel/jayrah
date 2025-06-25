        let allIssues = [];
        let selectedRow = null;
        let jiraBaseUrl = null;
        let availableBoards = [];
        let currentBoard = null;

        // Layout state management
        const LAYOUT_STATES = {
            HORIZONTAL: 'layout-horizontal',
            VERTICAL: 'layout-vertical'
        };

        let currentLayoutState = LAYOUT_STATES.HORIZONTAL;

        // View state management
        const VIEW_STATES = {
            BOTH: 'view-both',
            LIST_ONLY: 'view-list-only',
            DETAILS_ONLY: 'view-details-only'
        };

        const VIEW_ICONS = {
            [VIEW_STATES.BOTH]: "/static/icons/view-both.svg",
            [VIEW_STATES.LIST_ONLY]: "/static/icons/view-list.svg",
            [VIEW_STATES.DETAILS_ONLY]: "/static/icons/view-details.svg"
        };

        const VIEW_TITLES = {
            [VIEW_STATES.BOTH]: 'Showing both panels - click or press T to show list only',
            [VIEW_STATES.LIST_ONLY]: 'Showing list only - click or press T to show details only',
            [VIEW_STATES.DETAILS_ONLY]: 'Showing details only - click or press T to show both panels'
        };

        const LAYOUT_ICONS = {
            [LAYOUT_STATES.HORIZONTAL]: "/static/icons/layout-h.svg",
            [LAYOUT_STATES.VERTICAL]: "/static/icons/layout-v.svg"
        };

        const LAYOUT_TITLES = {
            [LAYOUT_STATES.HORIZONTAL]: 'Layout: horizontal (side by side) - click or press V to switch to vertical',
            [LAYOUT_STATES.VERTICAL]: 'Layout: vertical (top/bottom) - click or press V to switch to horizontal'
        };

        let currentViewState = VIEW_STATES.BOTH;

        // Cookie-based state management
        const STATE_COOKIES = {
            LAYOUT: 'jayrah_layout_state',
            VIEW: 'jayrah_view_state', 
            BOARD: 'jayrah_current_board',
            SEARCH_VISIBLE: 'jayrah_search_visible',
            SEARCH_QUERY: 'jayrah_search_query',
            SELECTED_ISSUE: 'jayrah_selected_issue'
        };

        // Cookie utility functions
        function setCookie(name, value, days = 30) {
            const expires = new Date();
            expires.setTime(expires.getTime() + (days * 24 * 60 * 60 * 1000));
            document.cookie = `${name}=${encodeURIComponent(value)}; expires=${expires.toUTCString()}; path=/; SameSite=Lax`;
        }

        function getCookie(name) {
            const nameEQ = name + "=";
            const ca = document.cookie.split(';');
            for (let i = 0; i < ca.length; i++) {
                let c = ca[i];
                while (c.charAt(0) === ' ') c = c.substring(1, c.length);
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
            
            const searchContainer = document.getElementById('search-container');
            if (searchContainer) {
                setCookie(STATE_COOKIES.SEARCH_VISIBLE, searchContainer.classList.contains('visible'));
            }
            
            const searchInput = document.getElementById('search');
            if (searchInput && searchInput.value.trim()) {
                setCookie(STATE_COOKIES.SEARCH_QUERY, searchInput.value.trim());
            } else {
                deleteCookie(STATE_COOKIES.SEARCH_QUERY);
            }
            
            if (selectedRow && selectedRow.dataset.issueKey) {
                setCookie(STATE_COOKIES.SELECTED_ISSUE, selectedRow.dataset.issueKey);
            } else {
                deleteCookie(STATE_COOKIES.SELECTED_ISSUE);
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
            if (searchVisible === 'true') {
                setTimeout(() => {
                    const searchContainer = document.getElementById('search-container');
                    if (searchContainer && !searchContainer.classList.contains('visible')) {
                        searchContainer.classList.add('visible');
                        const searchInput = document.getElementById('search');
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
                    const searchInput = document.getElementById('search');
                    if (searchInput) {
                        searchInput.value = savedQuery;
                        // Trigger search with saved query
                        searchIssues();
                    }
                }, 200);
            }
            
            // Restore selected issue (will be applied when issues are loaded)
            const savedSelectedIssue = getCookie(STATE_COOKIES.SELECTED_ISSUE);
            if (savedSelectedIssue) {
                setTimeout(() => {
                    restoreSelectedIssue(savedSelectedIssue);
                }, 300);
            }
        }
        
        function restoreSelectedIssue(issueKey) {
            const tbody = document.getElementById('issues-tbody');
            if (!tbody) return;
            
            const rows = tbody.querySelectorAll('tr[data-issue-key]');
            for (const row of rows) {
                if (row.dataset.issueKey === issueKey) {
                    selectRow(row);
                    // Scroll the row into view
                    row.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    break;
                }
            }
        }

        // Auto-save state on changes
        function setupAutoSave() {
            // Save state periodically
            setInterval(saveUIState, 5000); // Every 5 seconds
            
            // Save on page unload
            window.addEventListener('beforeunload', saveUIState);
            
            // Save on visibility change (tab switch, etc.)
            document.addEventListener('visibilitychange', () => {
                if (document.hidden) {
                    saveUIState();
                }
            });
        }

        // Initialize layout state from cookies or default (legacy function - replaced by newer version)
        function initializeLayoutState_old() {
            const savedLayout = getCookie(STATE_COOKIES.LAYOUT);
            if (savedLayout && Object.values(LAYOUT_STATES).includes(savedLayout)) {
                currentLayoutState = savedLayout;
            }

            const container = document.getElementById('view-container');
            const layoutToggleBtn = document.getElementById('layout-toggle');

            container.classList.add(currentLayoutState);

            // Initialize button icon and title
            if (layoutToggleBtn) {
                layoutToggleBtn.innerHTML = `<img src="${LAYOUT_ICONS[currentLayoutState]}" alt="">`;
                layoutToggleBtn.title = LAYOUT_TITLES[currentLayoutState];
            }
        }

        // Toggle view state
        function toggleViewState() {
            const container = document.getElementById('view-container');
            const toggleBtn = document.getElementById('view-toggle');

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
            toggleBtn.innerHTML = `<img src="${VIEW_ICONS[currentViewState]}" alt="">`;
            toggleBtn.title = VIEW_TITLES[currentViewState];

            // Save state to cookies
            saveUIState();
        }        // Initialize view state from cookies or default
        function initializeViewState() {
            const savedState = getCookie(STATE_COOKIES.VIEW);
            if (savedState && Object.values(VIEW_STATES).includes(savedState)) {
                currentViewState = savedState;
            }

            const container = document.getElementById('view-container');
            const toggleBtn = document.getElementById('view-toggle');

            container.classList.add(currentViewState);
            toggleBtn.innerHTML = `<img src="${VIEW_ICONS[currentViewState]}" alt="">`;
            toggleBtn.title = VIEW_TITLES[currentViewState];
        }

        // Navigation functions for keyboard shortcuts
        function navigateIssueList(direction = 'down') {
            const tbody = document.getElementById('issues-tbody');
            const rows = Array.from(tbody.querySelectorAll('tr')).filter(row =>
                !row.querySelector('.loading') && !row.querySelector('.no-issues')
            );

            if (rows.length === 0) return;

            let currentIndex = -1;
            if (selectedRow) {
                currentIndex = rows.findIndex(row => row === selectedRow);
            }

            let newIndex;
            if (direction === 'down') {
                newIndex = currentIndex + 1;
                if (newIndex >= rows.length) newIndex = 0; // Wrap to top
            } else {
                newIndex = currentIndex - 1;
                if (newIndex < 0) newIndex = rows.length - 1; // Wrap to bottom
            }

            const newRow = rows[newIndex];
            if (newRow) {
                // Extract issue key from the row
                const keyCell = newRow.querySelector('td:nth-child(2) a');
                if (keyCell) {
                    const issueKey = keyCell.textContent.trim();
                    selectRow(newRow, issueKey);

                    // Scroll row into view
                    newRow.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                }
            }
        }

        function scrollDetailPanel(direction) {
            const detailContent = document.querySelector('.detail-content');
            if (!detailContent) return;

            const scrollAmount = 100; // pixels to scroll
            const currentScroll = detailContent.scrollTop;

            if (direction === 'down') {
                detailContent.scrollTo({
                    top: currentScroll + scrollAmount,
                    behavior: 'smooth'
                });
            } else {
                detailContent.scrollTo({
                    top: currentScroll - scrollAmount,
                    behavior: 'smooth'
                });
            }
        }

        function openSelectedIssueInNewTab() {
            if (!selectedRow) {
                // If no row selected, try to select the first one
                const tbody = document.getElementById('issues-tbody');
                const firstRow = tbody.querySelector('tr:not(.loading):not(.no-issues)');
                if (firstRow) {
                    const keyCell = firstRow.querySelector('td:nth-child(2) a');
                    if (keyCell) {
                        const issueKey = keyCell.textContent.trim();
                        selectRow(firstRow, issueKey);
                    }
                }
            }

            if (selectedRow) {
                const keyCell = selectedRow.querySelector('td:nth-child(2) a');
                if (keyCell) {
                    const issueKey = keyCell.textContent.trim();
                    const jiraBaseUrl = getJiraBaseUrl();
                    if (jiraBaseUrl) {
                        const issueUrl = `${jiraBaseUrl}/browse/${issueKey}`;
                        window.open(issueUrl, '_blank');
                        showNotification(`Opened ${issueKey} in new tab`);
                    } else {
                        showNotification('Error: Jira base URL not configured', 'error');
                    }
                }
            } else {
                showNotification('No issue selected', 'error');
            }
        }

        function yankIssueUrl() {
            if (!selectedRow) {
                // If no row selected, try to select the first one
                const tbody = document.getElementById('issues-tbody');
                const firstRow = tbody.querySelector('tr:not(.loading):not(.no-issues)');
                if (firstRow) {
                    const keyCell = firstRow.querySelector('td:nth-child(2) a');
                    if (keyCell) {
                        const issueKey = keyCell.textContent.trim();
                        selectRow(firstRow, issueKey);
                    }
                }
            }

            if (selectedRow) {
                const keyCell = selectedRow.querySelector('td:nth-child(2) a');
                if (keyCell) {
                    const issueKey = keyCell.textContent.trim();
                    const jiraBaseUrl = getJiraBaseUrl();
                    if (jiraBaseUrl) {
                        const issueUrl = `${jiraBaseUrl}/browse/${issueKey}`;
                        navigator.clipboard.writeText(issueUrl).then(() => {
                            showNotification(`Copied ${issueKey} URL to clipboard`);
                        }).catch(() => {
                            showNotification(`Failed to copy URL for ${issueKey}`, 'error');
                        });
                    } else {
                        // Fallback: copy just the issue key
                        navigator.clipboard.writeText(issueKey).then(() => {
                            showNotification(`Copied issue key ${issueKey} to clipboard`);
                        }).catch(() => {
                            showNotification(`Failed to copy issue key ${issueKey}`, 'error');
                        });
                    }
                }
            } else {
                showNotification('No issue selected', 'error');
            }
        }

        function editSelectedIssueLabels() {
            if (!selectedRow) {
                // If no row selected, try to select the first one
                const tbody = document.getElementById('issues-tbody');
                const firstRow = tbody.querySelector('tr:not(.loading):not(.no-issues)');
                if (firstRow) {
                    const keyCell = firstRow.querySelector('td:nth-child(2) a');
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
                const keyCell = selectedRow.querySelector('td:nth-child(2) a');
                if (keyCell) {
                    const issueKey = keyCell.textContent.trim();

                    // Get current labels from the detail panel if it exists
                    const detailPanel = document.getElementById('detail-panel');
                    const labelTags = detailPanel.querySelectorAll('.label-tag');
                    const currentLabels = Array.from(labelTags).map(tag => tag.textContent.trim());

                    editLabels(issueKey, currentLabels);
                }
            } else {
                showNotification('No issue selected. Use j/k to navigate or click an issue.', 'error');
            }
        }

        function showHelpOverlay() {
            // Remove existing overlay if it exists
            const existingOverlay = document.getElementById('help-overlay');
            if (existingOverlay) {
                existingOverlay.remove();
            }

            // Create new help overlay
            const overlay = document.createElement('div');
            overlay.id = 'help-overlay';
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

            const helpContent = document.createElement('div');
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
                        <li style="margin-bottom: 0;">All shortcuts work except when typing in search box</li>
                    </ul>
                </div>
            `;

            overlay.appendChild(helpContent);
            document.body.appendChild(overlay);

            // Close on click outside or close button
            overlay.addEventListener('click', (e) => {
                if (e.target === overlay) {
                    hideHelpOverlay();
                }
            });

            const closeBtn = helpContent.querySelector('#close-help');
            if (closeBtn) {
                closeBtn.addEventListener('click', hideHelpOverlay);
            }
        }

        function hideHelpOverlay() {
            const overlay = document.getElementById('help-overlay');
            if (overlay) {
                overlay.remove();
            }
        }

        function openIssueInTab(issueKey) {
            const jiraBaseUrl = getJiraBaseUrl();
            if (jiraBaseUrl) {
                const issueUrl = `${jiraBaseUrl}/browse/${issueKey}`;
                window.open(issueUrl, '_blank');
                showNotification(`Opened ${issueKey} in new tab`);
            } else {
                showNotification('Error: Jira base URL not configured', 'error');
            }
        }

        function getJiraBaseUrl() {
            return jiraBaseUrl;
        }

        async function loadConfig() {
            try {
                const res = await fetch('/api/config');
                if (res.ok) {
                    const config = await res.json();
                    jiraBaseUrl = config.jira_base_url;
                }
            } catch (error) {
                console.error('Error loading config:', error);
            }
        }

        function showNotification(message, type = 'success') {
            // Create a simple notification
            const notification = document.createElement('div');
            let bgColor = 'var(--primary-color)';
            if (type === 'success') {
                bgColor = 'var(--success-color)';
            } else if (type === 'error') {
                bgColor = '#dc3545'; // Red for errors
            } else if (type === 'info') {
                bgColor = 'var(--primary-color)'; // Blue for info
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
            if (!text) return '';

            // Handle different text formats
            if (typeof text === 'object') {
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
            markdown = markdown.replace(/^h([1-6])\.\s+(.+)$/gm, (match, level, content) => {
                return '#'.repeat(parseInt(level)) + ' ' + content;
            });

            // Bold: *text* -> **text**
            markdown = markdown.replace(/\*([^*]+)\*/g, '**$1**');

            // Italic: _text_ -> *text*
            markdown = markdown.replace(/_([^_]+)_/g, '*$1*');

            // Code blocks: {code} -> ```
            markdown = markdown.replace(/\{code(?::([^}]*))?\}([\s\S]*?)\{code\}/g, (match, lang, code) => {
                return '```' + (lang || '') + '\n' + code.trim() + '\n```';
            });

            // Inline code: {{text}} -> `text`
            markdown = markdown.replace(/\{\{([^}]+)\}\}/g, '`$1`');

            // Links: [text|url] -> [text](url)
            markdown = markdown.replace(/\[([^|\]]+)\|([^\]]+)\]/g, '[$1]($2)');

            // Lists: * item -> - item (already compatible)
            // Numbers: # item -> 1. item
            markdown = markdown.replace(/^#\s+(.+)$/gm, '1. $1');

            // Line breaks: Convert \r\n or \n to proper breaks
            markdown = markdown.replace(/\r\n/g, '\n');

            return markdown;
        }

        // Extract text from Atlassian Document Format (ADF)
        function extractTextFromADF(adf) {
            if (!adf || typeof adf !== 'object') return '';

            let text = '';

            if (adf.type === 'text') {
                text = adf.text || '';
                // Apply marks if present
                if (adf.marks) {
                    adf.marks.forEach(mark => {
                        if (mark.type === 'strong') text = `**${text}**`;
                        if (mark.type === 'em') text = `*${text}*`;
                        if (mark.type === 'code') text = `\`${text}\``;
                        if (mark.type === 'link') text = `[${text}](${mark.attrs?.href || ''})`;
                    });
                }
            } else if (adf.type === 'paragraph') {
                if (adf.content) {
                    text = adf.content.map(extractTextFromADF).join('') + '\n\n';
                }
            } else if (adf.type === 'heading') {
                const level = adf.attrs?.level || 1;
                if (adf.content) {
                    text = '#'.repeat(level) + ' ' + adf.content.map(extractTextFromADF).join('') + '\n\n';
                }
            } else if (adf.type === 'codeBlock') {
                const lang = adf.attrs?.language || '';
                if (adf.content) {
                    text = '```' + lang + '\n' + adf.content.map(extractTextFromADF).join('') + '\n```\n\n';
                }
            } else if (adf.type === 'bulletList' || adf.type === 'orderedList') {
                if (adf.content) {
                    text = adf.content.map(item => {
                        const prefix = adf.type === 'bulletList' ? '- ' : '1. ';
                        return prefix + extractTextFromADF(item);
                    }).join('') + '\n';
                }
            } else if (adf.type === 'listItem') {
                if (adf.content) {
                    text = adf.content.map(extractTextFromADF).join('') + '\n';
                }
            } else if (adf.content) {
                // Recursively process content array
                text = adf.content.map(extractTextFromADF).join('');
            }

            return text;
        }

        // Convert markdown to HTML
        function markdownToHtml(markdown) {
            if (!markdown) return '';
            return marked.parse(markdown);
        }

        async function fetchIssues(q = "") {
            try {
                const url = q ? `/api/issues?q=${encodeURIComponent(q)}` : "/api/issues";
                const res = await fetch(url);
                if (!res.ok) throw new Error(`HTTP ${res.status}`);
                return await res.json();
            } catch (error) {
                console.error('Error fetching issues:', error);
                return [];
            }
        }

        async function refreshIssues() {
            try {
                // Get current search query if any
                const searchInput = document.getElementById('search');
                const query = searchInput ? searchInput.value.trim() : '';
                
                // Fetch issues with current search query
                allIssues = await fetchIssues(query);
                
                // Re-render the table
                renderTable(allIssues);
                
                // Close detail panel to refresh the view
                closeDetail();
                
                console.log('Issues refreshed successfully');
            } catch (error) {
                console.error('Error refreshing issues:', error);
            }
        }

        async function fetchIssueDetail(key) {
            try {
                const res = await fetch(`/api/issue/${key}`);
                if (!res.ok) throw new Error(`HTTP ${res.status}`);
                const data = await res.json();
                return data;
            } catch (error) {
                console.error('Error fetching issue detail:', error);
                return { error: 'Failed to load issue details' };
            }
        }

        function formatIssueDetail(data) {
            if (data.error) {
                return `<div class="detail-section"><p style="color: var(--error-color);">Error: ${data.error}</p></div>`;
            }

            const issue = data.issue || data; // Handle both old and new format
            const customFields = data.custom_fields || [];
            const fields = issue.fields || {};
            const key = issue.key || 'Unknown';
            const summary = fields.summary || 'No summary';
            const description = fields.description || 'No description provided';
            const status = fields.status?.name || 'Unknown';
            const assignee = fields.assignee?.displayName || fields.assignee?.name || 'Unassigned';
            const reporter = fields.reporter?.displayName || fields.reporter?.name || 'Unknown';
            const priority = fields.priority?.name || 'Unknown';
            const issueType = fields.issuetype?.name || 'Unknown';
            const created = fields.created ? new Date(fields.created).toLocaleString() : 'Unknown';
            const updated = fields.updated ? new Date(fields.updated).toLocaleString() : 'Unknown';
            const labels = fields.labels || [];
            const components = fields.components || [];
            const fixVersions = fields.fixVersions || [];

            let html = `
                <div class="detail-section">
                    <h3>📋 Issue Information</h3>
                    <div class="detail-field">
                        <div class="detail-label">Key:</div>
                        <div class="detail-value"><strong><a href="#" class="issue-key" onclick="openIssueInTab('${key}'); return false;">${key}</a></strong></div>
                    </div>
                    <div class="detail-field">
                        <div class="detail-label">Type:</div>
                        <div class="detail-value">${issueType}</div>
                    </div>
                    <div class="detail-field">
                        <div class="detail-label">Status:</div>
                        <div class="detail-value"><span class="status-badge ${getStatusClass(status)}">${status}</span></div>
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
                            <button class="edit-label-btn" onclick="editLabels('${key}', ${JSON.stringify(labels).replace(/"/g, '&quot;')})">
                                ✏️ Edit
                            </button>
                        </h3>
                        <div class="detail-labels">
                            ${labels.map(label => `<span class="label-tag">${label}</span>`).join('')}
                        </div>
                    </div>
                `;
            } else {
                html += `
                    <div class="detail-section">
                        <h3>🏷️ Labels 
                            <button class="edit-label-btn" onclick="editLabels('${key}', [])">
                                ✏️ Add Labels
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
                            ${components.map(comp => comp.name || comp).join(', ')}
                        </div>
                    </div>
                `;
            }

            if (fixVersions.length > 0) {
                html += `
                    <div class="detail-section">
                        <h3>🎯 Fix Versions</h3>
                        <div class="detail-value">
                            ${fixVersions.map(ver => ver.name || ver).join(', ')}
                        </div>
                    </div>
                `;
            }

            // Show custom fields if present
            if (customFields.length > 0) {
                let customFieldsHtml = '';
                customFields.forEach(cf => {
                    const fieldId = cf.field;
                    const fieldName = cf.name || fieldId;
                    const fieldType = cf.type || 'string';

                    if (fieldId && fields[fieldId]) {
                        let value = fields[fieldId];

                        // Handle different value types
                        if (Array.isArray(value)) {
                            value = value.map(v => {
                                if (typeof v === 'object' && v !== null) {
                                    return v.value || v.name || v.displayName || JSON.stringify(v);
                                }
                                return v;
                            }).filter(v => v).join(', ');
                        } else if (typeof value === 'object' && value !== null) {
                            value = value.value || value.name || value.displayName || JSON.stringify(value);
                        }

                        if (value) {
                            if (fieldType === 'text') {
                                customFieldsHtml += `
                                    <div class="detail-field">
                                        <div class="detail-label">${fieldName}:</div>
                                        <div class="detail-value">
                                            <div class="detail-description">${value}</div>
                                        </div>
                                    </div>
                                `;
                            } else if (fieldType === 'url') {
                                customFieldsHtml += `
                                    <div class="detail-field">
                                        <div class="detail-label">${fieldName}:</div>
                                        <div class="detail-value">
                                            <a href="${value}" class="detail-link" target="_blank">${value}</a>
                                        </div>
                                    </div>
                                `;
                            } else {
                                customFieldsHtml += `
                                    <div class="detail-field">
                                        <div class="detail-label">${fieldName}:</div>
                                        <div class="detail-value">${value}</div>
                                    </div>
                                `;
                            }
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
            const rawJson = document.getElementById('raw-json');
            const button = document.querySelector('.raw-json-toggle');

            if (rawJson.style.display === 'none' || rawJson.style.display === '') {
                rawJson.style.display = 'block';
                button.textContent = '📋 Hide Raw JSON';
            } else {
                rawJson.style.display = 'none';
                button.textContent = '🔍 Show Raw JSON';
            }
        }

        function getStatusClass(status) {
            const statusLower = status.toLowerCase();
            if (statusLower.includes('todo') || statusLower.includes('new') || statusLower.includes('open')) return 'status-todo';
            if (statusLower.includes('progress') || statusLower.includes('doing')) return 'status-progress';
            if (statusLower.includes('review') || statusLower.includes('qa')) return 'status-review';
            if (statusLower.includes('done') || statusLower.includes('closed') || statusLower.includes('resolved')) return 'status-done';
            return 'status-default';
        }

        function getUserInitials(name) {
            if (!name || name === 'None') return '?';
            return name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2);
        }

        function formatDate(dateStr) {
            if (!dateStr) return '';
            const date = new Date(dateStr);
            return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
        }

        function renderTable(issues) {
            const tbody = document.getElementById('issues-tbody');

            if (issues.length === 0) {
                tbody.innerHTML = '<tr><td colspan="8" class="no-issues">No issues found</td></tr>';
                return;
            }

            tbody.innerHTML = issues.map((row, index) => `
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
            `).join('');

            updateStats(issues.length);
        }

        function updateStats(count) {
            document.getElementById('stats').textContent = `${count} issue${count !== 1 ? 's' : ''}`;
        }

        async function selectRow(row, key) {
            // Remove previous selection
            if (selectedRow) {
                selectedRow.classList.remove('selected');
            }

            // Select new row
            selectedRow = row;
            row.classList.add('selected');

            // Show detail panel
            const detail = await fetchIssueDetail(key);
            showDetail(key, detail);
            
            // Save state when issue is selected
            saveUIState();
        }

        function showDetail(key, detail) {
            const panel = document.getElementById('detail-panel');
            panel.classList.remove('empty');

            panel.innerHTML = `
                <div class="detail-content">${formatIssueDetail(detail)}</div>
            `;
        }

        function closeDetail() {
            const panel = document.getElementById('detail-panel');
            panel.classList.add('empty');
            panel.innerHTML = `
                <div style="text-align: center; color: var(--text-muted);">
                    📋 Select an issue to view details
                </div>
            `;

            if (selectedRow) {
                selectedRow.classList.remove('selected');
                selectedRow = null;
            }
        }

        // Search functionality with debouncing
        let searchTimeout;
        document.getElementById('search').addEventListener('input', (e) => {
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(async () => {
                const issues = await fetchIssues(e.target.value);
                renderTable(issues);
                closeDetail(); // Close detail panel when searching
                
                // Save state when search query changes
                saveUIState();
            }, 300);
        });

        // Search toggle functionality
        function toggleSearchBar() {
            const searchContainer = document.querySelector('.search-container');
            const searchToggle = document.getElementById('search-toggle');
            const searchInput = document.getElementById('search');

            if (searchContainer.classList.contains('visible')) {
                // Hide search
                searchContainer.classList.remove('visible');
                searchToggle.classList.remove('active');
                searchToggle.title = 'Show search (Press /)';

                // Clear search if hiding
                if (searchInput.value.trim()) {
                    searchInput.value = '';
                    // Trigger search to show all issues
                    fetchIssues().then(issues => renderTable(issues));
                    closeDetail();
                }
            } else {
                // Show search
                searchContainer.classList.add('visible');
                searchToggle.classList.add('active');
                searchToggle.title = 'Hide search (Press /)';

                // Focus on search input after animation
                setTimeout(() => {
                    searchInput.focus();
                }, 200);
            }
            
            // Save state when search visibility changes
            saveUIState();
        }

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            // Don't trigger shortcuts when typing in input fields
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
                return;
            }

            if (e.key === 'Escape') {
                // Close help overlay first, then board modal, then search, then detail panel
                const helpOverlay = document.getElementById('help-overlay');
                const boardModal = document.getElementById('board-modal');
                const searchContainer = document.querySelector('.search-container');
                if (helpOverlay && helpOverlay.style.display !== 'none') {
                    hideHelpOverlay();
                } else if (boardModal) {
                    hideBoardSelector();
                } else if (searchContainer && searchContainer.classList.contains('visible')) {
                    toggleSearchBar();
                } else {
                    closeDetail();
                }
            } else if (e.key === 't') {
                e.preventDefault();
                toggleViewState();
            } else if (e.key.toLowerCase() === 'v') {
                e.preventDefault();
                toggleLayoutState();
            } else if (e.key.toLowerCase() === 'b') {
                e.preventDefault();
                showBoardSelector();
            } else if (e.key === 'r') {
                e.preventDefault();
                refreshIssues();
            } else if (e.key === '/') {
                e.preventDefault();
                toggleSearchBar();
            } else if (e.key === 'j') {
                e.preventDefault();
                navigateIssueList('down');
            } else if (e.key === 'k') {
                e.preventDefault();
                navigateIssueList('up');
            } else if (e.key === 'J') {
                e.preventDefault();
                scrollDetailPanel('down');
            } else if (e.key === 'K') {
                e.preventDefault();
                scrollDetailPanel('up');
            } else if (e.key === 'o' || e.key === 'O') {
                e.preventDefault();
                openSelectedIssueInNewTab();
            } else if (e.key === 'y' || e.key === 'Y') {
                e.preventDefault();
                yankIssueUrl();
            } else if (e.key === 'L') {
                e.preventDefault();
                editSelectedIssueLabels();
            } else if (e.key === '?') {
                e.preventDefault();
                showHelpOverlay();
            } else if (e.key === 'Home') {
                e.preventDefault();
                navigateToFirstIssue();
            } else if (e.key === 'End') {
                e.preventDefault();
                navigateToLastIssue();
            } else if (e.key === 'PageUp') {
                e.preventDefault();
                if (e.shiftKey) {
                    scrollDetailPanelPage('up');
                } else {
                    navigatePageUp();
                }
            } else if (e.key === 'PageDown') {
                e.preventDefault();
                if (e.shiftKey) {
                    scrollDetailPanelPage('down');
                } else {
                    navigatePageDown();
                }
            } else if (e.key === ' ') {
                e.preventDefault();
                if (e.shiftKey) {
                    scrollDetailPanelPage('up');
                } else {
                    scrollDetailPanelPage('down');
                }
            } else if (e.key === '/') {
                e.preventDefault();
                toggleSearchBar();
            }
        });

        // View toggle event listener
        document.getElementById('view-toggle').addEventListener('click', toggleViewState);

        // Layout toggle event listener
        document.getElementById('layout-toggle').addEventListener('click', toggleLayoutState);

        // Search toggle event listener
        document.getElementById('search-toggle').addEventListener('click', toggleSearchBar);

        // Refresh button event listener
        document.getElementById('refresh-button').addEventListener('click', refreshIssues);

        // Board selector event listener
        document.getElementById('board-selector').addEventListener('click', showBoardSelector);

        // Board management functions
        async function loadBoards() {
            try {
                const res = await fetch('/api/boards');
                if (res.ok) {
                    const data = await res.json();
                    availableBoards = data.boards || [];
                    updateBoardSelectorText();
                }
            } catch (error) {
                console.error('Error loading boards:', error);
            }
        }

        function updateBoardSelectorText() {
            const selector = document.getElementById('board-selector');
            if (currentBoard && selector) {
                selector.textContent = `📋 ${currentBoard}`;
            } else if (selector) {
                selector.textContent = '📋 Board';
            }
        }

        function showBoardSelector() {
            if (availableBoards.length === 0) {
                showNotification('No boards configured', 'error');
                return;
            }

            // Remove existing modal if it exists
            const existingModal = document.getElementById('board-modal');
            if (existingModal) {
                existingModal.remove();
            }

            // Create board selection modal
            const modal = document.createElement('div');
            modal.id = 'board-modal';
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

            const modalContent = document.createElement('div');
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
                        background: ${isSelected ? '#f1f8ff' : '#ffffff'};
                        border: 1px solid ${isSelected ? '#0366d6' : '#e1e4e8'};
                        border-radius: 6px;
                        padding: 0.75rem;
                        cursor: pointer;
                        text-align: left;
                        transition: all 0.2s ease;
                        color: ${isSelected ? '#0366d6' : '#24292e'};
                    ">
                        <div style="font-weight: 600; margin-bottom: 0.25rem;">${board.name} ${isSelected ? '✓' : ''}</div>
                        <div style="font-size: 0.875rem; color: #6a737d;">${board.description}</div>
                    </button>
                `;
            });

            boardsHtml += '</div>';
            modalContent.innerHTML = boardsHtml;
            modal.appendChild(modalContent);
            document.body.appendChild(modal);

            // Add event listeners
            modal.addEventListener('click', (e) => {
                if (e.target === modal) {
                    hideBoardSelector();
                }
            });

            document.getElementById('close-board-modal').addEventListener('click', hideBoardSelector);

            // Add click handlers for board options
            modalContent.querySelectorAll('.board-option').forEach(button => {
                button.addEventListener('click', () => {
                    const boardName = button.getAttribute('data-board-name');
                    switchToBoard(boardName);
                });

                button.addEventListener('mouseenter', () => {
                    if (!button.style.backgroundColor.includes('f1f8ff')) {
                        button.style.backgroundColor = '#f6f8fa';
                        button.style.borderColor = '#d1d5da';
                    }
                });

                button.addEventListener('mouseleave', () => {
                    if (!button.style.backgroundColor.includes('f1f8ff')) {
                        button.style.backgroundColor = '#ffffff';
                        button.style.borderColor = '#e1e4e8';
                    }
                });
            });
        }

        function hideBoardSelector() {
            const modal = document.getElementById('board-modal');
            if (modal) {
                modal.remove();
            }
        }

        async function switchToBoard(boardName) {
            try {
                hideBoardSelector();
                showNotification(`🔄 Switching to ${boardName}...`, 'info');

                const res = await fetch(`/api/boards/${encodeURIComponent(boardName)}/switch`, {
                    method: 'POST'
                });

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

                showNotification(`✅ Switched to ${boardName} (${result.issue_count} issues)`, 'success');
            } catch (error) {
                console.error('Error switching board:', error);
                showNotification(`❌ Failed to switch to ${boardName}`, 'error');
            }
        }

        // Initial load
        async function init() {
            // Initialize state management
            initializeViewState();
            initializeLayoutState();
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
        }

        init();

        // Additional navigation functions for Page Up/Down, Home/End
        function navigateToFirstIssue() {
            const tbody = document.getElementById('issues-tbody');
            const firstRow = tbody.querySelector('tr:not(.loading):not(.no-issues)');
            if (firstRow) {
                const keyCell = firstRow.querySelector('td:nth-child(2) a');
                if (keyCell) {
                    const issueKey = keyCell.textContent.trim();
                    selectRow(firstRow, issueKey);
                    firstRow.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                }
            }
        }

        function navigateToLastIssue() {
            const tbody = document.getElementById('issues-tbody');
            const rows = Array.from(tbody.querySelectorAll('tr')).filter(row =>
                !row.querySelector('.loading') && !row.querySelector('.no-issues')
            );
            const lastRow = rows[rows.length - 1];
            if (lastRow) {
                const keyCell = lastRow.querySelector('td:nth-child(2) a');
                if (keyCell) {
                    const issueKey = keyCell.textContent.trim();
                    selectRow(lastRow, issueKey);
                    lastRow.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                }
            }
        }

        function navigatePageUp() {
            const tbody = document.getElementById('issues-tbody');
            const rows = Array.from(tbody.querySelectorAll('tr')).filter(row =>
                !row.querySelector('.loading') && !row.querySelector('.no-issues')
            );

            if (rows.length === 0) return;

            let currentIndex = -1;
            if (selectedRow) {
                currentIndex = rows.findIndex(row => row === selectedRow);
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
                const keyCell = newRow.querySelector('td:nth-child(2) a');
                if (keyCell) {
                    const issueKey = keyCell.textContent.trim();
                    selectRow(newRow, issueKey);
                    newRow.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                }
            }
        }

        function navigatePageDown() {
            const tbody = document.getElementById('issues-tbody');
            const rows = Array.from(tbody.querySelectorAll('tr')).filter(row =>
                !row.querySelector('.loading') && !row.querySelector('.no-issues')
            );

            if (rows.length === 0) return;

            let currentIndex = -1;
            if (selectedRow) {
                currentIndex = rows.findIndex(row => row === selectedRow);
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
                const keyCell = newRow.querySelector('td:nth-child(2) a');
                if (keyCell) {
                    const issueKey = keyCell.textContent.trim();
                    selectRow(newRow, issueKey);
                    newRow.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                }
            }
        }

        function scrollDetailPanelPage(direction) {
            const detailContent = document.querySelector('.detail-content');
            if (!detailContent) return;

            const containerHeight = detailContent.clientHeight;
            const scrollAmount = containerHeight * 0.8; // Scroll 80% of visible area
            const currentScroll = detailContent.scrollTop;

            if (direction === 'down') {
                detailContent.scrollTo({
                    top: currentScroll + scrollAmount,
                    behavior: 'smooth'
                });
            } else {
                detailContent.scrollTo({
                    top: Math.max(0, currentScroll - scrollAmount),
                    behavior: 'smooth'
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
                const response = await fetch('/api/labels');
                const data = await response.json();
                const allLabels = data.labels || [];

                // Show the modal
                showLabelEditModal(issueKey, currentLabels, allLabels);
            } catch (error) {
                console.error('Error fetching labels:', error);
                showNotification('Failed to load labels', 'error');
            }
        }

        function showLabelEditModal(issueKey, currentLabels, allLabels) {
            // Remove existing modal if it exists
            if (labelEditModal) {
                labelEditModal.remove();
            }

            // Create modal
            labelEditModal = document.createElement('div');
            labelEditModal.className = 'label-edit-modal';
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
            const selectElement = document.getElementById('label-select');
            labelSelect = new TomSelect(selectElement, {
                create: true,
                createOnBlur: true,
                highlight: true,
                persist: false,
                maxItems: null,
                valueField: 'value',
                labelField: 'text',
                searchField: ['text'],
                options: allLabels.map(label => ({ value: label, text: label })),
                items: currentLabels,
                plugins: ['remove_button'],
                render: {
                    option: function (data, escape) {
                        return '<div>' + escape(data.text) + '</div>';
                    },
                    item: function (data, escape) {
                        return '<div>' + escape(data.text) + '</div>';
                    }
                },
                onItemAdd: function () {
                    this.close();
                },
                create: function (input) {
                    return {
                        value: input,
                        text: input
                    };
                }
            });

            // Focus on the select
            setTimeout(() => {
                labelSelect.focus();
            }, 100);

            // Close modal on escape
            const escapeHandler = (e) => {
                if (e.key === 'Escape') {
                    closeLabelEditModal();
                    document.removeEventListener('keydown', escapeHandler);
                }
            };
            document.addEventListener('keydown', escapeHandler);

            // Close modal when clicking outside
            labelEditModal.addEventListener('click', (e) => {
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
                    method: 'PUT',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ labels: newLabels })
                });

                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}`);
                }

                const result = await response.json();
                showNotification(`Labels updated for ${currentEditingIssue}`, 'success');

                // Refresh the issue detail to show updated labels
                const issueDetail = await fetchIssueDetail(currentEditingIssue);
                showDetail(currentEditingIssue, issueDetail);

                // Close the modal
                closeLabelEditModal();

            } catch (error) {
                console.error('Error saving labels:', error);
                showNotification('Failed to save labels', 'error');
            }
        }

        // Toggle layout state
        function toggleLayoutState() {
            const container = document.getElementById('view-container');
            const layoutToggleBtn = document.getElementById('layout-toggle');

            // Remove current layout class
            container.classList.remove(currentLayoutState);

            // Toggle between horizontal and vertical
            currentLayoutState = currentLayoutState === LAYOUT_STATES.HORIZONTAL
                ? LAYOUT_STATES.VERTICAL
                : LAYOUT_STATES.HORIZONTAL;

            // Apply new layout
            container.classList.add(currentLayoutState);

            // Update button icon and title
            if (layoutToggleBtn) {
                layoutToggleBtn.innerHTML = `<img src="${LAYOUT_ICONS[currentLayoutState]}" alt="">`;
                layoutToggleBtn.title = LAYOUT_TITLES[currentLayoutState];
            }

            // Save state to cookies
            saveUIState();

            // Show notification
            const layoutName = currentLayoutState === LAYOUT_STATES.HORIZONTAL ? 'horizontal (side by side)' : 'vertical (top/bottom)';
            showNotification(`Layout changed to ${layoutName}`);
        }

        // Initialize layout state from cookies or default
        function initializeLayoutState() {
            const savedLayout = getCookie(STATE_COOKIES.LAYOUT);
            if (savedLayout && Object.values(LAYOUT_STATES).includes(savedLayout)) {
                currentLayoutState = savedLayout;
            }

            const container = document.getElementById('view-container');
            const layoutToggleBtn = document.getElementById('layout-toggle');

            container.classList.add(currentLayoutState);

            // Initialize button icon and title
            if (layoutToggleBtn) {
                layoutToggleBtn.innerHTML = `<img src="${LAYOUT_ICONS[currentLayoutState]}" alt="">`;
                layoutToggleBtn.title = LAYOUT_TITLES[currentLayoutState];
            }
        }
