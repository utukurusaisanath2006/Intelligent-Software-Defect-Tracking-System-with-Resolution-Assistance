"""Activity/audit log model."""

from datetime import datetime
from extensions import db


class Activity(db.Model):
    """Audit trail entry for issue and system events."""

    __tablename__ = 'activities'

    # Event types
    EVT_CREATED = 'created'
    EVT_UPDATED = 'updated'
    EVT_STATUS_CHANGED = 'status_changed'
    EVT_ASSIGNED = 'assigned'
    EVT_COMMENTED = 'commented'
    EVT_ATTACHMENT_ADDED = 'attachment_added'
    EVT_SPRINT_CHANGED = 'sprint_changed'
    EVT_USER_CREATED = 'user_created'
    EVT_USER_UPDATED = 'user_updated'
    EVT_PROJECT_CREATED = 'project_created'
    EVT_PROJECT_UPDATED = 'project_updated'

    id = db.Column(db.Integer, primary_key=True)
    issue_id = db.Column(db.Integer, db.ForeignKey('issues.id'), nullable=True, index=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=True)
    actor_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    event_type = db.Column(db.String(30), nullable=False, index=True)
    field_name = db.Column(db.String(50), nullable=True)
    old_value = db.Column(db.String(200), nullable=True)
    new_value = db.Column(db.String(200), nullable=True)
    details = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationship to project (issue relationship is in Issue model)
    project_rel = db.relationship('Project', backref=db.backref('activities', lazy='dynamic'))

    @property
    def event_display(self):
        return self.event_type.replace('_', ' ').title()

    def to_dict(self):
        return {
            'id': self.id,
            'issue_id': self.issue_id,
            'issue_key': self.issue.issue_key if self.issue else None,
            'actor_id': self.actor_id,
            'actor_name': self.actor.full_name if self.actor else None,
            'event_type': self.event_type,
            'field_name': self.field_name,
            'old_value': self.old_value,
            'new_value': self.new_value,
            'details': self.details,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f'<Activity {self.event_type} by user {self.actor_id}>'
