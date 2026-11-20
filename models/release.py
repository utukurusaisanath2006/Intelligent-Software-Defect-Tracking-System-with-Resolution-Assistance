"""Release model for version management."""

from datetime import datetime
from extensions import db


class Release(db.Model):
    """Software release or milestone."""

    __tablename__ = 'releases'

    STATUS_PLANNING = 'planning'
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_RELEASED = 'released'
    VALID_STATUSES = [STATUS_PLANNING, STATUS_IN_PROGRESS, STATUS_RELEASED]

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    version = db.Column(db.String(30), nullable=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False, index=True)
    status = db.Column(db.String(20), default=STATUS_PLANNING, nullable=False)
    release_date = db.Column(db.Date, nullable=True)
    description = db.Column(db.Text, default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    issues = db.relationship('Issue', backref='release', lazy='dynamic')

    def __repr__(self):
        return f'<Release {self.name} ({self.version})>'
