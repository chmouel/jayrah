pub fn compact_error(value: &str) -> String {
    const LIMIT: usize = 60;
    let cleaned = value.replace('\n', " ");
    if cleaned.len() <= LIMIT {
        return cleaned;
    }
    format!("{}...", &cleaned[..LIMIT])
}

pub fn join_or_dash(values: &[String]) -> String {
    if values.is_empty() {
        return "-".to_string();
    }
    values.join(", ")
}

#[cfg(test)]
mod tests {
    use super::{compact_error, join_or_dash};

    #[test]
    fn compact_error_truncates_long_strings() {
        let input = "a".repeat(80);
        let compact = compact_error(&input);
        assert!(compact.ends_with("..."));
        assert!(compact.len() <= 63);
    }

    #[test]
    fn join_or_dash_formats_values() {
        assert_eq!(join_or_dash(&[]), "-");
        assert_eq!(join_or_dash(&["a".to_string(), "b".to_string()]), "a, b");
    }
}
