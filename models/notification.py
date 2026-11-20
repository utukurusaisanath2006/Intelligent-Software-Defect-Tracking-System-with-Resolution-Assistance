"""Notification model for in-app notifications."""

from datetime import datetime
from extensions import db


class Notification(db.Model):
    """In-app notification for users."""

    __tablename__ = 'notifications'

    TYPE_INFO = 'info'
    TYPE_ASSIGNED = 'assigned'
    TYPE_STATUS_CHANGED = 'status_changed'
    TYPE_COMMENTED = 'commented'
    TYPE_MENTION = 'mention'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    issue_id = db.Column(db.Integer, db.ForeignKey('issues.id'), nullable=True)
    type = db.Column(db.String(30), default=TYPE_INFO, nullable=False)
    message = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    issue = db.relationship('Issue', backref=db.backref('notifications', lazy='dynamic'))

    def to_dict(self):
        return {
            'id': self.id,
            'type': self.type,
            'message': self.message,
            'is_read': self.is_read,
            'issue_id': self.issue_id,
            'issue_key': self.issue.issue_key if self.issue else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f'<Notification {self.id} for user {self.user_id}>'
