import sys
from . import myji


def main():
    app = myji.MyJi()
    try:
        app.run()
    except KeyboardInterrupt:
        sys.exit(1)


if __name__ == "__main__":
    main()
