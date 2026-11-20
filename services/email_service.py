"""Email notification service using SMTP and standard library email tooling."""

import smtplib
import logging
from email.message import EmailMessage
from flask import current_app

logger = logging.getLogger(__name__)


class EmailService:
    """Dispatches transactional email notifications."""

    # In-memory outbox populated during development / test runs when MAIL_SUPPRESS_SEND is True
    outbox = []

    @classmethod
    def send_email(cls, to_email, subject, body_text, body_html=None):
        """
        Send a single email securely using configured SMTP settings.

        Returns (success: bool, error_message: str or None)
        """
        if not to_email:
            return False, "Recipient email address is required"

        config = current_app.config
        suppress_send = config.get('MAIL_SUPPRESS_SEND', True)
        sender = config.get('MAIL_DEFAULT_SENDER', 'noreply@intellitrack.dev')
        server_host = config.get('MAIL_SERVER', 'localhost')
        server_port = config.get('MAIL_PORT', 587)
        use_tls = config.get('MAIL_USE_TLS', True)
        use_ssl = config.get('MAIL_USE_SSL', False)
        username = config.get('MAIL_USERNAME')
        password = config.get('MAIL_PASSWORD')

        msg = EmailMessage()
        msg['Subject'] = subject
        msg['From'] = sender
        msg['To'] = to_email
        msg.set_content(body_text)

        if body_html:
            msg.add_alternative(body_html, subtype='html')

        # Development / test mode: record in outbox without network transmission
        if suppress_send:
            cls.outbox.append({
                'to': to_email,
                'from': sender,
                'subject': subject,
                'body_text': body_text,
                'body_html': body_html,
                'message': msg
            })
            logger.info("Email suppressed (dev/test mode): To=%s, Subject='%s'", to_email, subject)
            return True, None

        # Network transmission via SMTP
        try:
            logger.info("Connecting to SMTP server %s:%s for recipient %s", server_host, server_port, to_email)
            if use_ssl:
                server = smtplib.SMTP_SSL(server_host, server_port, timeout=10)
            else:
                server = smtplib.SMTP(server_host, server_port, timeout=10)

            if use_tls and not use_ssl:
                server.starttls()

            if username and password:
                server.login(username, password)

            server.send_message(msg)
            server.quit()
            logger.info("Email dispatched successfully to %s: '%s'", to_email, subject)
            return True, None
        except Exception as e:
            # Handle failure gracefully so caller is never blocked or crashed
            logger.error("Failed to send email to %s: %s", to_email, str(e))
            return False, str(e)

    @classmethod
    def send_issue_assigned(cls, issue, assignee, actor):
        """Send email to newly assigned user."""
        if not assignee or not assignee.email:
            return False, "No assignee email"

        # Check user notification preference if defined
        if not getattr(assignee, 'email_notifications_enabled', True):
            return True, "User preference disabled"

        subject = f"[IntelliTrack] Assigned: {issue.issue_key} - {issue.title[:50]}"
        text = (
            f"Hello {assignee.first_name or assignee.username},\n\n"
            f"You have been assigned to issue {issue.issue_key} by {actor.full_name}:\n\n"
            f"Title: {issue.title}\n"
            f"Priority: {issue.priority.title()}\n"
            f"Severity: {issue.severity.title()}\n"
            f"Status: {issue.status_display}\n\n"
            f"Description:\n{issue.description or 'No description provided.'}\n\n"
            f"---\nIntelliTrack Defect Tracking System"
        )
        return cls.send_email(assignee.email, subject, text)

    @classmethod
    def send_status_change(cls, issue, old_status, new_status, actor, recipient):
        """Send email notification on issue status transition."""
        if not recipient or not recipient.email:
            return False, "No recipient email"

        if not getattr(recipient, 'email_notifications_enabled', True):
            return True, "User preference disabled"

        old_display = old_status.replace('_', ' ').title()
        new_display = new_status.replace('_', ' ').title()
        subject = f"[IntelliTrack] Status Update: {issue.issue_key} -> {new_display}"
        text = (
            f"Hello {recipient.first_name or recipient.username},\n\n"
            f"The status of {issue.issue_key} has been updated by {actor.full_name}:\n\n"
            f"Title: {issue.title}\n"
            f"Old Status: {old_display}\n"
            f"New Status: {new_display}\n\n"
            f"---\nIntelliTrack Defect Tracking System"
        )
        return cls.send_email(recipient.email, subject, text)

    @classmethod
    def send_comment_added(cls, issue, comment, author, recipient):
        """Send email notification when a comment is posted."""
        if not recipient or not recipient.email:
            return False, "No recipient email"

        if not getattr(recipient, 'email_notifications_enabled', True):
            return True, "User preference disabled"

        subject = f"[IntelliTrack] New Comment on {issue.issue_key}"
        text = (
            f"Hello {recipient.first_name or recipient.username},\n\n"
            f"{author.full_name} posted a comment on {issue.issue_key} ({issue.title}):\n\n"
            f"\"{comment.body}\"\n\n"
            f"---\nIntelliTrack Defect Tracking System"
        )
        return cls.send_email(recipient.email, subject, text)

    @classmethod
    def send_release_notification(cls, release, actor, event='created', old_status=None, new_status=None):
        """Send email to all project members on release creation or status change."""
        from models.project import ProjectMembership

        members = ProjectMembership.query.filter_by(project_id=release.project_id).all()
        sent_emails = set()

        if event == 'created':
            subject = f"[IntelliTrack] New Release: {release.name} ({release.project.name})"
            for member in members:
                user = member.user
                if user and user.email and user.id != actor.id and user.email not in sent_emails:
                    sent_emails.add(user.email)
                    if getattr(user, 'email_notifications_enabled', True):
                        text = (
                            f"Hello {user.first_name or user.username},\n\n"
                            f"A new release milestone has been created by {actor.full_name} for project {release.project.name}:\n\n"
                            f"Release: {release.name}\n"
                            f"Version: {release.version or 'Milestone'}\n"
                            f"Status: {release.status.title()}\n"
                            f"Target Date: {release.release_date.strftime('%b %d, %Y') if release.release_date else 'Not set'}\n\n"
                            f"Description:\n{release.description or 'No description provided.'}\n\n"
                            f"---\nIntelliTrack Defect Tracking System"
                        )
                        cls.send_email(user.email, subject, text)

        elif event == 'status_changed':
            old_display = (old_status or '').replace('_', ' ').title()
            new_display = (new_status or '').replace('_', ' ').title()
            subject = f"[IntelliTrack] Release Status: {release.name} is now {new_display}"
            for member in members:
                user = member.user
                if user and user.email and user.id != actor.id and user.email not in sent_emails:
                    sent_emails.add(user.email)
                    if getattr(user, 'email_notifications_enabled', True):
                        text = (
                            f"Hello {user.first_name or user.username},\n\n"
                            f"Release milestone '{release.name}' status has been updated by {actor.full_name}:\n\n"
                            f"Old Status: {old_display}\n"
                            f"New Status: {new_display}\n\n"
                            f"---\nIntelliTrack Defect Tracking System"
                        )
                        cls.send_email(user.email, subject, text)
