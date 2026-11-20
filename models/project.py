"""Project and ProjectMembership models."""

from datetime import datetime
from extensions import db


class Project(db.Model):
    """Software project that contains issues."""

    __tablename__ = 'projects'

    STATUS_ACTIVE = 'active'
    STATUS_ARCHIVED = 'archived'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    key = db.Column(db.String(10), unique=True, nullable=False, index=True)
    description = db.Column(db.Text, default='')
    status = db.Column(db.String(20), default=STATUS_ACTIVE, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    issues = db.relationship('Issue', backref='project', lazy='dynamic')
    memberships = db.relationship('ProjectMembership', backref='project', lazy='dynamic',
                                  cascade='all, delete-orphan')
    sprints = db.relationship('Sprint', backref='project', lazy='dynamic')
    releases = db.relationship('Release', backref='project', lazy='dynamic')

    def generate_issue_key(self):
        """Generate next issue key like PROJ-42."""
        count = self.issues.count() + 1
        return f"{self.key}-{count}"

    @property
    def member_count(self):
        return self.memberships.count()

    @property
    def open_issue_count(self):
        from models.issue import Issue
        return self.issues.filter(
            Issue.status.notin_(['resolved', 'closed'])
        ).count()

    def __repr__(self):
        return f'<Project {self.key}: {self.name}>'


class ProjectMembership(db.Model):
    """Association between users and projects."""

    __tablename__ = 'project_memberships'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    role = db.Column(db.String(20), default='member')
    joined_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'project_id', name='uq_user_project'),
    )

    def __repr__(self):
        return f'<Membership user={self.user_id} project={self.project_id}>'
