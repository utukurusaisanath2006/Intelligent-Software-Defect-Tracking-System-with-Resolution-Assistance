"""Issue model — the core of IntelliTrack."""

from datetime import datetime
from extensions import db


class Issue(db.Model):
    """Software defect or feature request."""

    __tablename__ = 'issues'

    # Issue types
    TYPE_BUG = 'bug'
    TYPE_FEATURE = 'feature'
    TYPE_ENHANCEMENT = 'enhancement'
    TYPE_TECHNICAL_DEBT = 'technical_debt'
    VALID_TYPES = [TYPE_BUG, TYPE_FEATURE, TYPE_ENHANCEMENT, TYPE_TECHNICAL_DEBT]

    # Severities
    SEV_CRITICAL = 'critical'
    SEV_MAJOR = 'major'
    SEV_MINOR = 'minor'
    SEV_TRIVIAL = 'trivial'
    VALID_SEVERITIES = [SEV_CRITICAL, SEV_MAJOR, SEV_MINOR, SEV_TRIVIAL]

    # Priorities
    PRI_URGENT = 'urgent'
    PRI_HIGH = 'high'
    PRI_MEDIUM = 'medium'
    PRI_LOW = 'low'
    VALID_PRIORITIES = [PRI_URGENT, PRI_HIGH, PRI_MEDIUM, PRI_LOW]

    # Statuses (workflow states)
    STATUS_REPORTED = 'reported'
    STATUS_TRIAGING = 'triaging'
    STATUS_ASSIGNED = 'assigned'
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_CODE_REVIEW = 'code_review'
    STATUS_QA_VERIFICATION = 'qa_verification'
    STATUS_RESOLVED = 'resolved'
    STATUS_CLOSED = 'closed'
    STATUS_REOPENED = 'reopened'
    VALID_STATUSES = [
        STATUS_REPORTED, STATUS_TRIAGING, STATUS_ASSIGNED, STATUS_IN_PROGRESS,
        STATUS_CODE_REVIEW, STATUS_QA_VERIFICATION, STATUS_RESOLVED,
        STATUS_CLOSED, STATUS_REOPENED,
    ]
    OPEN_STATUSES = [
        STATUS_REPORTED, STATUS_TRIAGING, STATUS_ASSIGNED, STATUS_IN_PROGRESS,
        STATUS_CODE_REVIEW, STATUS_QA_VERIFICATION, STATUS_REOPENED,
    ]

    # Categories
    VALID_CATEGORIES = [
        'ui_ux', 'backend_api', 'database', 'authentication',
        'performance', 'security', 'integration', 'configuration', 'other',
    ]

    id = db.Column(db.Integer, primary_key=True)
    issue_key = db.Column(db.String(20), unique=True, nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default='')
    issue_type = db.Column(db.String(20), nullable=False, default=TYPE_BUG)
    category = db.Column(db.String(30), default='other')
    severity = db.Column(db.String(20), nullable=False, default=SEV_MINOR)
    priority = db.Column(db.String(20), nullable=False, default=PRI_MEDIUM)
    status = db.Column(db.String(30), nullable=False, default=STATUS_REPORTED, index=True)
    component = db.Column(db.String(100), default='')
    environment = db.Column(db.String(200), default='')
    steps_to_reproduce = db.Column(db.Text, default='')
    expected_result = db.Column(db.Text, default='')
    actual_result = db.Column(db.Text, default='')
    root_cause = db.Column(db.Text, default='')
    resolution_notes = db.Column(db.Text, default='')

    # Foreign keys
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False, index=True)
    reporter_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    assignee_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    sprint_id = db.Column(db.Integer, db.ForeignKey('sprints.id'), nullable=True)
    release_id = db.Column(db.Integer, db.ForeignKey('releases.id'), nullable=True)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    resolved_at = db.Column(db.DateTime, nullable=True)

    # Relationships
    comments = db.relationship('Comment', backref='issue', lazy='dynamic',
                               cascade='all, delete-orphan', order_by='Comment.created_at')
    activities = db.relationship('Activity', backref='issue', lazy='dynamic',
                                 cascade='all, delete-orphan', order_by='Activity.created_at.desc()')
    attachments = db.relationship('Attachment', backref='issue', lazy='dynamic',
                                  cascade='all, delete-orphan')

    @property
    def is_open(self):
        return self.status in self.OPEN_STATUSES

    @property
    def status_display(self):
        return self.status.replace('_', ' ').title()

    @property
    def type_display(self):
        return self.issue_type.replace('_', ' ').title()

    @property
    def severity_display(self):
        return self.severity.title()

    @property
    def priority_display(self):
        return self.priority.title()

    @property
    def category_display(self):
        return self.category.replace('_', '/').upper() if self.category else 'Other'

    def to_dict(self):
        """Serialize issue to dictionary."""
        return {
            'id': self.id,
            'issue_key': self.issue_key,
            'title': self.title,
            'description': self.description,
            'issue_type': self.issue_type,
            'category': self.category,
            'severity': self.severity,
            'priority': self.priority,
            'status': self.status,
            'component': self.component,
            'environment': self.environment,
            'project_id': self.project_id,
            'project_name': self.project.name if self.project else None,
            'project_key': self.project.key if self.project else None,
            'reporter_id': self.reporter_id,
            'reporter_name': self.reporter.full_name if self.reporter else None,
            'assignee_id': self.assignee_id,
            'assignee_name': self.assignee.full_name if self.assignee else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None,
        }

    def __repr__(self):
        return f'<Issue {self.issue_key}: {self.title[:40]}>'
