from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from config import Config # memanggil file config dari config.py

# inisialisasi sqlalchemy (belum dihubungkan ke app)
db = SQLAlchemy()

# buat app factory
def create_app(config_class=Config):
    app = Flask(__name__)
    # load konfigurasi dari class Config di config.py
    app.config.from_object(config_class)

    # inisialisasi db dengan menghubungkan ke app
    db.init_app(app)

    # mendaftarkan blueprints
    from .routes.auth_routes import auth_bp
    app.register_blueprint(auth_bp)
    
    from .routes.owner_routes import owner_bp
    app.register_blueprint(owner_bp)
    
    from .routes.lapak_routes import lapak_bp
    app.register_blueprint(lapak_bp)
    
    from .routes.supplier_routes import supplier_bp
    app.register_blueprint(supplier_bp)
    
    from .routes.superowner_routes import superowner_bp
    app.register_blueprint(superowner_bp)
    
    @app.route('/')
    def index():
      # akan diganti agar merender login.html (akan diurus auth_routes.py)
      # sementara diarahkan ke rute login
        from flask import redirect, url_for
        return redirect(url_for('auth.login_page'))

    return app
