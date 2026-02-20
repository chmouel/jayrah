mod adapter;
mod app;
mod cli_args;
mod mock;
mod terminal;
mod tui;
mod types;
mod utils;
mod worker;

use anyhow::Result;

use app::App;
use cli_args::{parse_cli_action, print_help, CliAction};
use terminal::{restore_terminal, setup_terminal};
use tui::run_app;

fn main() -> Result<()> {
    let source = match parse_cli_action()? {
        CliAction::Help => {
            print_help();
            return Ok(());
        }
        CliAction::Run(source) => source,
    };

    let mut terminal = setup_terminal()?;
    let run_result = run_app(&mut terminal, App::new(source));
    let restore_result = restore_terminal(&mut terminal);

    if let Err(error) = restore_result {
        return Err(error);
    }
    run_result
}
