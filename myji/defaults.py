FIELDS = [
    "key",
    "summary",
    "assignee",
    "reporter",
    "updated",
    "created",
    "resolution",
    "issuetype",
    "fixVersion",
    "status",
]
FZFOPTS = [
    "--highlight-line",
    "--color",
    "gutter:-1,selected-bg:238,selected-fg:146,current-fg:189",
    "--exact",
    "--bind",
    "alt-n:next-history",
    "--bind",
    "alt-p:previous-history",
    "--bind",
    "ctrl-j:preview-down",
    "--bind",
    "ctrl-k:preview-up",
    "--bind",
    "ctrl-n:down",
    "--bind",
    "ctrl-p:up",
    "--bind",
    "ctrl-v:change-preview-window(up,70%:wrap|hidden|right:wrap)",
]

# Add a header note about F1 help
HEADER_NOTE = "Press F1 for help | Ctrl+V toggles preview | Enter to open"

SUMMARY_MAX_LENGTH = 100

ISSUE_TYPE_EMOJIS = {
    "Feature Request": ("🌟", "FR"),
    "Bug": ("🐛", "BG"),
    "Enhancement": ("🚀", "EN"),
    "Task": ("✅", "TA"),
    "Support Patch": ("🩹", "SP"),
    "Patch": ("🩹", "PA"),
    "CTS Challenge": ("🏆", "CC"),
    "Release": ("📦", "RE"),
    "Sub-task": ("📝", "ST"),
    "Quality Risk": ("⚠️", "QR"),
    "Component Upgrade Subtask": ("🔄", "CU"),
    "Component Upgrade": ("🔄", "CO"),
    "Story": ("📖", "SO"),
    "Epic": ("🏞️", "EP"),
    "Risk": ("⚠️", "RI"),
    "Weakness": ("🔍", "WE"),
    "Vulnerability": ("🔒", "VU"),
    "Library Upgrade": ("📚", "LU"),
    "Clarification": ("❓", "CL"),
    "Technical task": ("🛠️", "TT"),
    "Tracker": ("📌", "TR"),
    "Requirement": ("📜", "RQ"),
    "Sub-requirement": ("📜", "SR"),
    "Documentation": ("📄", "DO"),
    "Support Request": ("🆘", "SR"),
    "Content Change": ("📝", "CC"),
    "Technical Requirement": ("🛠️", "TR"),
    "Business Requirement": ("🏢", "BR"),
    "Initiative": ("🌱", "IN"),
    "Dev Task": ("💻", "DT"),
    "QE Task": ("🔍", "QT"),
    "Docs Task": ("📄", "DT"),
    "OKR": ("🎯", "OK"),
    "Policy": ("📜", "PO"),
    "Question": ("❓", "QU"),
    "Analysis": ("📊", "AN"),
    "Feature": ("🌟", "FE"),
    "Request": ("📨", "RQ"),
    "Flare": ("🔥", "FL"),
    "Spike": ("📈", "SP"),
    "Service Request": ("📞", "SR"),
    "Incident": ("🚨", "IN"),
    "Platform": ("🌐", "PL"),
    "Change Request": ("🔄", "CR"),
    "Support Exception": ("🆘", "SE"),
    "Review": ("🔍", "RE"),
    "Simple Task": ("✅", "ST"),
    "QE Sub-task": ("🔍", "QS"),
    "Dev Sub-task": ("💻", "DS"),
    "Docs Sub-task": ("📄", "DS"),
    "Simple Sub-task": ("✅", "SS"),
    "Next Action": ("⏭️", "NA"),
    "BU Initiative": ("🌱", "BI"),
    "RFE": ("🌟", "RF"),
    "Issue": ("🐛", "IS"),
    "Closed Loop": ("♾️", "CL"),
    "Milestone": ("🏆", "MI"),
    "Build Task": ("🏗️", "BT"),
    "Report": ("📈", "RP"),
    "Schedule": ("📅", "SC"),
    "Doc": ("📄", "DC"),
    "Technical Feature": ("🛠️", "TF"),
    "Release Milestone": ("🏆", "RM"),
    "Release tracker": ("📦", "RT"),
    "Ticket": ("🎫", "TI"),
    "Project": ("📁", "PR"),
    "Root Cause Analysis": ("🔍", "RC"),
    "Weather-item": ("🌦️", "WI"),
    "Ad-Hoc Task": ("📝", "AH"),
    "Stakeholder Request": ("📨", "SR"),
    "Story Bug": ("🐛", "SB"),
    "Info": ("ℹ️", "IF"),
    "Team Improvement": ("🌱", "TI"),
    "Wireframe": ("📐", "WF"),
    "Supply Chain Exception": ("🚚", "SC"),
    "Software Security Exception": ("🔒", "SE"),
    "Objective": ("🎯", "OB"),
    "Strategic Goal": ("🏆", "SG"),
    "Outcome": ("🏁", "OC"),
    "PSRD Exception": ("📜", "PE"),
    "New Feature": ("🌟", "NF"),
    "Improvement": ("🚀", "IM"),
}

# Status emoji mapping
STATUS_EMOJI = {
    "Open": "🔓",
    "In Progress": "🏗️",
    "Code Review": "👀",
    "On QA": "🧪",
    "Done": "✅",
    "Closed": "🔒",
    "Resolved": "🎯",
    "Reopened": "🔄",
    "New": "🆕",
    "To Do": "📌",
}

# Priority emoji mapping
PRIORITY_EMOJI = {
    "Blocker": "❌",
    "Critical": "🛑",
    "Major": "🔴",
    "Minor": "🟠",
    "Trivial": "🟢",
}

# Priority ANSI color mapping
PRIORITY_COLORS = {
    "Blocker": "\033[91m",  # Bright red
    "Critical": "\033[31m",  # Red
    "Major": "\033[33m",  # Yellow
    "Minor": "\033[36m",  # Cyan
    "Trivial": "\033[32m",  # Green
}


CACHE_DURATION = 60 * 60 * 24 * 1  # 1 day
