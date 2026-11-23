"""Pytest fixtures for IntelliTrack isolated test suite."""

import pytest
from app import create_app
from extensions import db as _db
from models.user import User
from models.project import Project, ProjectMembership
from models.issue import Issue
from models.sprint import Sprint


@pytest.fixture(scope='function')
def app():
    """Create application configured for isolated in-memory testing."""
    application = create_app('testing')
    with application.app_context():
        _db.create_all()
        yield application
        _db.session.remove()
        _db.drop_all()


@pytest.fixture(scope='function')
def client(app):
    """Flask test client."""
    return app.test_client()


# Precomputed hash for test password 'secret123' to avoid plaintext passwords and repetitive runtime hashing
TEST_PASSWORD_HASH = 'scrypt:32768:8:1$Gm2nevbIVnfRfnq6$e9c18d77cb2356dbbe0fe27d7291e8cd40bd62cb603c4b3e75618858ed9ce575a91b4f19de067f6b0edf78f95dc77fdc2937e9b7b813cd1d82ceecd96945ba4e'


@pytest.fixture(scope='function')
def sample_data(app):
    """Seed users, projects, memberships, sprint, and sample issues."""
    admin = User(
        username='admin_t', email='admin@test.dev', password_hash=TEST_PASSWORD_HASH,
        first_name='Admin', last_name='User', role=User.ROLE_ADMIN, is_active=True
    )

    dev = User(
        username='dev_t', email='dev@test.dev', password_hash=TEST_PASSWORD_HASH,
        first_name='Dev', last_name='Engineer', role=User.ROLE_DEVELOPER, is_active=True
    )

    reporter = User(
        username='rep_t', email='reporter@test.dev', password_hash=TEST_PASSWORD_HASH,
        first_name='QA', last_name='Tester', role=User.ROLE_REPORTER, is_active=True
    )

    outsider = User(
        username='out_t', email='outsider@test.dev', password_hash=TEST_PASSWORD_HASH,
        first_name='Out', last_name='Sider', role=User.ROLE_REPORTER, is_active=True
    )

    inactive = User(
        username='inact_t', email='inactive@test.dev', password_hash=TEST_PASSWORD_HASH,
        first_name='In', last_name='Active', role=User.ROLE_REPORTER, is_active=False
    )

    _db.session.add_all([admin, dev, reporter, outsider, inactive])
    _db.session.flush()

    proj1 = Project(name='Core App', key='CORE', description='Primary application', status=Project.STATUS_ACTIVE)
    proj2 = Project(name='Secret Internal', key='SEC', description='Restricted project', status=Project.STATUS_ACTIVE)
    _db.session.add_all([proj1, proj2])
    _db.session.flush()

    # Memberships: admin, dev, reporter belong to CORE; only admin belongs to SEC
    for u in [admin, dev, reporter]:
        _db.session.add(ProjectMembership(user_id=u.id, project_id=proj1.id, role='member'))
    _db.session.add(ProjectMembership(user_id=admin.id, project_id=proj2.id, role='manager'))

    sprint = Sprint(name='Sprint 1', project_id=proj1.id, status=Sprint.STATUS_ACTIVE)
    _db.session.add(sprint)
    _db.session.flush()

    issue1 = Issue(
        issue_key='CORE-1',
        title='Database deadlock on checkout transaction',
        description='SQL deadlock occurs under heavy load during payment commit.',
        issue_type=Issue.TYPE_BUG,
        category='database',
        severity=Issue.SEV_CRITICAL,
        priority=Issue.PRI_URGENT,
        status=Issue.STATUS_REPORTED,
        component='Checkout',
        project_id=proj1.id,
        reporter_id=reporter.id,
        sprint_id=sprint.id,
    )
    issue2 = Issue(
        issue_key='CORE-2',
        title='Button alignment slightly off on login form',
        description='Minor CSS alignment issue on mobile button.',
        issue_type=Issue.TYPE_BUG,
        category='ui_ux',
        severity=Issue.SEV_MINOR,
        priority=Issue.PRI_LOW,
        status=Issue.STATUS_ASSIGNED,
        component='UI',
        project_id=proj1.id,
        reporter_id=reporter.id,
        assignee_id=dev.id,
    )
    issue_sec = Issue(
        issue_key='SEC-1',
        title='Restricted security audit item',
        description='Confidential details.',
        issue_type=Issue.TYPE_BUG,
        category='security',
        severity=Issue.SEV_CRITICAL,
        priority=Issue.PRI_URGENT,
        status=Issue.STATUS_REPORTED,
        project_id=proj2.id,
        reporter_id=admin.id,
    )
    _db.session.add_all([issue1, issue2, issue_sec])
    _db.session.commit()

    return {
        'admin': admin,
        'dev': dev,
        'reporter': reporter,
        'outsider': outsider,
        'inactive': inactive,
        'proj1': proj1,
        'proj2': proj2,
        'sprint': sprint,
        'issue1': issue1,
        'issue2': issue2,
        'issue_sec': issue_sec,
    }


def login(client, email, password='secret123'):
    """Helper to sign a user into the test client."""
    return client.post('/auth/login', data={'email': email, 'password': password}, follow_redirects=True)
