"""Notification service for creating and managing in-app user notifications."""

from datetime import datetime
from extensions import db
from models.notification import Notification
from models.project import ProjectMembership
from models.user import User


class NotificationService:
    """Manages in-app notifications."""

    @staticmethod
    def create_notification(user_id, message, issue_id=None, n_type='info'):
        """Create and persist a notification."""
        notification = Notification(
            user_id=user_id,
            issue_id=issue_id,
            type=n_type,
            message=message,
            is_read=False,
            created_at=datetime.utcnow()
        )
        db.session.add(notification)
        return notification

    @staticmethod
    def get_user_notifications(user_id, unread_only=False, limit=20):
        """Fetch notifications for a user."""
        query = Notification.query.filter_by(user_id=user_id)
        if unread_only:
            query = query.filter_by(is_read=False)
        return query.order_by(Notification.created_at.desc()).limit(limit).all()

    @staticmethod
    def get_unread_count(user_id):
        """Count unread notifications for a user."""
        return Notification.query.filter_by(user_id=user_id, is_read=False).count()

    @staticmethod
    def mark_as_read(notification_id, user_id):
        """Mark a single notification as read."""
        n = Notification.query.filter_by(id=notification_id, user_id=user_id).first()
        if n:
            n.is_read = True
            db.session.commit()
            return True
        return False

    @staticmethod
    def mark_all_read(user_id):
        """Mark all unread notifications for a user as read."""
        updated = Notification.query.filter_by(user_id=user_id, is_read=False).update({'is_read': True})
        db.session.commit()
        return updated

    @classmethod
    def notify_issue_created(cls, issue, reporter):
        """Notify relevant project members about a new issue."""
        members = ProjectMembership.query.filter_by(project_id=issue.project_id).all()
        for member in members:
            if member.user_id != reporter.id:
                cls.create_notification(
                    user_id=member.user_id,
                    issue_id=issue.id,
                    n_type=Notification.TYPE_INFO,
                    message=f"New issue {issue.issue_key} was reported: {issue.title[:60]}"
                )
        db.session.commit()

    @classmethod
    def notify_issue_assigned(cls, issue, assignee, actor):
        """Notify assignee when assigned to an issue."""
        if assignee.id != actor.id:
            cls.create_notification(
                user_id=assignee.id,
                issue_id=issue.id,
                n_type=Notification.TYPE_ASSIGNED,
                message=f"You have been assigned to {issue.issue_key}: {issue.title[:60]}"
            )
            db.session.commit()

            # Email notification (non-blocking failure handling)
            try:
                from services.email_service import EmailService
                EmailService.send_issue_assigned(issue, assignee, actor)
            except Exception:
                pass

    @classmethod
    def notify_status_change(cls, issue, old_status, new_status, actor):
        """Notify reporter and assignee when status changes."""
        old_display = old_status.replace('_', ' ').title()
        new_display = new_status.replace('_', ' ').title()
        msg = f"{issue.issue_key} status changed from {old_display} to {new_display}"

        recipients = set()
        if issue.reporter_id and issue.reporter_id != actor.id:
            recipients.add(issue.reporter_id)
        if issue.assignee_id and issue.assignee_id != actor.id:
            recipients.add(issue.assignee_id)

        for uid in recipients:
            cls.create_notification(
                user_id=uid,
                issue_id=issue.id,
                n_type=Notification.TYPE_STATUS_CHANGED,
                message=msg
            )
        db.session.commit()

        # Email notification (non-blocking failure handling)
        try:
            from services.email_service import EmailService
            for uid in recipients:
                user = User.query.get(uid)
                if user:
                    EmailService.send_status_change(issue, old_status, new_status, actor, user)
        except Exception:
            pass

    @classmethod
    def notify_comment_added(cls, issue, comment, author):
        """Notify issue reporter and assignee when a comment is added."""
        recipients = set()
        if issue.reporter_id and issue.reporter_id != author.id:
            recipients.add(issue.reporter_id)
        if issue.assignee_id and issue.assignee_id != author.id:
            recipients.add(issue.assignee_id)

        msg = f"New comment on {issue.issue_key} by {author.full_name}: {comment.body[:60]}"
        for uid in recipients:
            cls.create_notification(
                user_id=uid,
                issue_id=issue.id,
                n_type=Notification.TYPE_COMMENTED,
                message=msg
            )
        db.session.commit()

        # Email notification (non-blocking failure handling)
        try:
            from services.email_service import EmailService
            for uid in recipients:
                user = User.query.get(uid)
                if user:
                    EmailService.send_comment_added(issue, comment, author, user)
        except Exception:
            pass

    @classmethod
    def notify_release_created(cls, release, actor):
        """Notify project members about a new release."""
        members = ProjectMembership.query.filter_by(project_id=release.project_id).all()
        msg = f"New release '{release.name}' ({release.version or 'Milestone'}) created for project {release.project.name}."
        for member in members:
            if member.user_id != actor.id:
                cls.create_notification(
                    user_id=member.user_id,
                    n_type=Notification.TYPE_INFO,
                    message=msg
                )
        db.session.commit()

        # Email notification (non-blocking failure handling)
        try:
            from services.email_service import EmailService
            EmailService.send_release_notification(release, actor, event='created')
        except Exception:
            pass

    @classmethod
    def notify_release_status_changed(cls, release, old_status, new_status, actor):
        """Notify project members when release status changes."""
        members = ProjectMembership.query.filter_by(project_id=release.project_id).all()
        old_display = old_status.replace('_', ' ').title()
        new_display = new_status.replace('_', ' ').title()
        msg = f"Release '{release.name}' status updated from {old_display} to {new_display}."
        for member in members:
            if member.user_id != actor.id:
                cls.create_notification(
                    user_id=member.user_id,
                    n_type=Notification.TYPE_INFO,
                    message=msg
                )
        db.session.commit()

        # Email notification (non-blocking failure handling)
        try:
            from services.email_service import EmailService
            EmailService.send_release_notification(release, actor, event='status_changed', old_status=old_status, new_status=new_status)
        except Exception:
            pass
