from flask import Flask
from src.config import Config


def create_app(config=None):
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config.from_object(Config)
    if config:
        app.config.update(config)

    from src.views.main import bp as main_bp
    from src.api.routes import bp as api_bp
    from src.api.auth import bp as auth_bp
    from src.api.trade import bp as trade_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp, url_prefix="/api")
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(trade_bp, url_prefix="/trade")

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=Config.DEBUG)
