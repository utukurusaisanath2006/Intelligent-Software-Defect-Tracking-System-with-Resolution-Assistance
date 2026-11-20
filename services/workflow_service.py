"""Workflow engine — manages issue lifecycle transitions."""

from datetime import datetime
from extensions import db
from models.issue import Issue
from models.activity import Activity


class WorkflowService:
    """Centralized workflow transition manager."""

    # Valid state transitions
    TRANSITION_MAP = {
        'reported': ['triaging'],
        'triaging': ['assigned', 'closed'],
        'assigned': ['in_progress', 'closed'],
        'in_progress': ['code_review', 'assigned'],
        'code_review': ['qa_verification', 'in_progress'],
        'qa_verification': ['resolved', 'in_progress'],
        'resolved': ['closed', 'reopened'],
        'reopened': ['in_progress', 'closed'],
        'closed': ['reopened'],
    }

    # Role permissions for transitions
    ROLE_PERMISSIONS = {
        'admin': '*',  # All transitions
        'developer': {
            'assigned': ['in_progress'],
            'in_progress': ['code_review', 'assigned'],
            'code_review': ['qa_verification', 'in_progress'],
            'reopened': ['in_progress'],
        },
        'reporter': {
            'qa_verification': ['resolved', 'in_progress'],
            'resolved': ['reopened'],
        },
    }

    @classmethod
    def get_transition_map(cls):
        """Return the full transition map."""
        return dict(cls.TRANSITION_MAP)

    @classmethod
    def get_available_transitions(cls, issue, user):
        """Get valid next states for an issue given the user's role."""
        current = issue.status
        possible = cls.TRANSITION_MAP.get(current, [])

        if user.is_admin:
            return possible

        role_perms = cls.ROLE_PERMISSIONS.get(user.role, {})
        if role_perms == '*':
            return possible

        allowed = role_perms.get(current, [])
        return [t for t in possible if t in allowed]

    @classmethod
    def can_user_transition(cls, issue, user, target_status):
        """Check if user can transition issue to target status."""
        available = cls.get_available_transitions(issue, user)
        return target_status in available

    @classmethod
    def transition_issue(cls, issue, new_status, user, notes=None):
        """
        Execute a workflow transition.

        Returns (success: bool, message: str)
        """
        # Validate transition
        if new_status not in Issue.VALID_STATUSES:
            return False, f"Invalid status: {new_status}"

        available = cls.get_available_transitions(issue, user)
        if new_status not in available:
            return False, f"Transition from '{issue.status}' to '{new_status}' is not permitted for your role."

        old_status = issue.status

        # Update issue
        issue.status = new_status
        issue.updated_at = datetime.utcnow()

        # Set resolved timestamp
        if new_status == 'resolved':
            issue.resolved_at = datetime.utcnow()
        elif new_status == 'reopened':
            issue.resolved_at = None

        # Record activity
        activity = Activity(
            issue_id=issue.id,
            project_id=issue.project_id,
            actor_id=user.id,
            event_type=Activity.EVT_STATUS_CHANGED,
            field_name='status',
            old_value=old_status,
            new_value=new_status,
            details=notes or f"Status changed from {old_status} to {new_status}",
        )
        db.session.add(activity)

        # Create notifications
        from services.notification_service import NotificationService
        NotificationService.notify_status_change(issue, old_status, new_status, user)

        try:
            db.session.commit()
            return True, f"Issue transitioned to {new_status.replace('_', ' ').title()}"
        except Exception as e:
            db.session.rollback()
            return False, f"Database error: {str(e)}"

    @classmethod
    def get_status_display(cls, status):
        """Human-readable status name."""
        return status.replace('_', ' ').title()

    @classmethod
    def get_status_css_class(cls, status):
        """CSS class for status badge."""
        mapping = {
            'reported': 'status-open',
            'triaging': 'status-open',
            'assigned': 'status-open',
            'in_progress': 'status-progress',
            'code_review': 'status-progress',
            'qa_verification': 'status-progress',
            'resolved': 'status-resolved',
            'closed': 'status-closed',
            'reopened': 'status-critical',
        }
        return mapping.get(status, 'status-open')
