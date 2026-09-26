"""System update tracking and management model."""

from datetime import datetime
from app import db


class SystemUpdate(db.Model):
    """Track system updates, migrations, and rollback history."""
    
    __tablename__ = 'system_updates'
    
    id = db.Column(db.Integer, primary_key=True)
    version = db.Column(db.String(50), nullable=False, index=True)
    git_commit_sha = db.Column(db.String(40), nullable=True)
    git_branch = db.Column(db.String(100), nullable=False, default='main')
    update_type = db.Column(db.String(20), nullable=False)  # 'code', 'migration', 'rollback'
    status = db.Column(db.String(20), nullable=False, default='pending')  # pending, running, success, failed, rolled_back
    
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    
    changes_made = db.Column(db.Integer, default=0)  # Files changed, migrations run, etc.
    backup_path = db.Column(db.String(255), nullable=True)
    
    error_message = db.Column(db.Text, nullable=True)
    error_details = db.Column(db.Text, nullable=True)  # Full traceback
    
    initiated_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    initiated_user = db.relationship('User', backref='updates_initiated', foreign_keys=[initiated_by])
    
    rollback_from_update_id = db.Column(db.Integer, db.ForeignKey('system_updates.id'), nullable=True)
    rolled_back_by_update_id = db.Column(db.Integer, db.ForeignKey('system_updates.id'), nullable=True)
    
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<SystemUpdate {self.version} {self.status}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'version': self.version,
            'git_commit_sha': self.git_commit_sha,
            'git_branch': self.git_branch,
            'update_type': self.update_type,
            'status': self.status,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'changes_made': self.changes_made,
            'error_message': self.error_message,
            'initiated_by': self.initiated_user.email if self.initiated_user else None,
            'notes': self.notes,
            'created_at': self.created_at.isoformat(),
            'backup_path': self.backup_path,
            'duration_seconds': (self.completed_at - self.started_at).total_seconds() if self.completed_at and self.started_at else None,
        }


class UpdateLog(db.Model):
    """Detailed log entries for each update operation."""
    
    __tablename__ = 'update_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    update_id = db.Column(db.Integer, db.ForeignKey('system_updates.id'), nullable=False, index=True)
    update = db.relationship('SystemUpdate', backref='logs')
    
    log_level = db.Column(db.String(20), nullable=False)  # info, warning, error, success
    message = db.Column(db.Text, nullable=False)
    details = db.Column(db.Text, nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    def __repr__(self):
        return f'<UpdateLog {self.update_id} {self.log_level}>'
