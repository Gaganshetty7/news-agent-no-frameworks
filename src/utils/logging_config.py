import logging
import sys
from typing import Optional


COLORS = {
    logging.DEBUG:    "\033[37m",   # white
    logging.INFO:     "\033[36m",   # cyan
    logging.WARNING:  "\033[33m",   # yellow
    logging.ERROR:    "\033[31m",   # red
    logging.CRITICAL: "\033[35m",   # magenta
}
RESET = "\033[0m"


class ColorFormatter(logging.Formatter):
    def format(self, record):
        color = COLORS.get(record.levelno, "")
        fmt = f"%(asctime)s {color}[%(levelname)s]{RESET} %(name)s: %(message)s"
        return logging.Formatter(fmt, datefmt="%H:%M:%S").format(record)


def setup_logging(level: str = "INFO", log_file: Optional[str] = None):
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    console = logging.StreamHandler(sys.stdout)
    console.setLevel(numeric_level)
    console.setFormatter(ColorFormatter())

    handlers = [console]

    if log_file:
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        ))
        handlers.append(fh)

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.handlers.clear()
    for h in handlers:
        root.addHandler(h)
