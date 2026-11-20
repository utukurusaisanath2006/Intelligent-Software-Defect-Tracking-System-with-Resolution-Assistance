"""Database migration integration and schema integrity tests."""

import os
import sqlite3
import pytest
from alembic import command
from alembic.config import Config
from app import create_app
from extensions import db
from models.user import User
from models.project import Project, ProjectMembership
from models.issue import Issue


@pytest.fixture(scope='function')
def temp_db_path(tmp_path):
    """Path to an isolated temporary SQLite database for migration testing."""
    return str(tmp_path / 'temp_migration_test.db')


def test_migration_upgrade_and_downgrade_lifecycle(temp_db_path, monkeypatch):
    """Test full upgrade and downgrade cycle on a fresh database using Alembic."""
    uri = f"sqlite:///{temp_db_path.replace(os.sep, '/')}"
    monkeypatch.setenv('DATABASE_URL', uri)
    test_app = create_app('development')

    with test_app.app_context():
        # Configure alembic to point to the migrations directory
        alembic_cfg = Config(os.path.join(test_app.root_path, 'migrations', 'alembic.ini'))
        alembic_cfg.set_main_option('script_location', os.path.join(test_app.root_path, 'migrations'))
        alembic_cfg.set_main_option('sqlalchemy.url', uri)

        # 1. Run upgrade to head
        command.upgrade(alembic_cfg, 'head')

        # Verify all 10 application tables plus alembic_version exist
        conn = sqlite3.connect(temp_db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
        created_tables = set(r[0] for r in cursor.fetchall())
        conn.close()

        expected_tables = {
            'activities', 'attachments', 'comments', 'issues', 'notifications',
            'project_memberships', 'projects', 'releases', 'sprints', 'users',
            'alembic_version'
        }
        assert expected_tables.issubset(created_tables), f"Missing tables: {expected_tables - created_tables}"

        # 2. Insert records into the freshly migrated schema to ensure constraints and FKs function
        user = User(username='mig_user', email='mig@test.dev', first_name='Mig', last_name='Test', role=User.ROLE_ADMIN)
        user.set_password('password123')
        proj = Project(name='Mig Project', key='MIG', description='Testing migrations', status=Project.STATUS_ACTIVE)
        db.session.add_all([user, proj])
        db.session.flush()

        issue = Issue(
            issue_key='MIG-1',
            title='Test Migrated Issue',
            issue_type=Issue.TYPE_BUG,
            severity=Issue.SEV_MAJOR,
            priority=Issue.PRI_HIGH,
            status=Issue.STATUS_REPORTED,
            project_id=proj.id,
            reporter_id=user.id
        )
        db.session.add(issue)
        db.session.commit()

        # Verify query works on migrated DB
        assert User.query.filter_by(username='mig_user').first() is not None
        assert Issue.query.filter_by(issue_key='MIG-1').first() is not None

        # Clean session
        db.session.remove()

        # 3. Test downgrade to base
        command.downgrade(alembic_cfg, 'base')

        conn = sqlite3.connect(temp_db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
        remaining_tables = [r[0] for r in cursor.fetchall()]
        conn.close()

        # Only alembic_version table should remain after downgrade to base
        assert 'users' not in remaining_tables
        assert 'issues' not in remaining_tables
        assert 'projects' not in remaining_tables


def test_existing_database_not_corrupted_or_altered():
    """Ensure the existing development database instance/intellitrack.db has preserved its data."""
    db_path = os.path.join(os.path.dirname(__file__), '..', 'instance', 'intellitrack.db')
    if not os.path.exists(db_path):
        pytest.skip("instance/intellitrack.db does not exist")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT count(*) FROM users;")
    user_count = cursor.fetchone()[0]
    cursor.execute("SELECT count(*) FROM projects;")
    project_count = cursor.fetchone()[0]
    cursor.execute("SELECT count(*) FROM issues;")
    issue_count = cursor.fetchone()[0]
    cursor.execute("SELECT count(*) FROM activities;")
    activity_count = cursor.fetchone()[0]
    conn.close()

    assert user_count == 5, f"Expected 5 users, found {user_count}"
    assert project_count == 3, f"Expected 3 projects, found {project_count}"
    assert issue_count == 13, f"Expected 13 issues, found {issue_count}"
    assert activity_count == 37, f"Expected 37 activities, found {activity_count}"
