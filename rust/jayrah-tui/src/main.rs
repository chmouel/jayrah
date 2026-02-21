mod adapter;
mod app;
mod cli_args;
mod mock;
mod telemetry;
mod terminal;
mod theme;
mod tui;
mod types;
mod utils;
mod worker;

use anyhow::Result;
use std::{env, fs};

use app::App;
use cli_args::{parse_cli_action, print_help, CliAction};
use terminal::{restore_terminal, setup_terminal};
use tui::{run_app, RunOutcome};

fn emit_choose_result(chosen_key: &str, choose_output_path: Option<&str>) -> Result<()> {
    if let Some(path) = choose_output_path {
        fs::write(path, format!("{chosen_key}\n"))?;
    } else {
        println!("{chosen_key}");
    }
    Ok(())
}

fn main() -> Result<()> {
    let run_config = match parse_cli_action()? {
        CliAction::Help => {
            print_help();
            return Ok(());
        }
        CliAction::Run(config) => config,
    };

    if let Some(config_file) = run_config.config_file.as_deref() {
        env::set_var("JAYRAH_CONFIG_FILE", config_file);
    }

    let mut terminal = setup_terminal()?;
    let run_result = run_app(
        &mut terminal,
        App::new(run_config.source, run_config.choose_mode),
    );
    restore_terminal(&mut terminal)?;
    let outcome = run_result?;
    if let RunOutcome::Chosen(Some(key)) = outcome {
        let choose_output_path = env::var("JAYRAH_TUI_CHOOSE_FILE").ok();
        emit_choose_result(&key, choose_output_path.as_deref())?;
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use std::{fs, path::PathBuf};

    use super::emit_choose_result;

    fn temp_output_path() -> PathBuf {
        let mut path = std::env::temp_dir();
        let nanos = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .expect("time")
            .as_nanos();
        path.push(format!("jayrah-tui-choose-{nanos}.txt"));
        path
    }

    #[test]
    fn writes_selected_key_to_output_file_when_path_provided() {
        let path = temp_output_path();
        let path_string = path.to_string_lossy().to_string();

        emit_choose_result("JAY-999", Some(path_string.as_str())).expect("write result");

        let contents = fs::read_to_string(&path).expect("read file");
        assert_eq!(contents, "JAY-999\n");

        fs::remove_file(path).expect("cleanup");
    }
}
