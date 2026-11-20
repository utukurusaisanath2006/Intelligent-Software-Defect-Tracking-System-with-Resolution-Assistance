"""Attachment model for file uploads on issues."""

from datetime import datetime
from extensions import db


class Attachment(db.Model):
    """File attachment on an issue."""

    __tablename__ = 'attachments'

    id = db.Column(db.Integer, primary_key=True)
    issue_id = db.Column(db.Integer, db.ForeignKey('issues.id'), nullable=False, index=True)
    uploader_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    stored_filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    content_type = db.Column(db.String(100), default='application/octet-stream')
    file_size = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    uploader = db.relationship('User', backref=db.backref('uploads', lazy='dynamic'))

    def __repr__(self):
        return f'<Attachment {self.original_filename} on issue {self.issue_id}>'
