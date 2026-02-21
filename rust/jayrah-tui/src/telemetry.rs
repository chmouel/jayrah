use std::{
    env,
    sync::OnceLock,
    time::{Duration, SystemTime, UNIX_EPOCH},
};

static TELEMETRY_ENABLED: OnceLock<bool> = OnceLock::new();

pub fn emit_success(op: &str, key: Option<&str>, elapsed: Duration) {
    if !telemetry_enabled() {
        return;
    }
    eprintln!(
        "jayrah_tui_telemetry ts_unix_ms={} op={} key={} status=ok duration_ms={}",
        unix_ms_now(),
        sanitize(op),
        sanitize(key.unwrap_or("-")),
        elapsed.as_millis(),
    );
}

pub fn emit_failure(op: &str, key: Option<&str>, elapsed: Duration, error: &str) {
    if !telemetry_enabled() {
        return;
    }
    eprintln!(
        "jayrah_tui_telemetry ts_unix_ms={} op={} key={} status=error duration_ms={} error={}",
        unix_ms_now(),
        sanitize(op),
        sanitize(key.unwrap_or("-")),
        elapsed.as_millis(),
        sanitize(error),
    );
}

fn telemetry_enabled() -> bool {
    *TELEMETRY_ENABLED.get_or_init(|| {
        let value = env::var("JAYRAH_TUI_TELEMETRY").unwrap_or_default();
        parse_bool_flag(value.as_str())
    })
}

fn parse_bool_flag(value: &str) -> bool {
    matches!(
        value.trim().to_ascii_lowercase().as_str(),
        "1" | "true" | "yes" | "on"
    )
}

fn unix_ms_now() -> u128 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|duration| duration.as_millis())
        .unwrap_or(0)
}

fn sanitize(value: &str) -> String {
    value
        .replace('\\', "\\\\")
        .replace('\n', "\\n")
        .replace('\r', "\\r")
        .replace(' ', "_")
}

#[cfg(test)]
mod tests {
    use super::{parse_bool_flag, sanitize};

    #[test]
    fn parses_telemetry_bool_flags() {
        assert!(parse_bool_flag("1"));
        assert!(parse_bool_flag("true"));
        assert!(parse_bool_flag("YES"));
        assert!(parse_bool_flag("on"));
        assert!(!parse_bool_flag(""));
        assert!(!parse_bool_flag("0"));
        assert!(!parse_bool_flag("false"));
    }

    #[test]
    fn sanitizes_whitespace_and_control_characters() {
        let sanitized = sanitize("line one\nline\\two");
        assert_eq!(sanitized, "line_one\\nline\\\\two");
    }
}
