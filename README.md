# RobotOS 2.0 — Sprint B1.1 Shared Core

This is the first executable foundation of RobotOS 2.0.

## Requirements

- Python 3.11

## Windows setup

```powershell
cd C:\RobotOS-2.0
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
pytest
```

Expected result: all tests pass.

## Current modules

- Protocol version constants
- Message type enumeration
- Pydantic message validation
- JSON serialization/deserialization
- Shared event definitions
- Loguru configuration

## Next sprint

Sprint B1.2 adds the Windows Brain WebSocket server.
