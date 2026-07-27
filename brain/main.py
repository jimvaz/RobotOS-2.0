"""RobotOS Brain application entry point."""

from brain.config import CONFIG
from brain.server import BrainServer
from shared.logger import configure_logging
from shared.version import BRAIN_NAME, ROBOTOS_VERSION


def main() -> None:
    configure_logging(
        level=CONFIG.log_level,
        log_file="logs/brain.log",
    )

    print("=" * 48)
    print(f"{BRAIN_NAME} {ROBOTOS_VERSION}")
    print("=" * 48)

    server = BrainServer()
    server.run()


if __name__ == "__main__":
    main()