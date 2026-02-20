use std::env;

use anyhow::{anyhow, Result};

use crate::types::AdapterSource;

#[derive(Debug)]
pub enum CliAction {
    Run(AdapterSource),
    Help,
}

pub fn parse_cli_action() -> Result<CliAction> {
    parse_args(env::args().skip(1))
}

pub fn print_help() {
    println!("jayrah-tui (phase 1 preview)");
    println!("Usage:");
    println!("  cargo run -p jayrah-tui -- [--board <name>] [--query <jql>] [--mock]");
    println!("Options:");
    println!("  --board <name>   Load issues from a configured board");
    println!("  --query <jql>    Load issues from a raw JQL query");
    println!("  --mock           Skip adapter calls and use built-in mock issues");
}

fn parse_args<I>(args: I) -> Result<CliAction>
where
    I: IntoIterator<Item = String>,
{
    let mut board = None;
    let mut query = None;
    let mut mock_only = false;

    let mut args = args.into_iter();
    while let Some(arg) = args.next() {
        match arg.as_str() {
            "--board" => {
                board = Some(
                    args.next()
                        .ok_or_else(|| anyhow!("--board requires a value"))?,
                );
            }
            "--query" | "-q" => {
                query = Some(
                    args.next()
                        .ok_or_else(|| anyhow!("--query requires a value"))?,
                );
            }
            "--mock" => {
                mock_only = true;
            }
            "--help" | "-h" => {
                return Ok(CliAction::Help);
            }
            other => return Err(anyhow!("Unknown argument: {other}")),
        }
    }

    if board.is_some() && query.is_some() {
        return Err(anyhow!("Use either --board or --query, not both"));
    }

    // If nothing is provided, use the legacy default board name.
    if !mock_only && board.is_none() && query.is_none() {
        board = Some("myissue".to_string());
    }

    Ok(CliAction::Run(AdapterSource {
        board,
        query,
        mock_only,
    }))
}

#[cfg(test)]
mod tests {
    use super::{parse_args, CliAction};

    #[test]
    fn defaults_to_legacy_board_when_no_args() {
        let action = parse_args(Vec::<String>::new()).expect("action");
        let CliAction::Run(source) = action else {
            panic!("expected run action");
        };

        assert_eq!(source.board.as_deref(), Some("myissue"));
        assert!(!source.mock_only);
    }

    #[test]
    fn returns_help_action() {
        let action = parse_args(vec!["--help".to_string()]).expect("action");
        assert!(matches!(action, CliAction::Help));
    }

    #[test]
    fn rejects_board_and_query_together() {
        let error = parse_args(vec![
            "--board".to_string(),
            "my".to_string(),
            "--query".to_string(),
            "project = DEMO".to_string(),
        ])
        .expect_err("expected error");

        assert!(error.to_string().contains("either --board or --query"));
    }
}
