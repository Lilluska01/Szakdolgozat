from flask import Flask, jsonify
from config.config import Config
from web.routes.user_routes import user_bp
from web.routes.access_routes import access_bp
from web.routes.auth_routes import auth_bp
from web.routes.page_routes import page_bp
from web.routes.course_routes import course_bp
from web.routes.session_routes import session_bp
from web.routes.analytics_routes import analytics_bp
from web.routes.import_routes import import_bp
from web.routes.export_routes import export_bp
from web.routes.health_routes import health_bp
from web.routes.docs_routes import docs_bp


def create_app(test_config=None):
    app = Flask(__name__)
    app.config['SECRET_KEY'] = Config.SECRET_KEY
    app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024
    app.config['JSON_SORT_KEYS'] = False
    if test_config:
        app.config.update(test_config)
    app.register_blueprint(user_bp, url_prefix='/api/users')
    app.register_blueprint(access_bp, url_prefix='/api/access')
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(course_bp, url_prefix='/api/courses')
    app.register_blueprint(session_bp, url_prefix='/api/sessions')
    app.register_blueprint(analytics_bp, url_prefix='/api/analytics')
    app.register_blueprint(import_bp, url_prefix='/api/users/import')
    app.register_blueprint(export_bp, url_prefix='/api/export')
    app.register_blueprint(health_bp, url_prefix='/api/health')
    app.register_blueprint(docs_bp, url_prefix='/api/docs')
    app.register_blueprint(page_bp)

    @app.get('/api/health')
    def health():
        return jsonify({'status': 'ok'})

    @app.errorhandler(404)
    def not_found(_error):
        return jsonify({'error': 'not_found', 'message': 'A kért erőforrás nem található.'}), 404

    @app.errorhandler(413)
    def too_large(_error):
        return jsonify({'error': 'payload_too_large'}), 413

    return app





