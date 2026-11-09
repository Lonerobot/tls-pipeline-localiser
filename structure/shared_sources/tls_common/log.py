"""Shared logging for every host. Stdlib only, so it runs on Python 3.11 (Maya, Nuke) and 3.13 (Blender).

Every logger lives under one stdlib logger, "tls", so the studio owns formatting and level in one place
and nothing is printed twice through a host's or AYON's own root handlers:

    tls                      handler, format and level are set here, once. Does not propagate.
    tls.maya.line_tools      one logger per tool, named <host>.<tool>

Use a subclass of the host class for each tool:

    from tls_common import MayaLogger

    class PlayblastLogger(MayaLogger):
        NAME = "playblast"

    PlayblastLogger.info("Output path %s", path)

Control (all optional):

    TLS_LOG_LEVEL   DEBUG, INFO, WARNING, ERROR, CRITICAL or a number. Default INFO.
    TLS_LOG_FILE    a file that also receives INFO and above.
"""
import logging
import os
import sys

ROOT_NAME = "tls"
LEVEL_VARIABLE = "TLS_LOG_LEVEL"
FILE_VARIABLE = "TLS_LOG_FILE"
DEFAULT_LEVEL = logging.INFO
FORMAT = "[%(name)s][%(levelname)s] %(message)s"
FILE_FORMAT = "[%(asctime)s][%(name)s][%(levelname)s] %(message)s"


def _level_from_environment():
    text = os.environ.get(LEVEL_VARIABLE, "").strip()
    if text.isdigit():
        return int(text)
    level = logging.getLevelName(text.upper()) if text else None
    return level if isinstance(level, int) else None  # getLevelName returns a string for unknown names


def _root(make_handler):
    """Return the "tls" logger, configuring it the first time. Safe across module reloads."""
    root = logging.getLogger(ROOT_NAME)
    if not getattr(root, "_tls_configured", False):
        root.propagate = False
        root.setLevel(_level_from_environment() or DEFAULT_LEVEL)
        handler = make_handler()
        handler.setFormatter(logging.Formatter(FORMAT))
        root.addHandler(handler)
        root._tls_configured = True
        path = os.environ.get(FILE_VARIABLE, "").strip()
        if path:
            _add_file_handler(root, path, logging.INFO)
    return root


def _add_file_handler(root, path, level):
    target = os.path.abspath(path)
    for handler in root.handlers:
        if isinstance(handler, logging.FileHandler) and handler.baseFilename == target:
            handler.setLevel(level)  # already attached: update it rather than duplicating output
            return handler
    os.makedirs(os.path.dirname(target), exist_ok=True)
    handler = logging.FileHandler(target, encoding="utf-8")
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter(FILE_FORMAT))
    root.addHandler(handler)
    return handler


class BaseLogger:
    """Logger access through classmethods. Subclass per host, then per tool.

    HOST and NAME build the logger name. A host class sets HOST, a tool sets NAME. Each subclass keeps
    its own logger: it is never inherited from a parent class.
    """

    HOST = ""
    NAME = ""

    @classmethod
    def make_handler(cls):
        """The handler for the "tls" logger. Override in a host class that needs somewhere other than stdout."""
        return logging.StreamHandler(sys.stdout)

    @classmethod
    def logger_name(cls):
        return ".".join(part for part in (ROOT_NAME, cls.HOST, cls.NAME) if part)

    @classmethod
    def logger_obj(cls):
        logger = cls.__dict__.get("_logger")  # not cls._logger: that would find a parent class's logger
        if logger is None:
            _root(cls.make_handler)
            logger = logging.getLogger(cls.logger_name())
            cls._logger = logger
        return logger

    @classmethod
    def set_level(cls, level):
        cls.logger_obj().setLevel(level)

    @classmethod
    def write_to_file(cls, path, level=logging.WARNING):
        """Also write to `path`. Calling it again for the same file updates the level, it does not duplicate output."""
        cls.logger_obj()
        return _add_file_handler(logging.getLogger(ROOT_NAME), path, level)

    @classmethod
    def log(cls, level, msg, *args, **kwargs):
        cls.logger_obj().log(level, msg, *args, **kwargs)

    @classmethod
    def debug(cls, msg, *args, **kwargs):
        cls.logger_obj().debug(msg, *args, **kwargs)

    @classmethod
    def info(cls, msg, *args, **kwargs):
        cls.logger_obj().info(msg, *args, **kwargs)

    @classmethod
    def warning(cls, msg, *args, **kwargs):
        cls.logger_obj().warning(msg, *args, **kwargs)

    @classmethod
    def error(cls, msg, *args, **kwargs):
        cls.logger_obj().error(msg, *args, **kwargs)

    @classmethod
    def critical(cls, msg, *args, **kwargs):
        cls.logger_obj().critical(msg, *args, **kwargs)

    @classmethod
    def exception(cls, msg, *args, **kwargs):
        cls.logger_obj().exception(msg, *args, **kwargs)


class MayaLogger(BaseLogger):
    HOST = "maya"


class BlenderLogger(BaseLogger):
    HOST = "blender"


class NukeLogger(BaseLogger):
    HOST = "nuke"


def get_logger(name):
    """A plain stdlib logger named tls.<name>, for code that prefers logging.Logger to the class API."""
    _root(BaseLogger.make_handler)
    return logging.getLogger("{}.{}".format(ROOT_NAME, name))
