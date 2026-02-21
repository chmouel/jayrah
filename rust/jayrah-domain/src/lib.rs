#[derive(Clone, Debug, PartialEq, Eq)]
pub struct QuerySource {
    pub board: Option<String>,
    pub query: Option<String>,
}

impl QuerySource {
    pub fn is_query_mode(&self) -> bool {
        self.query.is_some()
    }
}

#[cfg(test)]
mod tests {
    use super::QuerySource;

    #[test]
    fn query_mode_detects_query_presence() {
        let source = QuerySource {
            board: None,
            query: Some("project = DEMO".to_string()),
        };
        assert!(source.is_query_mode());
    }
}
