"""Exception types."""


class LocaliserError(Exception):
    """Base class for every error the localiser raises on purpose."""


class ConfigError(LocaliserError):
    """Malformed or unsupported config or manifest."""


class UnsupportedSeriesError(ConfigError):
    """The studio config has no release for this host or DCC series."""


class ReleaseUnavailableError(LocaliserError):
    """The requested release cannot be resolved or fetched. The message names the host and release."""

    def __init__(self, message, *, host=None, release_id=None):
        details = [message]
        if host:
            details.append(f"host={host}")
        if release_id:
            details.append(f"release={release_id}")
        super().__init__("; ".join(details))


class VerificationError(LocaliserError):
    """Checksum or identity verification failed."""


class UnsafeArchiveError(LocaliserError):
    """The archive contains a member that must not be extracted."""


class LockTimeoutError(LocaliserError):
    """Another process held the lock for longer than the timeout."""


class PublishError(LocaliserError):
    """The publisher refused or failed to publish a release."""
