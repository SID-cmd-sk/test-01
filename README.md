# test-01

Windows-first local startup scripts are available in `scripts/`.

## Single-command startup

```powershell
scripts/start.ps1
```

Optional flags:

- `-SkipInstall` skips dependency install
- `-SkipValidation` skips runtime checks
- `-NoRun` prepares environment without launching services

You can override launch commands with:

- `BACKEND_START_CMD`
- `UI_START_CMD`

## Double-click launcher

Use `scripts/start.bat` from File Explorer.
