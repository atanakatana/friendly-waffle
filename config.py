import os
# mendapat path absolute dari direktori saat ini
basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    # konfigurasi database SQLite
    # mengarahkan database ke folder 'app' di dalam direktori proyek
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(basedir, 'app', 'penjualan.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # nanti DSECRET_KEY juga ditaruh di sini
    # SECRET_KEY = os.environ.get('SECRET_KEY') or 'tidak-akan-bisa-menebak'
    
    # harga konstan
    HARGA_BELI_DEFAULT = 8000
    HARGA_JUAL_DEFAULT = 10000
    # menambah konstanta profit sharing
    # total profit per produk = 10000 - 8000 = 2000
    # profit owner = 75% x 2000 = 1500
    # profit superowner = 25% x 2000 = 500
    PROFIT_SHARE_OWNER_RATIO = 0.75
    PROFIT_SHARE_SUPEROWNER_RATIO = 0.25