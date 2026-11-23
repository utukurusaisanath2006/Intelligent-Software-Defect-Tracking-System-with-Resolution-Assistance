"""IntelliTrack Flask Application Factory and CLI commands."""

import os
import click
from datetime import datetime
from flask import Flask, render_template, request, jsonify, url_for, abort, session
from flask_login import current_user
from markupsafe import Markup, escape
from flask_wtf.csrf import CSRFError
from config import config
from extensions import db, login_manager, csrf, migrate
import models  # Register all models for SQLAlchemy metadata and migrations
from routes import register_blueprints


def create_app(config_name=None):
    """Application factory for IntelliTrack."""
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')

    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config.get(config_name, config['default']))
    if os.environ.get('DATABASE_URL'):
        app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')

    # Ensure instance and upload directories exist
    os.makedirs(app.instance_path, exist_ok=True)
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # Safe migration strategy for legacy attachments: copy files from static/uploads to secure UPLOAD_FOLDER without deleting originals
    legacy_upload_dir = os.path.join(app.root_path, 'static', 'uploads')
    if os.path.isdir(legacy_upload_dir) and os.path.abspath(app.config['UPLOAD_FOLDER']) != os.path.abspath(legacy_upload_dir):
        import shutil
        for fname in os.listdir(legacy_upload_dir):
            src_file = os.path.join(legacy_upload_dir, fname)
            dst_file = os.path.join(app.config['UPLOAD_FOLDER'], fname)
            if os.path.isfile(src_file) and not os.path.exists(dst_file):
                try:
                    shutil.copy2(src_file, dst_file)
                except Exception:
                    pass

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db, render_as_batch=True)
    login_manager.init_app(app)
    csrf.init_app(app)

    # Register blueprints
    register_blueprints(app)

    # Custom Jinja2 filters
    @app.template_filter('nl2br')
    def nl2br_filter(value):
        if not value:
            return ''
        escaped = escape(str(value))
        return Markup(escaped.replace('\r\n', '<br>').replace('\n', '<br>'))

    # Context processors
    @app.context_processor
    def inject_global_data():
        unread_notifications = 0
        if current_user.is_authenticated:
            from services.notification_service import NotificationService
            try:
                unread_notifications = NotificationService.get_unread_count(current_user.id)
            except Exception:
                unread_notifications = 0

        def url_for_page(page_num):
            args = request.args.to_dict(flat=True)
            args['page'] = page_num
            return url_for(request.endpoint, **args)

        return {
            'now': datetime.utcnow(),
            'unread_notifications_count': unread_notifications,
            'app_name': 'IntelliTrack',
            'current_year': datetime.utcnow().year,
            'url_for_page': url_for_page,
        }

    # Block direct unauthenticated access to legacy static/uploads directory & manage session lifetime
    @app.before_request
    def pre_request_security_check():
        if request.path.startswith('/static/uploads/'):
            abort(404)
        if current_user.is_authenticated:
            session.permanent = True

    # Security headers
    @app.after_request
    def set_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['X-Download-Options'] = 'noopen'
        csp_policy = (
            "default-src 'self'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com data:; "
            "img-src 'self' data: https:; "
            "script-src 'self' 'unsafe-inline'; "
            "frame-ancestors 'self';"
        )
        response.headers['Content-Security-Policy'] = csp_policy
        return response

    # Error handlers & Security event logging
    @app.errorhandler(CSRFError)
    def handle_csrf_error(e):
        reason = getattr(e, 'description', 'CSRF token missing or invalid')
        app.logger.warning(f"Security Alert: CSRF validation failure on {request.path} from ip={request.remote_addr}: {reason}")
        if request.path.startswith('/api/'):
            return jsonify({'success': False, 'error': f'CSRF validation failed: {reason}'}), 400
        return render_template('errors/400.html', error=reason), 400

    @app.errorhandler(403)
    def forbidden(e):
        actor = current_user.username if (hasattr(current_user, 'is_authenticated') and current_user.is_authenticated) else 'anonymous'
        app.logger.warning(f"Security Alert: 403 Forbidden access attempt on {request.path} by user='{actor}' from ip={request.remote_addr}")
        if request.path.startswith('/api/'):
            return jsonify({'success': False, 'error': 'Forbidden: Insufficient permissions'}), 403
        return render_template('errors/403.html'), 403

    @app.errorhandler(404)
    def page_not_found(e):
        if request.path.startswith('/api/'):
            return jsonify({'success': False, 'error': 'Resource not found'}), 404
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def internal_server_error(e):
        if request.path.startswith('/api/'):
            return jsonify({'success': False, 'error': 'Internal server error'}), 500
        return render_template('errors/500.html'), 500

    # CLI commands
    @app.cli.command('init-db')
    def init_db_command():
        """Create all database tables."""
        with app.app_context():
            import models  # noqa: F401
            db.create_all()
            click.echo("Initialized the database tables successfully.")

    @app.cli.command('seed-db')
    def seed_db_command():
        """Seed the database with realistic demo data."""
        with app.app_context():
            import models  # noqa: F401
            db.create_all()
            from seed import seed_database
            seed_database()
            click.echo("Database seeded successfully with demo projects, users, and issues.")

    return app


app = create_app()

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=True)
