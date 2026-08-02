"""Nobi Brain application entry point."""

from datetime import datetime

from brain.config import CONFIG
from brain.server import BrainServer
from shared.logger import configure_logging
from shared.version import NOBI_VERSION, ROBOTOS_VERSION


def _greeting() -> str:
    hour = datetime.now().hour
    if 5 <= hour < 12:
        return "Καλημέρα!"
    if 12 <= hour < 18:
        return "Καλό απόγευμα!"
    return "Καλησπέρα!"


def main() -> None:
    configure_logging(level=CONFIG.log_level, log_file="logs/brain.log")
    print("=" * 48)
    print("                 NOBI")
    print("          Powered by RobotOS")
    print("=" * 48)
    print(f"Nobi {NOBI_VERSION} | RobotOS {ROBOTOS_VERSION}")
    print()
    print(_greeting())
    print("Είμαι ο Nobi.")
    print("Έτοιμος να σε βοηθήσω.")
    print()
    BrainServer().run()


if __name__ == "__main__":
    main()
