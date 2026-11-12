"""Start a DCC with the environment that makes it load the pipeline.

The environment is built for the child process only; nothing persistent is written. This is the one place that
decides it, so the `launch` command and the tray app's Launch button start a host the same way. AYON, which
launches hosts itself, supplies the same variables: TLS_PIPELINE, and the host's bootstrap folder in the
variable that host reads (`HostInfo.discovery_variable`).
"""
import os
import subprocess
import sys
from typing import Mapping, Sequence

from .api import expose_environment
from .clone import override_source_folder
from .config import LocalConfig
from .errors import LocaliserError
from .hosts import HOSTS, find_executable
from .resolve import ROOT_VARIABLE
from .sync import dev_release, pipeline_root, source_variable, startup_release


def launch_environment(
    host: str, series: str, config: LocalConfig, environ: Mapping[str, str] | None = None
) -> dict[str, str]:
    """The environment for one launch of `host` `series`: `environ` (a pin, a dev source or shared folders may
    already be in it) plus the pipeline root and the bootstrap discovery variable. Reads local state only."""
    env = dict(os.environ if environ is None else environ)
    chosen = override_source_folder(config, host, series)  # the tray app's override; an explicit source wins
    if chosen is not None and not env.get(source_variable(host), "").strip():
        env[source_variable(host)] = str(chosen)
    if env.get(source_variable(host), "").strip():
        # The stub in the DCC runs the source where it is; check now that it can.
        dev_release(host, series, config, env[source_variable(host)], env)
    else:
        expose_environment(startup_release(host, series, config, env), env)
    root = pipeline_root(env)
    variable = HOSTS[host].discovery_variable
    existing = env.get(variable)
    env[ROOT_VARIABLE] = str(root)
    env[variable] = str(root / "bootstrap" / host)
    # Blender accepts one system scripts directory; Maya and Nuke accept search paths.
    if host != "blender" and existing:
        env[variable] += os.pathsep + existing
    return env


def launch_host(
    host: str,
    series: str,
    config: LocalConfig,
    environ: Mapping[str, str] | None = None,
    command: Sequence[str] | None = None,
) -> subprocess.Popen:
    """Start the installed `host` `series` (or `command`) without waiting for it, and return the process.

    Logging is the host's own business (its console or script editor, and the files `tls_common` writes). The
    caller (a tray app started from a shortcut) usually has no console, and a host that inherits standard streams
    that don't exist fails to load the pipeline, so they are pointed at nothing. The host gets a hidden console
    rather than none (CREATE_NO_WINDOW, not DETACHED_PROCESS): without one, every console program the host
    starts, Nuke's frame server for one, opens its own empty window. Python in the host is told to write UTF-8,
    so a toolchain printing a symbol can't fail on the Windows code page."""
    env = launch_environment(host, series, config, environ)
    env.setdefault("PYTHONIOENCODING", "utf-8")
    if command is None:
        program = find_executable(host, series)
        if program is None:
            raise LocaliserError(f"{HOSTS[host].display_name} {series} was not found in the standard install folders")
        command = [str(program)]
    flags = (subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP) if sys.platform.startswith("win") else 0
    return subprocess.Popen(
        list(command), env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        close_fds=True, creationflags=flags,
    )
