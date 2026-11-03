from flask import Flask
from .config import Config

def create_app(config_obj=Config):
    app = Flask(__name__)
    app.config.from_object(config_obj)

    # Import routes (they register blueprint)
    from . import app as api_app  # noqa: F401
    app.register_blueprint(api_app.bp)

    # Optional Basic Auth middleware
    username = app.config.get("CONSOLE_USERNAME", "")
    password = app.config.get("CONSOLE_PASSWORD", "")
    if username and password:
        from flask import request, jsonify

        @app.before_request
        def check_auth():
            if request.path.startswith("/static"):
                return None
            auth = request.authorization
            if not auth or auth.username != username or auth.password != password:
                return jsonify({"error": "Unauthorized"}), 401

    return app