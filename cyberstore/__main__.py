"""Entry point for python -m cyberstore."""

from cyberstore.app import CyberStoreApp


def main() -> None:
    app = CyberStoreApp()
    app.run()


if __name__ == "__main__":
    main()
