"""Nobi Node application entry point."""

from node.client import NodeClient
from node.config import CONFIG
from shared.logger import configure_logging
from shared.version import NOBI_VERSION, ROBOTOS_VERSION


def main() -> None:
    configure_logging(level=CONFIG.log_level, log_file="logs/node.log")
    print("=" * 48)
    print("              NOBI NODE")
    print("          Powered by RobotOS")
    print("=" * 48)
    print(f"Nobi {NOBI_VERSION} | RobotOS {ROBOTOS_VERSION}")
    NodeClient().run()


if __name__ == "__main__":
    main()
