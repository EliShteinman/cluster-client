from app.config import Settings
from app.main import create_app
from app.server import serve

if __name__ == "__main__":
    settings: Settings = Settings()
    serve(app=create_app(settings=settings), settings=settings.server)
