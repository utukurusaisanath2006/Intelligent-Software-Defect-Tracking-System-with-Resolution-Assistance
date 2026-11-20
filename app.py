"""IntelliTrack Flask Application Factory and CLI commands."""

import os
import click
from datetime import datetime
from flask import Flask, render_template, request, jsonify, url_for
from flask_login import current_user
from markupsafe import Markup, escape
from config import config
from extensions import db, login_manager, csrf
from routes import register_blueprints


def create_app(config_name=None):
    """Application factory for IntelliTrack."""
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')

    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config.get(config_name, config['default']))

    # Ensure instance and upload directories exist
    os.makedirs(app.instance_path, exist_ok=True)
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # Initialize extensions
    db.init_app(app)
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

    # Security headers
    @app.after_request
    def set_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        return response

    # Error handlers
    @app.errorhandler(403)
    def forbidden(e):
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
