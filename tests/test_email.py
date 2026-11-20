"""Email notification service unit and integration tests."""

import smtplib
from unittest.mock import patch, MagicMock
from extensions import db
from models.user import User
from models.project import Project, ProjectMembership
from models.issue import Issue
from models.comment import Comment
from models.release import Release
from models.notification import Notification
from services.email_service import EmailService
from services.notification_service import NotificationService
from services.workflow_service import WorkflowService


def setup_function():
    """Clear outbox before each test."""
    EmailService.outbox.clear()


def test_email_suppression_mode_records_in_outbox(app):
    """When MAIL_SUPPRESS_SEND is True, emails are recorded in outbox without network transmission."""
    with app.app_context():
        success, err = EmailService.send_email(
            to_email='user@test.dev',
            subject='Welcome to IntelliTrack',
            body_text='Hello user, your account is ready.'
        )
        assert success is True
        assert err is None
        assert len(EmailService.outbox) == 1
        entry = EmailService.outbox[0]
        assert entry['to'] == 'user@test.dev'
        assert entry['subject'] == 'Welcome to IntelliTrack'
        assert 'Hello user' in entry['body_text']


def test_issue_assigned_triggers_email(app, sample_data):
    """Assigning an issue sends an email notification to the assignee."""
    with app.app_context():
        issue = sample_data['issue1']
        dev = sample_data['dev']
        admin = sample_data['admin']

        NotificationService.notify_issue_assigned(issue, dev, admin)

        # In-app notification created
        notif = Notification.query.filter_by(user_id=dev.id, type=Notification.TYPE_ASSIGNED).first()
        assert notif is not None

        # Email sent to outbox
        matching_emails = [e for e in EmailService.outbox if e['to'] == dev.email]
        assert len(matching_emails) == 1
        assert f"Assigned: {issue.issue_key}" in matching_emails[0]['subject']
        assert dev.first_name in matching_emails[0]['body_text']


def test_status_change_triggers_email(app, sample_data):
    """Issue status transition sends notification emails to reporter and assignee."""
    with app.app_context():
        issue = sample_data['issue2']  # reporter: reporter@test.dev, assignee: dev@test.dev
        admin = sample_data['admin']

        WorkflowService.transition_issue(issue, 'in_progress', admin)

        # Both dev and reporter should receive emails (actor was admin)
        recipients = [e['to'] for e in EmailService.outbox]
        assert sample_data['dev'].email in recipients
        assert sample_data['reporter'].email in recipients


def test_comment_added_triggers_email(app, sample_data):
    """Adding a comment triggers email notification to issue subscribers."""
    with app.app_context():
        issue = sample_data['issue2']
        dev = sample_data['dev']

        comment = Comment(issue_id=issue.id, author_id=dev.id, body='Fix committed in rev 4920.')
        db.session.add(comment)
        db.session.commit()

        NotificationService.notify_comment_added(issue, comment, dev)

        # Reporter receives email (dev is the author so dev is excluded)
        matching = [e for e in EmailService.outbox if e['to'] == sample_data['reporter'].email]
        assert len(matching) == 1
        assert f"New Comment on {issue.issue_key}" in matching[0]['subject']
        assert 'Fix committed' in matching[0]['body_text']


def test_release_notifications_dispatch_email(app, sample_data):
    """Release creation and status update send email to project members."""
    with app.app_context():
        proj1 = sample_data['proj1']
        admin = sample_data['admin']

        release = Release(name='v2.0 Beta', project_id=proj1.id, status='planning')
        db.session.add(release)
        db.session.commit()

        # 1. Release created
        NotificationService.notify_release_created(release, admin)
        create_emails = [e for e in EmailService.outbox if 'New Release: v2.0 Beta' in e['subject']]
        assert len(create_emails) >= 1

        # 2. Status changed
        NotificationService.notify_release_status_changed(release, 'planning', 'in_progress', admin)
        status_emails = [e for e in EmailService.outbox if 'Release Status: v2.0 Beta is now In Progress' in e['subject']]
        assert len(status_emails) >= 1


def test_email_failure_does_not_break_workflow(app, sample_data):
    """SMTP network or authentication failure is handled gracefully and never crashes callers."""
    with app.app_context():
        app.config['MAIL_SUPPRESS_SEND'] = False

        # Mock smtplib.SMTP to raise connection error
        with patch('smtplib.SMTP', side_effect=smtplib.SMTPConnectError(421, 'Service not available')):
            success, err = EmailService.send_email(
                to_email='user@test.dev',
                subject='Test Fail',
                body_text='This should fail safely.'
            )
            assert success is False
            assert 'Service not available' in err

            # Verify that calling NotificationService does not raise an exception
            issue = sample_data['issue1']
            dev = sample_data['dev']
            admin = sample_data['admin']
            # Should not raise:
            NotificationService.notify_issue_assigned(issue, dev, admin)

            # In-app notification still persisted successfully in DB
            notif = Notification.query.filter_by(user_id=dev.id, issue_id=issue.id).first()
            assert notif is not None


def test_user_notification_preference_respected(app, sample_data):
    """If user has email_notifications_enabled=False, email is suppressed."""
    with app.app_context():
        issue = sample_data['issue1']
        dev = sample_data['dev']
        admin = sample_data['admin']

        dev.email_notifications_enabled = False

        success, msg = EmailService.send_issue_assigned(issue, dev, admin)
        assert success is True
        assert 'User preference disabled' in msg
        assert len(EmailService.outbox) == 0
