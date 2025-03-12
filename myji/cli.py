import sys
from . import myji, utils


def main():
    app = myji.MyJi()
    try:
        app.run()
    except KeyboardInterrupt:
        utils.log("Operation cancelled by user", "WARNING")
        sys.exit(1)
    except Exception as e:
        utils.log(f"Error: {e}", "ERROR")
        sys.exit(1)


if __name__ == "__main__":
    main()
