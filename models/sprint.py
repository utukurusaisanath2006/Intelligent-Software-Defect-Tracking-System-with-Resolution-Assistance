"""Sprint model for agile planning."""

from datetime import datetime
from extensions import db


class Sprint(db.Model):
    """Agile sprint for grouping issues."""

    __tablename__ = 'sprints'

    STATUS_PLANNING = 'planning'
    STATUS_ACTIVE = 'active'
    STATUS_COMPLETED = 'completed'
    VALID_STATUSES = [STATUS_PLANNING, STATUS_ACTIVE, STATUS_COMPLETED]

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False, index=True)
    status = db.Column(db.String(20), default=STATUS_PLANNING, nullable=False)
    start_date = db.Column(db.Date, nullable=True)
    end_date = db.Column(db.Date, nullable=True)
    goal = db.Column(db.Text, default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    issues = db.relationship('Issue', backref='sprint', lazy='dynamic')

    @property
    def total_issues(self):
        return self.issues.count()

    @property
    def completed_issues(self):
        return self.issues.filter(
            Issue.status.in_(['resolved', 'closed'])
        ).count() if self.issues.count() > 0 else 0

    @property
    def completion_rate(self):
        total = self.total_issues
        if total == 0:
            return 0
        return round((self.completed_issues / total) * 100, 1)

    def __repr__(self):
        return f'<Sprint {self.name}>'


# Fix circular import for completed_issues property
from models.issue import Issue
