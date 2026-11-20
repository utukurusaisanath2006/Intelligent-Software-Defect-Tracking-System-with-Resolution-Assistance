"""User model with authentication support."""

from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from extensions import db, login_manager


class User(UserMixin, db.Model):
    """Application user with role-based access."""

    __tablename__ = 'users'

    ROLE_ADMIN = 'admin'
    ROLE_DEVELOPER = 'developer'
    ROLE_REPORTER = 'reporter'
    VALID_ROLES = [ROLE_ADMIN, ROLE_DEVELOPER, ROLE_REPORTER]

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    first_name = db.Column(db.String(80), nullable=False, default='')
    last_name = db.Column(db.String(80), nullable=False, default='')
    role = db.Column(db.String(20), nullable=False, default=ROLE_REPORTER)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    reported_issues = db.relationship('Issue', foreign_keys='Issue.reporter_id', backref='reporter', lazy='dynamic')
    assigned_issues = db.relationship('Issue', foreign_keys='Issue.assignee_id', backref='assignee', lazy='dynamic')
    comments = db.relationship('Comment', backref='author', lazy='dynamic')
    activities = db.relationship('Activity', backref='actor', lazy='dynamic')
    notifications = db.relationship('Notification', backref='user', lazy='dynamic')
    memberships = db.relationship('ProjectMembership', backref='user', lazy='dynamic')

    def set_password(self, password):
        """Hash and store password."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Verify password against hash."""
        return check_password_hash(self.password_hash, password)

    @property
    def full_name(self):
        """Return user's full name."""
        name = f"{self.first_name} {self.last_name}".strip()
        return name if name else self.username

    @property
    def initials(self):
        """Return user initials for avatar."""
        if self.first_name and self.last_name:
            return f"{self.first_name[0]}{self.last_name[0]}".upper()
        return self.username[:2].upper()

    @property
    def is_admin(self):
        return self.role == self.ROLE_ADMIN

    @property
    def is_developer(self):
        return self.role == self.ROLE_DEVELOPER

    @property
    def is_reporter(self):
        return self.role == self.ROLE_REPORTER

    def has_project_access(self, project_id):
        """Check if user has access to a project."""
        if self.is_admin:
            return True
        from models.project import ProjectMembership
        return ProjectMembership.query.filter_by(
            user_id=self.id, project_id=project_id
        ).first() is not None

    def __repr__(self):
        return f'<User {self.username} ({self.role})>'


@login_manager.user_loader
def load_user(user_id):
    """Flask-Login user loader callback."""
    return User.query.get(int(user_id))
