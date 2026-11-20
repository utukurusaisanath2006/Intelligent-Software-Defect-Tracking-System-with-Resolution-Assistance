"""Comment model for issue discussions."""

from datetime import datetime
from extensions import db


class Comment(db.Model):
    """User comment on an issue."""

    __tablename__ = 'comments'

    id = db.Column(db.Integer, primary_key=True)
    issue_id = db.Column(db.Integer, db.ForeignKey('issues.id'), nullable=False, index=True)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'issue_id': self.issue_id,
            'author_id': self.author_id,
            'author_name': self.author.full_name if self.author else None,
            'author_initials': self.author.initials if self.author else '??',
            'body': self.body,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f'<Comment {self.id} on issue {self.issue_id}>'
