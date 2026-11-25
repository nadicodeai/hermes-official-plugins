"""Advanced Delegation: two extra ``delegation.backend`` modes for ``delegate_task``.

* ``model_map`` (``model_map.py``): the agent picks a named model route for each subagent.
* ``profile_routes`` (``profile_routes.py``): the agent runs each subagent as one of your Hermes profiles.

Plus ``hermes delegation config`` (``cli.py``) to pick the mode and edit its routes, the
``/delegation`` slash command (``slash.py``) to switch modes in a chat, and the ``model-routing``
skill (``skills/model-routing``, loaded as ``advanced-delegation:model-routing``), which guides the
agent in picking a model route per task, and a system prompt section (``advanced-delegation.routes``)
that tells the agent, while Model routes mode has routes, to hand a big job's parts to the cheapest
route that fits without being asked.

The bundled ``default`` backend stays in Hermes core. This module only registers. ``plugin.yaml``
declares ``requires_hermes: ">=0.22.5"``, which Hermes 0.22.0+ enforces before import; older cores
ignore that field, so on a core without pluggable delegation providers ``register`` logs one warning
and registers nothing (the skill included: it only makes sense with model routes available).
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

logger = logging.getLogger(__name__)

SKILL = "model-routing"
# Shown in skill listings; the 60-character limit applies (same text as the SKILL.md frontmatter).
SKILL_DESCRIPTION = "Before a big job, hand parts to subagents on cheaper models."
SKILL_MD = Path(__file__).resolve().parent / "skills" / SKILL / "SKILL.md"
SECTION = "advanced-delegation.routes"
SECTION_MAX_CHARS = 640
#: The agent is told to hand reading over unasked only while her own model's input price is at least this many
#: times the first route's. Below that, briefing the subagents and reading their answers costs her more than the
#: reading saves: measured on an agent at 2 USD per million input tokens, a route at 1 USD made the job dearer and
#: a route at 0.10 USD made it cheaper.
CHEAPER_BY = 5
#: What that agent is told in every chat while Model routes mode has routes: without it she does the whole job on
#: her own model, since nothing else she always reads says a cheaper route exists for part of it. It names the
#: tool's `option` as a condition, since a chat keeps these words after its tools are rebuilt on another mode.
ROUTES_GUIDANCE = (
    "# Subagents on cheaper models\n\n"
    "While `delegate_task` has an `option`, its values are other models, from the cheapest. What you read "
    "yourself costs many times more than what the first one reads.\n\n"
    "Without being asked, hand each part of a job a cheaper model can do to subagents on the first `option` that "
    "fits: a lot of reading (ten long documents or more), lookups, the same step over many items. Each reports the "
    "facts you list, with their exact words and where they are. You compare, judge, check what surprises you, and "
    "answer. If an option is refused, do it yourself.\n\n"
    "A small job, or exact work a short program does, you do yourself."
)


#: A model whose price could not be found is not looked up again for this long: the lookup can wait on a price
#: catalog that does not answer, and it runs while a new chat's first message waits.
PRICE_UNKNOWN_FOR_SECONDS = 600.0
_price_unknown_until: dict[str, float] = {}


def _input_price(model: str, provider: str = "", base_url: str = ""):
    """USD per million input tokens that core's price tables give ``model``, else ``None``. A gateway core cannot
    price by its name is priced by the model's own id, as the routers list it."""
    if not model or time.monotonic() < _price_unknown_until.get(model, 0.0):
        return None
    try:
        from agent.usage_pricing import get_pricing_entry
    except ImportError:
        return None
    for known_by, at in ((provider, base_url), ("openrouter", "")) if "/" in model else ((provider, base_url),):
        try:
            entry = get_pricing_entry(model, provider=known_by or None, base_url=at or None)
        except Exception:  # noqa: BLE001 - a price table that cannot be read leaves the price unknown
            continue
        price = getattr(entry, "input_cost_per_million", None)
        if price:
            return price
    _price_unknown_until[model] = time.monotonic() + PRICE_UNKNOWN_FOR_SECONDS
    return None


def routes_guidance(session_info) -> str:
    """The system prompt section: ``ROUTES_GUIDANCE`` while this profile runs Model routes mode and the first
    route's model is known to read at least ``CHEAPER_BY`` times cheaper than the agent's own, else nothing: an
    unknown price, or a first route that is not that much cheaper, is no reason to move her reading. Rendered once
    per new session, like the tool list that carries the routes."""
    if str(session_info.get("platform") or "") == "subagent":
        return ""  # a subagent is the one sent to read, and has no delegate_task to hand it on with
    from . import store
    from .model_map import BACKEND, configured_options
    section = store.delegation_section()
    if store.current_mode(section) != BACKEND:
        return ""
    backends = section.get("backends")
    settings = backends.get(BACKEND) if isinstance(backends, dict) else None
    options = configured_options(settings) if isinstance(settings, dict) else {}
    if not options:
        return ""
    first = next(iter(options.values()))["route"]
    cheapest = _input_price(str(first.get("model") or ""), str(first.get("provider") or ""), str(first.get("base_url") or ""))
    if cheapest is None:
        return ""
    hers = _input_price(str(session_info.get("model") or ""), str(session_info.get("provider") or ""))
    if hers is None or hers < CHEAPER_BY * cheapest:
        return ""
    return ROUTES_GUIDANCE


def register(ctx) -> None:
    try:
        from .model_map import ModelMapDelegationProvider
        from .profile_routes import ProfilesDelegationProvider
    except ModuleNotFoundError as exc:
        if exc.name != "agent.delegation_provider":
            raise
        logger.warning(
            "advanced-delegation needs a Hermes core with pluggable delegation providers "
            "(agent.delegation_provider); update Hermes. The plugin is inactive until then.")
        return
    ctx.register_delegation_provider(ModelMapDelegationProvider())
    ctx.register_delegation_provider(ProfilesDelegationProvider())
    from . import cli, slash
    ctx.register_command("delegation", slash.make_handler(ctx),
                         description="Show/switch delegation mode or model-route preset (next session; --now for this chat)",
                         args_hint="[default|model_map|profile_routes|preset NAME] [--now]")
    ctx.register_cli_command(
        name="delegation", help="Delegation modes: default, model routes, profile routes",
        setup_fn=cli.setup_parser, handler_fn=cli.handle,
        description="Pick how delegate_task routes subagents and edit the routes: "
                    "`hermes delegation config` (or `--show` to print the current setup).")
    # Last, and guarded: a skill that fails to register must never take the delegation modes down.
    try:
        ctx.register_skill(name=SKILL, path=SKILL_MD, description=SKILL_DESCRIPTION)
    except Exception as exc:
        logger.warning("advanced-delegation: could not register the %s skill (%s); the delegation modes "
                       "still work.", SKILL, exc)
    try:
        ctx.register_system_prompt_section(SECTION, routes_guidance, max_chars=SECTION_MAX_CHARS)
    except Exception as exc:
        logger.warning("advanced-delegation: could not register the %s prompt section (%s); the delegation "
                       "modes still work.", SECTION, exc)
