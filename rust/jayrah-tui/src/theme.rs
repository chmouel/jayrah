use ratatui::style::{Color, Modifier, Style};

const BASE03: Color = Color::Indexed(234);
const BASE02: Color = Color::Indexed(235);
const BASE01: Color = Color::Indexed(240);
const BASE0: Color = Color::Indexed(244);
const BASE1: Color = Color::Indexed(245);
const BASE2: Color = Color::Indexed(254);
const BASE3: Color = Color::Indexed(230);
const YELLOW: Color = Color::Indexed(136);
const ORANGE: Color = Color::Indexed(166);
const RED: Color = Color::Indexed(124);
const BLUE: Color = Color::Indexed(33);
const CYAN: Color = Color::Indexed(37);
const GREEN: Color = Color::Indexed(64);
const VIOLET: Color = Color::Indexed(61);

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum StatusTone {
    Neutral,
    Info,
    Success,
    Warning,
    Error,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Theme;

impl Theme {
    pub fn solarized_warm() -> Self {
        Self
    }

    pub fn screen(self) -> Style {
        Style::default().bg(BASE03).fg(BASE0)
    }

    pub fn panel(self) -> Style {
        Style::default().bg(BASE03).fg(BASE0)
    }

    pub fn panel_border(self, active: bool) -> Style {
        if active {
            Style::default().fg(CYAN).add_modifier(Modifier::BOLD)
        } else {
            Style::default().fg(BASE01)
        }
    }

    pub fn panel_title(self, active: bool) -> Style {
        if active {
            Style::default().fg(YELLOW).add_modifier(Modifier::BOLD)
        } else {
            Style::default().fg(BASE1).add_modifier(Modifier::BOLD)
        }
    }

    pub fn detail_section_title(self) -> Style {
        Style::default().fg(ORANGE).add_modifier(Modifier::BOLD)
    }

    pub fn detail_label(self) -> Style {
        Style::default().fg(CYAN).add_modifier(Modifier::BOLD)
    }

    pub fn detail_value(self) -> Style {
        Style::default().fg(BASE2)
    }

    pub fn detail_loading(self) -> Style {
        Style::default().fg(BLUE).add_modifier(Modifier::BOLD)
    }

    pub fn detail_error(self) -> Style {
        Style::default().fg(RED).add_modifier(Modifier::BOLD)
    }

    pub fn detail_placeholder(self) -> Style {
        Style::default().fg(BASE1).add_modifier(Modifier::DIM)
    }

    pub fn table_header(self) -> Style {
        Style::default()
            .bg(BASE02)
            .fg(BASE2)
            .add_modifier(Modifier::BOLD)
    }

    pub fn table_row(self) -> Style {
        Style::default().bg(BASE03).fg(BASE0)
    }

    pub fn table_status(self, status: &str) -> Style {
        self.status(issue_status_tone(status))
    }

    pub fn table_selected(self) -> Style {
        Style::default()
            .bg(BLUE)
            .fg(BASE3)
            .add_modifier(Modifier::BOLD)
    }

    pub fn popup(self) -> Style {
        Style::default().bg(BASE02).fg(BASE2)
    }

    pub fn popup_border(self) -> Style {
        Style::default().fg(VIOLET)
    }

    pub fn popup_title(self) -> Style {
        Style::default().fg(ORANGE).add_modifier(Modifier::BOLD)
    }

    pub fn edit_help(self) -> Style {
        Style::default().fg(BASE1).add_modifier(Modifier::DIM)
    }

    pub fn filter_bar(self, focused: bool) -> Style {
        if focused {
            Style::default()
                .bg(BASE02)
                .fg(CYAN)
                .add_modifier(Modifier::BOLD)
        } else {
            Style::default().bg(BASE02).fg(BASE1)
        }
    }

    pub fn search_bar(self, focused: bool) -> Style {
        if focused {
            Style::default()
                .bg(BASE02)
                .fg(BLUE)
                .add_modifier(Modifier::BOLD)
        } else {
            Style::default().bg(BASE02).fg(BASE1)
        }
    }

    pub fn footer_base(self) -> Style {
        Style::default().bg(BASE02).fg(BASE1)
    }

    pub fn footer_mode(self) -> Style {
        Style::default().fg(YELLOW).add_modifier(Modifier::BOLD)
    }

    pub fn footer_hint(self) -> Style {
        Style::default().fg(BASE0)
    }

    pub fn status(self, tone: StatusTone) -> Style {
        match tone {
            StatusTone::Neutral => Style::default().fg(BASE1),
            StatusTone::Info => Style::default().fg(CYAN),
            StatusTone::Success => Style::default().fg(GREEN).add_modifier(Modifier::BOLD),
            StatusTone::Warning => Style::default().fg(ORANGE).add_modifier(Modifier::BOLD),
            StatusTone::Error => Style::default().fg(RED).add_modifier(Modifier::BOLD),
        }
    }
}

pub fn issue_status_tone(status: &str) -> StatusTone {
    let lowered = status.to_ascii_lowercase();

    if contains_any(
        lowered.as_str(),
        &[
            "failed",
            "failure",
            "error",
            "rejected",
            "cancelled",
            "canceled",
        ],
    ) {
        return StatusTone::Error;
    }

    if contains_any(
        lowered.as_str(),
        &[
            "done",
            "closed",
            "resolved",
            "complete",
            "completed",
            "accepted",
            "deployed",
            "merged",
        ],
    ) {
        return StatusTone::Success;
    }

    if contains_any(
        lowered.as_str(),
        &[
            "blocked", "on hold", "pending", "waiting", "todo", "to do", "backlog",
        ],
    ) {
        return StatusTone::Warning;
    }

    if contains_any(
        lowered.as_str(),
        &[
            "in progress",
            "progress",
            "review",
            "testing",
            "qa",
            "ready",
            "triage",
        ],
    ) {
        return StatusTone::Info;
    }

    StatusTone::Neutral
}

pub fn status_tone(status_line: &str) -> StatusTone {
    let lowered = status_line.to_ascii_lowercase();

    if contains_any(
        lowered.as_str(),
        &["error", "failed", "failure", "unable", "invalid", "denied"],
    ) {
        return StatusTone::Error;
    }

    if contains_any(
        lowered.as_str(),
        &[
            "saved",
            "loaded",
            "applied",
            "submitted",
            "opened",
            "reloaded",
            "updated",
            "switched",
            "selected",
            "created",
        ],
    ) {
        return StatusTone::Success;
    }

    if contains_any(
        lowered.as_str(),
        &["warning", "fallback", "mock", "disabled", "empty", "none"],
    ) {
        return StatusTone::Warning;
    }

    if contains_any(
        lowered.as_str(),
        &["focus", "search", "filter", "help", "mode"],
    ) {
        return StatusTone::Info;
    }

    StatusTone::Neutral
}

fn contains_any(line: &str, patterns: &[&str]) -> bool {
    patterns.iter().any(|pattern| line.contains(pattern))
}

#[cfg(test)]
mod tests {
    use ratatui::style::{Color, Modifier};

    use super::{issue_status_tone, status_tone, StatusTone, Theme};

    #[test]
    fn selected_row_style_uses_contrasting_accent() {
        let style = Theme::solarized_warm().table_selected();
        assert_eq!(style.bg, Some(Color::Indexed(33)));
        assert_eq!(style.fg, Some(Color::Indexed(230)));
        assert!(style.add_modifier.contains(Modifier::BOLD));
    }

    #[test]
    fn focused_filter_style_emphasizes_focus() {
        let style = Theme::solarized_warm().filter_bar(true);
        assert_eq!(style.bg, Some(Color::Indexed(235)));
        assert_eq!(style.fg, Some(Color::Indexed(37)));
        assert!(style.add_modifier.contains(Modifier::BOLD));
    }

    #[test]
    fn status_tone_detects_error_and_success() {
        assert_eq!(status_tone("Failed to load issues"), StatusTone::Error);
        assert_eq!(status_tone("Loaded 10 issues"), StatusTone::Success);
    }

    #[test]
    fn detail_styles_are_semantic_and_visible() {
        let theme = Theme::solarized_warm();
        let label = theme.detail_label();
        assert_eq!(label.fg, Some(Color::Indexed(37)));
        assert!(label.add_modifier.contains(Modifier::BOLD));

        let loading = theme.detail_loading();
        assert_eq!(loading.fg, Some(Color::Indexed(33)));
        assert!(loading.add_modifier.contains(Modifier::BOLD));

        let placeholder = theme.detail_placeholder();
        assert_eq!(placeholder.fg, Some(Color::Indexed(245)));
        assert!(placeholder.add_modifier.contains(Modifier::DIM));
    }

    #[test]
    fn issue_status_tone_maps_common_workflow_statuses() {
        assert_eq!(issue_status_tone("Done"), StatusTone::Success);
        assert_eq!(issue_status_tone("In Progress"), StatusTone::Info);
        assert_eq!(issue_status_tone("Blocked"), StatusTone::Warning);
        assert_eq!(issue_status_tone("Failed"), StatusTone::Error);
        assert_eq!(issue_status_tone("Open"), StatusTone::Neutral);
    }

    #[test]
    fn table_status_style_uses_expected_status_color() {
        let done_style = Theme::solarized_warm().table_status("Done");
        assert_eq!(done_style.fg, Some(Color::Indexed(64)));
        assert!(done_style.add_modifier.contains(Modifier::BOLD));

        let blocked_style = Theme::solarized_warm().table_status("Blocked");
        assert_eq!(blocked_style.fg, Some(Color::Indexed(166)));
    }
}
