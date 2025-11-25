"""Centralized user-facing error messages for registry-related operations."""


class ErrorMessages:
    TOOL_NOT_ALLOWED = (
        "Local tool '{module_path}' is not permitted by security policy. "
        "Add an allowlist entry under default.local_tools_allowlist in security.yaml "
        "or use a gateway-managed tool."
    )


__all__ = ["ErrorMessages"]
