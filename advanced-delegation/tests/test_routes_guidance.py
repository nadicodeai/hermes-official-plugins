"""The ``advanced-delegation.routes`` system prompt section: what the agent is told in every chat while Model
routes mode has routes, so she hands a big job's parts to a cheaper route without being asked."""

from __future__ import annotations

import re
import shutil

import pytest

pytest.importorskip("agent.delegation_provider", reason="Hermes core without pluggable delegation providers")

import hermes_yaml as yaml  # noqa: E402

import advanced_delegation_plugin  # noqa: E402

PLUGIN = "advanced-delegation"
OPTIONS = [
    {"name": "fast", "description": "Cheap; reading and lookups.", "provider": "openrouter", "model": "fast-model"},
    {"name": "deep", "description": "Dear; hard problems.", "provider": "openrouter", "model": "deep-model"},
]


def _rendered(tmp_path, monkeypatch, plugin_root, delegation):
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
        return {item.id: item.content for item in manager.render_system_prompt_sections({"profile_name": "default"})}
    finally:
        manager.unload()


def test_with_routes_the_agent_is_told_to_hand_big_jobs_to_the_cheapest_route_unasked(tmp_path, monkeypatch, plugin_root):
    sections = _rendered(tmp_path, monkeypatch, plugin_root,
                         {"backend": "model_map", "backends": {"model_map": {"options": OPTIONS}}})
    text = sections[advanced_delegation_plugin.SECTION]
    assert "Without being asked, hand them to subagents" in text
    assert "listed from the cheapest" in text
    assert "three or more long documents or sources" in text
    assert "name the first `option` that fits on every task" in text
    assert "wait for the results" in text
    assert "exact work on numbers or tables that a short program does, you do yourself" in text
    assert len(text) <= advanced_delegation_plugin.SECTION_MAX_CHARS
    assert not re.search(r"\bHermes\b|\bNous\b", text)


@pytest.mark.parametrize("delegation", [
    {},
    {"backend": "default", "backends": {"model_map": {"options": OPTIONS}}},
    {"backend": "model_map", "backends": {"model_map": {"options": []}}},
    {"backend": "model_map", "backends": {"model_map": {"options": [{"name": "broken"}]}}},
    {"backend": "profile_routes", "backends": {"profile_routes": {"profiles": [{"name": "coder", "description": "Code."}]}}},
], ids=["unset", "default mode", "no routes", "only a malformed route", "profile routes"])
def test_without_model_routes_the_agent_is_told_nothing(tmp_path, monkeypatch, plugin_root, delegation):
    assert advanced_delegation_plugin.SECTION not in _rendered(tmp_path, monkeypatch, plugin_root, delegation)
