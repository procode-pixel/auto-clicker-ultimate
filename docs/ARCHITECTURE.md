# Architecture

The interface, the automation workers, storage, and operating-system calls are separate.

- `ui` draws the window and sends intents to `Controller`. It never sleeps on a click interval. A 200 ms timer reads a snapshot.
- `Controller` allows one worker: click engine, macro player, or workflow runner. A second start raises `BusyAutomation`.
- `ClickEngine`, `MacroPlayer`, and `WorkflowRunner` are daemon threads. Stop and emergency set an event that the wait loop checks about every 20 ms.
- `SafetyPolicy` validates a job before a thread starts. `clamp_policy` refuses limits above the hard ceiling.
- `platform.input_backend` uses Win32 `SendInput`/`mouse_event` on Windows and pynput elsewhere. Tests use `FakeBackend`.
- `platform.screen` grabs a frame with `mss` only while a recognition step runs, and only after the user enables capture.
- `storage.Database` is SQLite in the user profile directory. Import goes through `exchange.load_document`, which rejects unknown schemas, extra executable fields, and invalid jobs.

Closing the window can leave the tray icon running. Exit from the tray, or the emergency path, stops workers and closes the database. `Controller.shutdown` is safe to call twice.
