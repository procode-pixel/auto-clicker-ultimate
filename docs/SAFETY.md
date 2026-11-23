# Safety

Auto Clicker Ultimate is a local automation tool. It is not a stealth utility.

- No process injection, no security bypass, no hidden window, no extra privileges.
- Every run is started by a button or a shortcut you configured.
- The emergency control is always on the sidebar and on `Ctrl+Shift+F12` unless you change that shortcut. The shortcut cannot be left empty.
- After an emergency stop, starting again requires clearing the latch.
- Fast or infinite configurations require the confirmation checkbox. The engine rejects them otherwise.
- Screen capture is off until the checkbox on Smart automation is enabled, and a grab happens only during a recognition step.
- Imported profiles, macros, and workflows are JSON documents. They are validated before they are stored. They are never passed to `eval` or a shell.
- Logs stay in `%APPDATA%\AutoClickerUltimate\autoclicker.log` on Windows.
