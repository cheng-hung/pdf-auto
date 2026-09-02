"""Configuration-path resolution for :mod:`pdf_auto`.

The workflow reads its runtime settings from an INI file. This module resolves
*which* INI to use, in priority order, without importing any beamline
dependency (import-safe for the offline test suite):

1. an explicit path passed on the command line (``--config``);
2. the ``PDF_AUTO_CONFIG`` environment variable;
3. the beamline deployment path (``DEFAULT_CONFIG_PATH``) **if it exists**; and
4. the template shipped inside the package (``pdf_auto/data/pdf_auto_config.ini``).

The packaged template keeps structural defaults and the conventional ZMQ socket
names, but its ``[PATH]`` roots are placeholders — a real deployment overrides
it via ``--config`` or ``PDF_AUTO_CONFIG``.
"""

from __future__ import annotations

import os
from importlib.resources import as_file, files
from pathlib import Path

# Environment variable that overrides the default config path.
CONFIG_ENV_VAR = "PDF_AUTO_CONFIG"

# Beamline deployment INI. Used as a fallback only when it exists, so installs
# elsewhere do not depend on this absolute path.
DEFAULT_CONFIG_PATH = Path("/home/xf28id1/src/pdf-auto/pdf_auto_config.ini")

# Packaged template filename (under pdf_auto/data/).
_PACKAGED_CONFIG_NAME = "pdf_auto_config.ini"


def packaged_config_path() -> Path:
    """Return the filesystem path to the INI template shipped in the package.

    ``importlib.resources`` may extract the file from a zip; ``as_file`` yields
    a real path. For a normal (unzipped) install this is a stable path inside
    the installed package, so returning it directly is fine.
    """
    resource = files("pdf_auto.data").joinpath(_PACKAGED_CONFIG_NAME)
    with as_file(resource) as path:
        return Path(path)


def resolve_config_path(explicit: str | os.PathLike[str] | None = None) -> Path:
    """Resolve the INI path to use, applying the documented precedence.

    Parameters
    ----------
    explicit:
        A path from ``--config`` (or a caller). If given, it wins unconditionally
        and is returned as-is (even if missing, so the caller sees a clear error).
    """
    if explicit is not None:
        return Path(explicit)

    env_value = os.environ.get(CONFIG_ENV_VAR)
    if env_value:
        return Path(env_value)

    if DEFAULT_CONFIG_PATH.exists():
        return DEFAULT_CONFIG_PATH

    return packaged_config_path()
