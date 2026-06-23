from __future__ import annotations

from pathlib import Path

from claude_backup.discovery import discover_sources


def test_discover_sources_uses_env_and_native_home_only_when_existing(tmp_path):
    env_config = tmp_path / "env-config"
    env_projects = env_config / "projects"
    env_projects.mkdir(parents=True)

    home = tmp_path / "home"
    native_projects = home / ".claude" / "projects"
    native_projects.mkdir(parents=True)

    missing_config = tmp_path / "missing-config"
    assert not (missing_config / "projects").exists()

    found = discover_sources(
        env={"CLAUDE_CONFIG_DIR": str(env_config)},
        home=home,
        platform_system="Linux",
        wsl=False,
    )

    assert found == [env_projects, native_projects]


def test_discover_sources_dedupes_same_env_and_native_path(tmp_path):
    home = tmp_path / "home"
    native_projects = home / ".claude" / "projects"
    native_projects.mkdir(parents=True)

    found = discover_sources(
        env={"CLAUDE_CONFIG_DIR": str(home / ".claude")},
        home=home,
        platform_system="Linux",
        wsl=False,
    )

    assert found == [native_projects]


def test_discover_sources_ignores_missing_candidates(tmp_path):
    home = tmp_path / "home"
    home.mkdir()

    found = discover_sources(
        env={"CLAUDE_CONFIG_DIR": str(tmp_path / "missing-config")},
        home=home,
        platform_system="Linux",
        wsl=False,
    )

    assert found == []
