"""The ``advanced-delegation.routes`` system prompt section: an agent is told to hand a lot of reading to the first
route, unasked, only while Model routes mode has routes and that route is known to read at least ``CHEAPER_BY`` times
cheaper than her own model."""

from __future__ import annotations

import shutil
from decimal import Decimal
from types import SimpleNamespace

import pytest

pytest.importorskip("agent.delegation_provider", reason="Hermes core without pluggable delegation providers")

import hermes_yaml as yaml  # noqa: E402

import advanced_delegation_plugin  # noqa: E402

PLUGIN = "advanced-delegation"
OPTIONS = [
    {"name": "fast", "description": "Cheap; reading and lookups.", "provider": "openrouter", "model": "fast-model"},
    {"name": "deep", "description": "Dear; hard problems.", "provider": "openrouter", "model": "deep-model"},
]
ROUTED = {"backend": "model_map", "backends": {"model_map": {"options": OPTIONS}}}
PRICES = {"main-model": "2", "fast-model": "0.1", "deep-model": "3", "cheap-main": "0.3"}


@pytest.fixture(autouse=True)
def priced(monkeypatch):
    """Core's price table, answering for the models of these tests and nothing else."""
    from agent import usage_pricing

    def entry(model, provider=None, base_url=None, api_key=None):
        return SimpleNamespace(input_cost_per_million=Decimal(PRICES[model])) if model in PRICES else None

    monkeypatch.setattr(usage_pricing, "get_pricing_entry", entry)
    advanced_delegation_plugin._price_unknown_until.clear()


def _told(tmp_path, monkeypatch, plugin_root, delegation, model="main-model", platform="cli"):
    from hermes_cli import plugins as plugins_mod
    from hermes_cli.plugins import PluginManager

    home = tmp_path / "os-home" / ".hermes"
    shutil.copytree(plugin_root, home / "plugins" / PLUGIN,
                    ignore=shutil.ignore_patterns("tests", "__pycache__", ".pytest_cache"))
    (home / "config.yaml").write_text(yaml.safe_dump(
        {"plugins": {"enabled": [PLUGIN]}, "delegation": delegation}), encoding="utf-8")
    empty_bundled = tmp_path / "bundled"
    empty_bundled.mkdir()
    monkeypatch.setattr(plugins_mod, "get_bundled_plugins_dir", lambda: empty_bundled)
    manager = PluginManager()
    manager.discover_and_load()
    try:
        rendered = manager.render_system_prompt_sections(
            {"profile_name": "default", "model": model, "provider": "openrouter", "platform": platform})
        return {item.id: item.content for item in rendered}
    finally:
        manager.unload()


def test_an_agent_whose_first_route_reads_far_cheaper_than_her_own_model_is_told_to_hand_reading_over(
        tmp_path, monkeypatch, plugin_root):
    told = _told(tmp_path, monkeypatch, plugin_root, ROUTED)
    assert told[advanced_delegation_plugin.SECTION] == advanced_delegation_plugin.ROUTES_GUIDANCE
    assert len(told[advanced_delegation_plugin.SECTION]) <= advanced_delegation_plugin.SECTION_MAX_CHARS


@pytest.mark.parametrize("delegation", [
    {},
    {"backend": "default", "backends": {"model_map": {"options": OPTIONS}}},
    {"backend": "model_map", "backends": {"model_map": {"options": []}}},
    {"backend": "model_map", "backends": {"model_map": {"options": [{"name": "broken"}]}}},
    {"backend": "profile_routes", "backends": {"profile_routes": {"profiles": [{"name": "coder", "description": "Code."}]}}},
], ids=["unset", "default mode", "no routes", "only a malformed route", "profile routes"])
def test_without_model_routes_the_agent_is_told_nothing(tmp_path, monkeypatch, plugin_root, delegation):
    assert advanced_delegation_plugin.SECTION not in _told(tmp_path, monkeypatch, plugin_root, delegation)


@pytest.mark.parametrize(("model", "options"), [
    ("fast-model", OPTIONS),
    ("cheap-main", OPTIONS),
    ("main-model", [OPTIONS[1], OPTIONS[0]]),
    ("unpriced-main", OPTIONS),
    ("main-model", [{**OPTIONS[0], "model": "unpriced-route"}, OPTIONS[1]]),
], ids=["her own model is the first route's", "her own model is only three times dearer", "a dearer model put first",
        "her own model has no known price", "the first route has no known price"])
def test_an_agent_is_told_nothing_unless_the_first_route_is_known_to_read_far_cheaper(
        tmp_path, monkeypatch, plugin_root, model, options):
    delegation = {"backend": "model_map", "backends": {"model_map": {"options": options}}}
    assert advanced_delegation_plugin.SECTION not in _told(tmp_path, monkeypatch, plugin_root, delegation, model=model)


def test_a_model_its_gateway_cannot_price_is_priced_by_its_own_id(monkeypatch):
    from agent import usage_pricing
    asked = []

    def entry(model, provider=None, base_url=None, api_key=None):
        asked.append(provider)
        return SimpleNamespace(input_cost_per_million=Decimal("2")) if provider == "openrouter" else None

    monkeypatch.setattr(usage_pricing, "get_pricing_entry", entry)
    assert advanced_delegation_plugin._input_price("vendor/model", "a-gateway") == Decimal("2")
    assert asked == ["a-gateway", "openrouter"]


def test_a_subagent_is_told_nothing_whatever_model_it_runs_on(tmp_path, monkeypatch, plugin_root):
    assert advanced_delegation_plugin.SECTION not in _told(tmp_path, monkeypatch, plugin_root, ROUTED, platform="subagent")


def test_a_model_with_no_known_price_is_not_looked_up_again_at_once_and_the_agent_s_own_is_not_looked_up_at_all(monkeypatch):
    from agent import usage_pricing
    asked = []

    def entry(model, provider=None, base_url=None, api_key=None):
        asked.append((model, provider))
        return None

    monkeypatch.setattr(usage_pricing, "get_pricing_entry", entry)
    advanced_delegation_plugin._price_unknown_until.clear()

    assert advanced_delegation_plugin._input_price("vendor/route-model", "a-gateway") is None
    assert advanced_delegation_plugin._input_price("vendor/route-model", "a-gateway") is None
    assert asked == [("vendor/route-model", "a-gateway"), ("vendor/route-model", "openrouter")]
