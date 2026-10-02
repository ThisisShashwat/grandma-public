from pathlib import Path

from flask import Flask

from . import web
from .routes import home

ROOT = Path(__file__).resolve().parent.parent


def create_app():
    app = Flask(__name__, static_folder=ROOT / "static", template_folder=ROOT / "templates")
    app.jinja_env.trim_blocks = True
    app.jinja_env.lstrip_blocks = True
    app.context_processor(web.context)
    app.register_blueprint(home.bp)
    return app
