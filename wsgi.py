"""
WSGI Production Entrypoint for SmartShelf.
Runs the production server via Waitress (Windows compatible multi-threaded WSGI server).
"""
import os
from app import create_app
from config import ProductionConfig, DevelopmentConfig

env = os.getenv("FLASK_ENV", "production").lower()
config_class = DevelopmentConfig if env == "development" else ProductionConfig
application = create_app(config_class)

if __name__ == "__main__":
    from waitress import serve
    port = int(os.getenv("PORT", 5000))
    host = os.getenv("HOST", "127.0.0.1")
    print(f"Starting SmartShelf Production Server on http://{host}:{port}")
    serve(application, host=host, port=port, threads=6)
