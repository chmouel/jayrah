---
applyTo: '**/tui/**'
---

if you need to test the tui feature you can use the following command:

```bash
textual run --dev jayrah.cli:main -- browse
```

here is the help of textual run command:

```text
Options:
  --dev                       Enable development mode.
  --host HOST                 Host where the development console is running.
                              Defaults to 127.0.0.1.
  --port PORT                 Port where the development console is running.
                              Defaults to 8081.
  --press TEXT                Comma separated keys to simulate press.
  --screenshot DELAY          Take screenshot after DELAY seconds.
  --screenshot-path PATH      The target location for the screenshot
  --screenshot-filename NAME  The filename for the screenshot
  -c, --command               Run as command rather that a file / module.
  -r, --show-return           Show any return value on exit.
  --help                      Show this message and exit.
  ```

  and then for the command you can press the keybinding of the feature you want to test but that needs to be passed for textual run command ie

```bash
textual run --dev --press t,q jayrah.cli:main -- browse myissues
```

  so same you can take a screenshot if i ask you to do with that feature.

  you can send 'q' to quit the tui.
