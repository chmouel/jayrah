import datetime


def colorize(color, pipe_char):
    colors = {
        "cyan": "\033[96m",
        "reset": "\033[0m",
    }
    return f"{colors.get(color)}{pipe_char}{colors.get('reset')}"


def show_time(s):
    return datetime.datetime.strptime(s, "%Y-%m-%dT%H:%M:%S.%f%z").strftime("%Y-%m-%d")


def parse_email(s):
    return s.split("@")[0].split("+")[0]
