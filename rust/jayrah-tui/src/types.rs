#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Issue {
    pub key: String,
    pub summary: String,
    pub status: String,
    pub assignee: String,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct IssueDetail {
    pub key: String,
    pub summary: String,
    pub status: String,
    pub priority: String,
    pub issue_type: String,
    pub assignee: String,
    pub reporter: String,
    pub created: String,
    pub updated: String,
    pub labels: Vec<String>,
    pub components: Vec<String>,
    pub fix_versions: Vec<String>,
    pub description: String,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct AdapterSource {
    pub board: Option<String>,
    pub query: Option<String>,
    pub mock_only: bool,
}

impl AdapterSource {
    pub fn describe(&self) -> String {
        if self.mock_only {
            return "mock-only".to_string();
        }

        if let Some(query) = &self.query {
            return format!("query={query}");
        }

        if let Some(board) = &self.board {
            return format!("board={board}");
        }

        "board=myissue".to_string()
    }
}
