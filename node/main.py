"""RobotOS Node application entry point."""

from node.client import NodeClient
from node.config import CONFIG
from shared.logger import configure_logging
from shared.version import NODE_NAME, ROBOTOS_VERSION


def main() -> None:
    configure_logging(
        level=CONFIG.log_level,
        log_file="logs/node.log",
    )

    print("=" * 48)
    print(f"{NODE_NAME} {ROBOTOS_VERSION}")
    print("=" * 48)

    client = NodeClient()
    client.run()


if __name__ == "__main__":
    main()