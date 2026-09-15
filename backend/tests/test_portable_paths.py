"""Configuration follows the checkout location without changing stored data."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy.engine import make_url

from app import cli, config
from app.config import Settings

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("working_directory", ["backend", "elsewhere"])
@pytest.mark.parametrize("custom", [False, True])
def test_relative_paths_use_project_root(monkeypatch, tmp_path, working_directory, custom):
    project = tmp_path / "checkout with spaces"
    folder = project / "backend" if working_directory == "backend" else tmp_path / "elsewhere"
    folder.mkdir(parents=True)
    monkeypatch.setattr(config, "ROOT", project)
    monkeypatch.chdir(folder)
    values = (
        {
            "database_url": "sqlite:///.runtime/current/team-nav.db",
            "key_file": ".runtime/current/credential.key",
            "setup_token_file": ".runtime/current/setup-token",
            "frontend_dist": "frontend/dist-next",
        }
        if custom
        else {}
    )

    settings = Settings(_env_file=None, **values)

    assert Path(make_url(settings.resolved_database_url).database) == project / (
        ".runtime/current/team-nav.db" if custom else ".runtime/team-nav.db"
    )
    assert settings.key_file == project / (
        ".runtime/current/credential.key" if custom else ".runtime/secrets/credential.key"
    )
    assert settings.setup_token_file == project / (
        ".runtime/current/setup-token" if custom else ".runtime/secrets/setup-token"
    )
    assert settings.frontend_dist == project / ("frontend/dist-next" if custom else "frontend/dist")
    assert not (folder / ".runtime").exists()


@pytest.mark.parametrize(
    "url",
    [
        "sqlite://",
        "sqlite:///:memory:",
        "sqlite:///file:shared?mode=memory&cache=shared&uri=true",
    ],
)
def test_sqlite_memory_and_native_uri_are_preserved(url):
    assert Settings(_env_file=None, database_url=url).resolved_database_url == url


def test_sqlite_driver_and_query_are_preserved(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "ROOT", tmp_path)
    settings = Settings(
        _env_file=None,
        database_url="sqlite+pysqlite:///.runtime/test.db?timeout=12&check_same_thread=false",
    )
    url = make_url(settings.resolved_database_url)
    assert url.drivername == "sqlite+pysqlite"
    assert Path(url.database) == tmp_path / ".runtime/test.db"
    assert dict(url.query) == {"timeout": "12", "check_same_thread": "false"}


def test_explicit_absolute_locations_remain_supported(monkeypatch, tmp_path):
    project = tmp_path / "checkout"
    storage = tmp_path / "external-storage"
    monkeypatch.setattr(config, "ROOT", project)
    settings = Settings(
        _env_file=None,
        database_url=f"sqlite:///{(storage / 'test.db').as_posix()}",
        key_file=storage / "key",
        setup_token_file=storage / "token",
        frontend_dist=storage / "frontend",
    )
    assert Path(make_url(settings.resolved_database_url).database) == storage / "test.db"
    assert settings.key_file == storage / "key"
    assert settings.setup_token_file == storage / "token"
    assert settings.frontend_dist == storage / "frontend"


def test_postgresql_url_and_relative_password_file(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "ROOT", tmp_path)
    password = tmp_path / "database-password"
    password.write_text("test-only-file-password", encoding="utf-8")
    database_url = "postgresql+psycopg://test:original%40password@db:5432/nav?sslmode=require"
    plain = Settings(_env_file=None, database_url=database_url)
    assert plain.resolved_database_url == database_url
    settings = Settings(_env_file=None, database_url=database_url, database_password_file="database-password")
    result = make_url(settings.resolved_database_url)
    assert result.password == "test-only-file-password"
    assert result.host == "db" and result.database == "nav"
    assert result.query["sslmode"] == "require"
    assert settings.database_password_file == password


def test_postgresql_client_uses_configured_program_files(monkeypatch, tmp_path):
    installation = tmp_path / "custom programs"
    executable = installation / "PostgreSQL/16/bin/pg_dump.exe"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"")
    monkeypatch.setenv("ProgramFiles", str(installation))
    monkeypatch.setattr(cli.shutil, "which", lambda name: None)
    assert cli.pg_tool("pg_dump") == str(executable)


RELOCATION_SMOKE = r"""
import sys
from pathlib import Path
from sqlalchemy.engine import make_url
from fastapi.testclient import TestClient
from app.cli import initialize
from app.config import ROOT, Settings
from app.main import create_app

settings = Settings()
assert Path(make_url(settings.database_url).database).is_relative_to(ROOT)
assert settings.key_file.is_relative_to(ROOT)
assert settings.setup_token_file.is_relative_to(ROOT)
assert settings.frontend_dist == ROOT / 'frontend/dist'
initialize(settings)
origin = settings.origin_list[0]
with TestClient(create_app(settings), base_url=origin, headers={'Origin': origin}) as client:
    assert client.get('/').text == 'portable frontend'
    if sys.argv[1] == 'create':
        assert client.get('/api/v1/setup/status').json()['needs_setup'] is True
        response = client.post('/api/v1/setup', json={
            'username': 'portable_user', 'display_name': 'Portable user',
            'password': 'portable-test-only-password', 'workspace_name': '',
            'token': settings.setup_token_file.read_text(),
        })
        assert response.status_code == 201, response.text
        client.headers['X-CSRF-Token'] = response.json()['csrf_token']
        response = client.post('/api/v1/resources', json={
            'scope': 'personal', 'type': 'bookmark', 'name': 'Survives relocation',
            'endpoints': [{'url': 'https://portable.example/'}],
        })
        assert response.status_code == 201, response.text
        endpoint = response.json()['endpoints'][0]['id']
        response = client.post(f'/api/v1/endpoints/{endpoint}/credentials', json={
            'name': 'Portable credential', 'username': 'portable-reader',
            'password': 'test-only-encrypted-value',
        })
        assert response.status_code == 201, response.text
    else:
        assert client.get('/api/v1/setup/status').json()['needs_setup'] is False
        response = client.post('/api/v1/auth/login', json={
            'username': 'portable_user', 'password': 'portable-test-only-password',
        })
        assert response.status_code == 200, response.text
        client.headers['X-CSRF-Token'] = response.json()['csrf_token']
        resources = client.get('/api/v1/resources?view=personal').json()['items']
        assert len(resources) == 1 and resources[0]['name'] == 'Survives relocation'
        endpoint = resources[0]['endpoints'][0]['id']
        account = client.get(f'/api/v1/endpoints/{endpoint}/credentials').json()[0]
        response = client.post(f"/api/v1/credentials/{account['id']}/access", json={
            'field': 'password', 'purpose': 'reveal',
        })
        assert response.status_code == 200, response.text
        assert response.json()['value'] == 'test-only-encrypted-value'
print('portable paths, persisted account and credential verified')
"""


@pytest.mark.parametrize("with_env_file", [False, True])
def test_checkout_relocation_preserves_database_and_credentials(tmp_path, with_env_file):
    original = tmp_path / "first checkout"
    relocated = tmp_path / "second checkout with spaces"
    outside = tmp_path / "unrelated shell directory"
    outside.mkdir()
    for directory in ("app", "migrations"):
        shutil.copytree(
            PROJECT_ROOT / "backend" / directory,
            original / "backend" / directory,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
    shutil.copyfile(PROJECT_ROOT / "backend/alembic.ini", original / "backend/alembic.ini")
    (original / "frontend/dist").mkdir(parents=True)
    (original / "frontend/dist/index.html").write_text("portable frontend", encoding="utf-8")
    if with_env_file:
        shutil.copyfile(PROJECT_ROOT / ".env.example", original / ".env")

    def run(checkout, stage):
        environment = {key: value for key, value in os.environ.items() if not key.startswith("TEAM_NAV_")}
        environment.update(PYTHONPATH=str(checkout / "backend"), PYTHONUTF8="1")
        result = subprocess.run(
            [sys.executable, "-c", RELOCATION_SMOKE, stage],
            cwd=outside,
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
            timeout=40,
        )
        assert result.returncode == 0, result.stdout + result.stderr

    run(original, "create")
    shutil.copytree(original, relocated)
    run(relocated, "read")
    assert not (outside / ".runtime").exists()
