"""The public MCP tool surface of the raven-ar9 oracle server.

Builds one independently-addressable namespace per registered ARE app and publishes
ONLY each app's legitimate public ``@app_tool`` surface, every call routed through
the deterministic clock in ``clock.py``.

Two invariants are enforced here, both fail-closed:

ONE  Discovery is allow-list driven. A method reaches the surface only because ARE
     itself marked it as an app tool. If no ARE discovery API can be found, this
     module raises instead of falling back to "every public attribute" — guessing
     would publish ``get_state`` and friends, i.e. hand the agent the world state.

TWO  A denied name is never published. Private/dunder names, state dumps, answer or
     ground-truth endpoints, and anything carrying a clock-tamper token are refused,
     and the refusals are returned alongside the table so the self-test can assert
     on them rather than trusting this docstring.

Public tool naming is ARE's own: ``f"{app.name}__{function}"``. Because the name is
the APP INSTANCE name and not its class, two instances of one class (this universe
ships ``Messages`` and ``Chats``, both ``MessagingAppV2``; ``ContactsApp`` and
``InternalContacts``, both contacts apps) get disjoint namespaces with no shadowing.
Collisions are a hard error, not a last-writer-wins overwrite.
"""

from __future__ import annotations

import functools
import inspect
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from typing import Any

from raven_ar9.clock import CLOCK_TAMPER_TOKENS, DeterministicClock

NAME_SEPARATOR = "__"

DENIED_EXACT_NAMES: frozenset[str] = frozenset(
    {
        "get_state",
        "set_state",
        "load_state",
        "save_state",
        "dump_state",
        "state",
        "get_app_state",
        "reset_state",
        "disclose",
        "get_ground_truth",
        "ground_truth",
        "answer",
        "solution",
        "oracle",
        "validate",
        "get_tools",
        "get_tools_with_descriptions",
        "get_implemented_protocols",
        "register_to_env",
        "time",
        "tick",
        "now",
        "get_collection",
        "collection",
        "list_collections",
    }
)

DENIED_SUBSTRINGS: tuple[str, ...] = (
    "disclose",
    "ground_truth",
    "groundtruth",
    "_gt_",
    "gt_snapshot",
    "state_dump",
    "dump_state",
    "debug",
    "cheat",
    "internal_only",
    "_private",
    "tamper",
)

TOOL_MARKER_ATTRS: tuple[str, ...] = (
    "__app_tool__",
    "_is_app_tool",
    "is_app_tool",
    "_app_tool",
    "__is_app_tool__",
    "__tool__",
)


class ToolDiscoveryError(RuntimeError):
    """Raised when the app's tool surface cannot be established from ARE metadata."""


class ToolCollision(RuntimeError):
    """Raised when two apps would publish the same public tool name."""


@dataclass(frozen=True)
class ToolSpec:
    public_name: str
    app_name: str
    function_name: str
    description: str
    target: Callable[..., Any]


@dataclass(frozen=True)
class SurfaceTable:
    tools: tuple[ToolSpec, ...]
    apps: tuple[str, ...]
    refused: tuple[tuple[str, str, str], ...]

    def names(self) -> tuple[str, ...]:
        return tuple(spec.public_name for spec in self.tools)

    def names_for(self, app_name: str) -> tuple[str, ...]:
        return tuple(s.public_name for s in self.tools if s.app_name == app_name)


def refusal_reason(function_name: str) -> str | None:
    """Why ``function_name`` may not be published, or ``None`` if it may be.

    Order matters only for the reported reason, not the verdict: any single hit is
    disqualifying. Clock tokens are checked against the same vocabulary the scorer's
    tamper detector uses, so the surface cannot publish a tool the scorer would then
    flag as tampering.
    """
    if not function_name or function_name.startswith("_"):
        return "private_or_dunder"
    lowered = function_name.lower()
    if lowered in DENIED_EXACT_NAMES:
        return "denied_exact_name"
    for token in CLOCK_TAMPER_TOKENS:
        if token in lowered:
            return f"clock_tamper_token:{token}"
    for token in DENIED_SUBSTRINGS:
        if token in lowered:
            return f"denied_substring:{token}"
    return None


def _candidate_names(app: Any) -> list[str]:
    """Function names ARE itself marks as app tools, in a stable order."""
    found: list[str] = []

    getter = getattr(app, "get_tools", None)
    if callable(getter):
        try:
            for tool in getter() or []:
                name = (
                    getattr(tool, "function_name", None)
                    or getattr(tool, "name", None)
                    or getattr(tool, "__name__", None)
                )
                if isinstance(name, str) and name:
                    found.append(name.split(NAME_SEPARATOR)[-1])
        except Exception as exc:  # noqa: BLE001 - fall through to marker scan
            found = []
            _ = exc

    if not found:
        for name, member in inspect.getmembers(type(app)):
            if not callable(member):
                continue
            if any(getattr(member, attr, False) for attr in TOOL_MARKER_ATTRS):
                found.append(name)

    if not found:
        raise ToolDiscoveryError(
            f"app {getattr(app, 'name', app)!r} exposed no ARE tool metadata via "
            f"get_tools() or {TOOL_MARKER_ATTRS}; refusing to guess a surface"
        )

    seen: set[str] = set()
    ordered: list[str] = []
    for name in found:
        if name not in seen:
            seen.add(name)
            ordered.append(name)
    return sorted(ordered)


def _describe(target: Callable[..., Any], app_name: str, function_name: str) -> str:
    doc = inspect.getdoc(target) or ""
    first = doc.strip()
    if first:
        return first
    return f"{function_name} on the {app_name} app."


def build_surface(apps: Sequence[Any]) -> SurfaceTable:
    """Enumerate the publishable surface of ``apps`` with collisions as hard errors."""
    tools: list[ToolSpec] = []
    refused: list[tuple[str, str, str]] = []
    app_names: list[str] = []
    claimed: dict[str, str] = {}

    for app in apps:
        app_name = getattr(app, "name", None) or type(app).__name__
        if app_name in app_names:
            raise ToolCollision(f"two registered apps share the instance name {app_name!r}")
        app_names.append(app_name)

        for function_name in _candidate_names(app):
            reason = refusal_reason(function_name)
            if reason is not None:
                refused.append((app_name, function_name, reason))
                continue
            target = getattr(app, function_name, None)
            if not callable(target):
                refused.append((app_name, function_name, "not_callable_on_instance"))
                continue
            public_name = f"{app_name}{NAME_SEPARATOR}{function_name}"
            if public_name in claimed:
                raise ToolCollision(
                    f"public tool name {public_name!r} claimed by both "
                    f"{claimed[public_name]!r} and {app_name!r}"
                )
            claimed[public_name] = app_name
            tools.append(
                ToolSpec(
                    public_name=public_name,
                    app_name=app_name,
                    function_name=function_name,
                    description=_describe(target, app_name, function_name),
                    target=target,
                )
            )

    return SurfaceTable(
        tools=tuple(tools), apps=tuple(app_names), refused=tuple(refused)
    )


def _public_signature(target: Callable[..., Any]) -> inspect.Signature:
    signature = inspect.signature(target)
    kept = [
        p
        for name, p in signature.parameters.items()
        if name != "self" and p.kind not in (p.VAR_POSITIONAL, p.VAR_KEYWORD)
    ]
    return signature.replace(parameters=kept, return_annotation=inspect.Signature.empty)


def make_metered_tool(spec: ToolSpec, clock: DeterministicClock) -> Callable[..., Any]:
    """Wrap one app tool so every invocation goes through the clock.

    The wrapper carries the underlying signature so the MCP layer can build the
    argument schema, and it is the ONLY way the tool is reachable: there is no
    unmetered route to ``spec.target`` on the published surface.
    """

    @functools.wraps(spec.target)
    def invoke(*args: Any, **kwargs: Any) -> Any:
        result, _ = clock.meter(
            tool=spec.public_name,
            app=spec.app_name,
            function=spec.function_name,
            body=lambda: spec.target(*args, **kwargs),
        )
        return result

    invoke.__name__ = spec.public_name
    invoke.__qualname__ = spec.public_name
    invoke.__doc__ = spec.description
    try:
        invoke.__signature__ = _public_signature(spec.target)  # type: ignore[attr-defined]
    except (TypeError, ValueError):
        pass
    return invoke


def _adder(server: Any) -> Callable[..., Any]:
    for name in ("add_tool", "tool", "register_tool"):
        candidate = getattr(server, name, None)
        if callable(candidate):
            return candidate
    raise ToolDiscoveryError(
        "MCP server object exposes none of add_tool/tool/register_tool; cannot publish a surface"
    )


def register_surface(
    server: Any, table: SurfaceTable, clock: DeterministicClock
) -> tuple[str, ...]:
    """Publish ``table`` on ``server``, returning the published names in order."""
    add = _adder(server)
    published: list[str] = []
    for spec in table.tools:
        fn = make_metered_tool(spec, clock)
        try:
            add(fn, name=spec.public_name, description=spec.description)
        except TypeError:
            add(fn)
        published.append(spec.public_name)
    return tuple(published)


def create_mcp_server(server_name: str) -> Any:
    """An MCP server object across the 1.x/2.x rename of FastMCP -> MCPServer."""
    errors: list[str] = []
    try:
        from mcp.server.fastmcp import FastMCP

        return FastMCP(server_name)
    except Exception as exc:  # noqa: BLE001 - try the 2.x name next
        errors.append(f"mcp.server.fastmcp.FastMCP: {exc}")
    try:
        from mcp.server.mcpserver import MCPServer

        return MCPServer(server_name)
    except Exception as exc:  # noqa: BLE001
        errors.append(f"mcp.server.mcpserver.MCPServer: {exc}")
    raise ToolDiscoveryError("no usable MCP server implementation: " + "; ".join(errors))


def audit(table: SurfaceTable, expected_apps: Iterable[str] | None = None) -> dict[str, Any]:
    """The machine-readable surface audit the self-test asserts on."""
    names = table.names()
    duplicates = sorted({n for n in names if names.count(n) > 1})
    leaked = sorted(n for n in names if refusal_reason(n.split(NAME_SEPARATOR, 1)[-1]))
    per_app = {app: len(table.names_for(app)) for app in table.apps}
    missing = sorted(set(expected_apps or ()) - set(table.apps))
    unexpected = sorted(set(table.apps) - set(expected_apps or table.apps))
    return {
        "apps": list(table.apps),
        "app_count": len(table.apps),
        "tool_count": len(names),
        "tools_per_app": per_app,
        "duplicate_tool_names": duplicates,
        "leaked_denied_tools": leaked,
        "refused": [
            {"app": app, "function": fn, "reason": reason} for app, fn, reason in table.refused
        ],
        "missing_expected_apps": missing,
        "unexpected_apps": unexpected,
    }
