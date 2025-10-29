import datetime
import re
import random
from datetime import timedelta
from flask import Flask, render_template, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import IntegrityError
from sqlalchemy.sql import func, or_
from sqlalchemy.orm import joinedload
from calendar import monthrange
import logging

# Inisialisasi aplikasi Flask
app = Flask(__name__)
# Konfigurasi database SQLite
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///penjualan.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Setup logging
logging.basicConfig(level=logging.INFO)

# Inisialisasi SQLAlchemy
db = SQLAlchemy(app)

# --- HARGA KONSTAN (SEBAGAI DEFAULT) ---
HARGA_BELI_DEFAULT = 8000
HARGA_JUAL_DEFAULT = 10000

# menambah konstanta profit sharing
# total profit per produk = 10000 - 8000 = 2000
# profit owner = 75% x 2000 = 1500
# profit superowner = 25% x 2000 = 500
PROFIT_SHARE_OWNER_RATIO = 0.75
PROFIT_SHARE_SUPEROWNER_RATIO = 0.25
# ===================================================================
# DEFINISI MODEL DATABASE
# ===================================================================

product_lapak_association = db.Table('product_lapak',
    db.Column('product_id', db.Integer, db.ForeignKey('product.id'), primary_key=True),
    db.Column('lapak_id', db.Integer, db.ForeignKey('lapak.id'), primary_key=True)
)

lapak_anggota_association = db.Table('lapak_anggota',
    db.Column('lapak_id', db.Integer, db.ForeignKey('lapak.id'), primary_key=True),
    db.Column('admin_id', db.Integer, db.ForeignKey('admin.id'), primary_key=True)
)

class Admin(db.Model):
    __tablename__ = 'admin'
    id = db.Column(db.Integer, primary_key=True)
    nama_lengkap = db.Column(db.String(100), nullable=False)
    nik = db.Column(db.String(20), unique=True, nullable=False)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    nomor_kontak = db.Column(db.String(20), nullable=True)
    password = db.Column(db.String(120), nullable=False)
    #relasi ke super owner
    super_owner_id= db.Column(db.Integer, db.ForeignKey('super_owner.id'), nullable=True)

class SuperOwner(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nama_lengkap = db.Column(db.String(100), nullable=True) 
    nik = db.Column(db.String(20), unique=True, nullable=True)
    username = db.Column(db.String(80), unique=True, nullable=False) # Username tetap wajib
    email = db.Column(db.String(120), unique=True, nullable=True)
    nomor_kontak = db.Column(db.String(20), nullable=True)
    password = db.Column(db.String(120), nullable=False) # Password tetap wajib
    #relasi ke owner
    owners= db.relationship('Admin', backref='super_owner', lazy=True)

class Supplier(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nama_supplier = db.Column(db.String(100), nullable=False)
    username = db.Column(db.String(80), unique=True, nullable=False) 
    kontak = db.Column(db.String(20), nullable=True)
    nomor_register = db.Column(db.String(50), unique=True, nullable=True)
    alamat = db.Column(db.Text, nullable=True)
    password = db.Column(db.String(120), nullable=False)
    # --- REVISI: Kolom baru untuk info pembayaran ---
    metode_pembayaran = db.Column(db.String(20), nullable=True)
    nomor_rekening = db.Column(db.String(50), nullable=True)
    products = db.relationship('Product', backref='supplier', lazy=True, cascade="all, delete-orphan")
    balance = db.relationship('SupplierBalance', backref='supplier', uselist=False, cascade="all, delete-orphan")

class Lapak(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lokasi = db.Column(db.String(200), nullable=False, unique=True)
    user_id = db.Column(db.Integer, db.ForeignKey('admin.id'), nullable=False) # Penanggung Jawab
    penanggung_jawab = db.relationship('Admin', foreign_keys=[user_id], backref=db.backref('lapak_pj', uselist=False))
    anggota = db.relationship('Admin', secondary=lapak_anggota_association, lazy='subquery',
                              backref=db.backref('lapak_anggota', lazy=True))
    reports = db.relationship('LaporanHarian', backref='lapak', lazy=True, cascade="all, delete-orphan")

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nama_produk = db.Column(db.String(100), nullable=False)
    supplier_id = db.Column(db.Integer, db.ForeignKey('supplier.id'), nullable=True)
    harga_beli = db.Column(db.Float, nullable=False, default=HARGA_BELI_DEFAULT)
    harga_jual = db.Column(db.Float, nullable=False, default=HARGA_JUAL_DEFAULT)
    is_manual = db.Column(db.Boolean, default=False, nullable=False)
    lapaks = db.relationship('Lapak', secondary=product_lapak_association, lazy='subquery',
                             backref=db.backref('products', lazy=True))

class StokHarian(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lapak_id = db.Column(db.Integer, db.ForeignKey('lapak.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    jumlah_sisa = db.Column(db.Integer, nullable=False)
    tanggal = db.Column(db.Date, default=datetime.date.today, nullable=False)
    __table_args__ = (db.UniqueConstraint('lapak_id', 'product_id', 'tanggal', name='_lapak_product_date_uc'),)

class LaporanHarian(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lapak_id = db.Column(db.Integer, db.ForeignKey('lapak.id'), nullable=False)
    tanggal = db.Column(db.Date, nullable=False, default=datetime.date.today)
    total_pendapatan = db.Column(db.Float, nullable=False)
    total_biaya_supplier = db.Column(db.Float, nullable=False, default=0)
    pendapatan_cash = db.Column(db.Float, nullable=False)
    pendapatan_qris = db.Column(db.Float, nullable=False)
    pendapatan_bca = db.Column(db.Float, nullable=False) 
    total_produk_terjual = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), default='Menunggu Konfirmasi')
    manual_pendapatan_cash = db.Column(db.Float, nullable=True)
    manual_pendapatan_qris = db.Column(db.Float, nullable=True)
    manual_pendapatan_bca = db.Column(db.Float, nullable=True)
    manual_total_pendapatan = db.Column(db.Float, nullable=True)
    #kolom tambahan untuk profit sharing
    keuntungan_owner = db.Column(db.Float, nullable=True, default=0.0)
    keuntungan_superowner = db.Column(db.Float, nullable=True, default=0.0)
    rincian_produk = db.relationship('LaporanHarianProduk', backref='laporan', lazy=True, cascade="all, delete-orphan")

class LaporanHarianProduk(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    laporan_id = db.Column(db.Integer, db.ForeignKey('laporan_harian.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    stok_awal = db.Column(db.Integer, nullable=False)
    stok_akhir = db.Column(db.Integer, nullable=False)
    jumlah_terjual = db.Column(db.Integer, nullable=False)
    total_harga_jual = db.Column(db.Float, nullable=False)
    total_harga_beli = db.Column(db.Float, nullable=False)
    product = db.relationship('Product')

class SupplierBalance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey('supplier.id'), unique=True, nullable=False)
    balance = db.Column(db.Float, nullable=False, default=0.0)
    
class SuperOwnerBalance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    super_owner_id = db.Column(db.Integer, db.ForeignKey('super_owner.id'), nullable=False)
    owner_id = db.Column(db.Integer, db.ForeignKey('admin.id'), nullable=False)
    balance = db.Column(db.Float, nullable=False, default=0.0)
    
    super_owner = db.relationship('SuperOwner')
    owner = db.relationship('Admin')
    __table_args__ = (db.UniqueConstraint('super_owner_id', 'owner_id', name='_superowner_owner_uc'),)

class PembayaranSupplier(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey('supplier.id'), nullable=False)
    tanggal_pembayaran = db.Column(db.Date, nullable=False, default=datetime.date.today)
    jumlah_pembayaran = db.Column(db.Float, nullable=False)
    metode_pembayaran = db.Column(db.String(20), nullable=False) 
    supplier = db.relationship('Supplier')

# (Letakkan ini setelah kelas 'PembayaranSupplier')

class Notifikasi(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    lapak_id = db.Column(db.Integer, db.ForeignKey('lapak.id'), nullable=False)
    supplier_id = db.Column(db.Integer, db.ForeignKey('supplier.id'), nullable=False)
    waktu_dikirim = db.Column(db.DateTime, server_default=func.now())
    status = db.Column(db.String(20), default='baru', nullable=False) # Status: 'baru' atau 'dibaca'

    # Relasi untuk memudahkan pengambilan data
    product = db.relationship('Product')
    lapak = db.relationship('Lapak')
    supplier = db.relationship('Supplier')
    
# (Letakkan ini setelah kelas 'Notifikasi')

class RiwayatPenarikanSuperOwner(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    super_owner_id = db.Column(db.Integer, db.ForeignKey('super_owner.id'), nullable=False)
    jumlah_penarikan = db.Column(db.Float, nullable=False)
    tanggal_penarikan = db.Column(db.DateTime, server_default=func.now())

    super_owner = db.relationship('SuperOwner')

# ===================================================================
# CLI & Rute Halaman
# ===================================================================
@app.cli.command("init-db")
def init_db_command():
    db.create_all()
    print("Database telah diinisialisasi.")
    
# GANTI FUNGSI LAMA DENGAN VERSI BARU INI
@app.cli.command("seed-db")
def seed_db_command():
    """Menghapus database dan membuat data pengguna inti saja."""
    db.drop_all()
    db.create_all()
    print("Database dibersihkan dan struktur baru dibuat...")

    # ===================================================================
    # 1. BUAT PENGGUNA INTI (SUPEROWNER, OWNER, ADMIN LAPAK)
    # ===================================================================
    super_owner = SuperOwner(username="superowner", password="superowner", nama_lengkap="Super Owner Utama")
    db.session.add(super_owner)
    db.session.flush() 

    owner_utama = Admin(nama_lengkap="Owner Utama", nik="1000000000", username="owner", email="owner@app.com", password="owner", super_owner_id=super_owner.id)
    admin_andi = Admin(nama_lengkap="Andi (PJ Kopo)", nik="1111111111", username="andi", email="andi@app.com", password="andi")
    admin_budi = Admin(nama_lengkap="Budi (PJ Buah Batu)", nik="2222222222", username="budi", email="budi@app.com", password="budi")
    db.session.add_all([owner_utama, admin_andi, admin_budi])
    db.session.commit()
    print("=> Pengguna (SuperOwner, Owner, Admin) berhasil dibuat.")

    # Inisialisasi Saldo Awal SuperOwner untuk Owner Utama (wajib ada untuk logika profit)
    db.session.add(SuperOwnerBalance(super_owner_id=super_owner.id, owner_id=owner_utama.id, balance=0.0))
    db.session.commit()

    print("\nDatabase siap dengan data pengguna inti. Silakan jalankan aplikasi.")
    
@app.route('/')
def login_page():
    return render_template('index.html')
# ===================================================================
# ENDPOINTS API
# ===================================================================
@app.route('/api/login', methods=['POST'])
def handle_login():
    data = request.json
    username = data.get('username', '').lower()
    password = data.get('password')
    admin = Admin.query.filter(db.func.lower(Admin.username) == username).first()
    if admin and admin.password == password:
        if admin.username == 'owner':
            return jsonify({"success": True, "role": "owner", "user_info": {"nama_lengkap": admin.nama_lengkap, "id": admin.id}})
        else:
            lapak_info = Lapak.query.filter(or_(Lapak.user_id == admin.id, Lapak.anggota.any(id=admin.id))).first()
            return jsonify({"success": True, "role": "lapak", "user_info": {"nama_lengkap": admin.nama_lengkap, "lapak_id": lapak_info.id if lapak_info else None, "id": admin.id}})
    supplier = Supplier.query.filter(db.func.lower(Supplier.username) == username).first()
    if supplier and supplier.password == password:
        return jsonify({"success": True, "role": "supplier", "user_info": {"nama_supplier": supplier.nama_supplier,"supplier_id": supplier.id}})
      
    #tambahan untuk superowner
    superowner = SuperOwner.query.filter(db.func.lower(SuperOwner.username) == username).first()
    if superowner and superowner.password == password:
        return jsonify({"success": True, "role": "superowner", "user_info": {"username": superowner.username, "id": superowner.id}})
    return jsonify({"success": False, "message": "Username atau password salah"}), 401
# --- OWNER API ---
# GANTI FUNGSI LAMA DENGAN VERSI BARU INI
@app.route('/api/get_data_owner', methods=['GET'])
def get_owner_data():
    try:
        admins = Admin.query.filter(Admin.username != 'owner').all()
        lapaks = Lapak.query.options(joinedload(Lapak.penanggung_jawab), joinedload(Lapak.anggota)).all()
        suppliers = Supplier.query.all()
        
        admin_list = [{"id": u.id, "nama_lengkap": u.nama_lengkap, "nik": u.nik, "username": u.username, "email": u.email, "nomor_kontak": u.nomor_kontak, "password": u.password} for u in admins]
        lapak_list = [{"id": l.id, "lokasi": l.lokasi, "penanggung_jawab": f"{l.penanggung_jawab.nama_lengkap}", "user_id": l.user_id, "anggota": [{"id": a.id, "nama": a.nama_lengkap} for a in l.anggota], "anggota_ids": [a.id for a in l.anggota]} for l in lapaks]
        supplier_list = []
        for s in suppliers:
            products = Product.query.filter_by(supplier_id=s.id).all()
            product_list = [{"id": p.id, "name": p.nama_produk, "harga_beli": p.harga_beli, "harga_jual": p.harga_jual} for p in products]
            lapak_ids = [lapak.id for lapak in products[0].lapaks] if products else []
            supplier_list.append({
                "id": s.id, "nama_supplier": s.nama_supplier, "username": s.username, "kontak": s.kontak, 
                "nomor_register": s.nomor_register, "alamat": s.alamat, "password": s.password, 
                "metode_pembayaran": s.metode_pembayaran, "nomor_rekening": s.nomor_rekening,
                "products": product_list, "lapak_ids": lapak_ids
            })
        
        today = datetime.date.today()
        start_of_month = today.replace(day=1)
        
        # Kalkulasi lama (tetap ada)
        total_pendapatan_bulan_ini = db.session.query(func.sum(LaporanHarian.total_pendapatan)).filter(LaporanHarian.tanggal >= start_of_month, LaporanHarian.status == 'Terkonfirmasi').scalar() or 0
        total_biaya_bulan_ini = db.session.query(func.sum(PembayaranSupplier.jumlah_pembayaran)).filter(PembayaranSupplier.tanggal_pembayaran >= start_of_month).scalar() or 0

        # === LOGIKA BARU UNTUK KPI PROFIT OWNER ===
        profit_owner_bulan_ini = db.session.query(func.sum(LaporanHarian.keuntungan_owner))\
            .filter(LaporanHarian.tanggal >= start_of_month, LaporanHarian.status == 'Terkonfirmasi').scalar() or 0
        
        profit_superowner_bulan_ini = db.session.query(func.sum(LaporanHarian.keuntungan_superowner))\
            .filter(LaporanHarian.tanggal >= start_of_month, LaporanHarian.status == 'Terkonfirmasi').scalar() or 0
        # === AKHIR LOGIKA BARU ===

        summary_data = {
            "pendapatan_bulan_ini": total_pendapatan_bulan_ini, 
            "biaya_bulan_ini": total_biaya_bulan_ini,
            "profit_owner_bulan_ini": profit_owner_bulan_ini, # Data baru
            "profit_superowner_bulan_ini": profit_superowner_bulan_ini # Data baru
        }
        
        return jsonify({"admin_data": admin_list, "lapak_data": lapak_list, "supplier_data": supplier_list, "summary": summary_data})
    except Exception as e:
        return jsonify({"success": False, "message": f"Terjadi kesalahan server: {str(e)}"}), 500
      
# GANTI FUNGSI LAMA DENGAN VERSI BARU INI
@app.route('/api/add_admin', methods=['POST'])
def add_admin():
    data = request.json
    if data['password'] != data['password_confirm']: return jsonify({"success": False, "message": "Password dan konfirmasi password tidak cocok."}), 400
    try:
        new_admin = Admin(
            nama_lengkap=data['nama_lengkap'], 
            nik=data['nik'], 
            username=data['username'], 
            email=data['email'], 
            nomor_kontak=data['nomor_kontak'], 
            password=data['password'],
            # PERUBAHAN DI SINI: Terima super_owner_id jika ada
            super_owner_id=data.get('super_owner_id') 
        )
        db.session.add(new_admin)
        db.session.commit()
        return jsonify({"success": True, "message": "Admin/Owner berhasil ditambahkan"})
    except IntegrityError:
        db.session.rollback()
        return jsonify({"success": False, "message": "Gagal: Username, NIK, atau email sudah ada."}), 400

@app.route('/api/update_admin/<int:admin_id>', methods=['PUT'])
def update_admin(admin_id):
    data = request.json
    admin = Admin.query.get_or_404(admin_id)
    if data.get('password') and data['password'] != data['password_confirm']: return jsonify({"success": False, "message": "Password dan konfirmasi password tidak cocok."}), 400
    try:
        admin.nama_lengkap = data['nama_lengkap']
        admin.nik = data['nik']
        admin.username = data['username']
        admin.email = data['email']
        admin.nomor_kontak = data['nomor_kontak']
        if data.get('password'): admin.password = data['password']
        db.session.commit()
        return jsonify({"success": True, "message": "Data Admin berhasil diperbarui"})
    except IntegrityError:
        db.session.rollback()
        return jsonify({"success": False, "message": "Gagal: Username, NIK, atau email sudah digunakan oleh admin lain."}), 400

@app.route('/api/delete_admin/<int:admin_id>', methods=['DELETE'])
def delete_admin(admin_id):
    admin = Admin.query.get_or_404(admin_id)
    if Lapak.query.filter_by(user_id=admin_id).first(): return jsonify({"success": False, "message": "Gagal menghapus: Admin ini adalah Penanggung Jawab sebuah lapak."}), 400
    db.session.delete(admin)
    db.session.commit()
    return jsonify({"success": True, "message": "Admin berhasil dihapus"})

@app.route('/api/add_lapak', methods=['POST'])
def add_lapak():
    data = request.json
    try:
        new_lapak = Lapak(lokasi=data['lokasi'], user_id=data['user_id'])
        anggota_ids = data.get('anggota_ids', [])
        if anggota_ids: new_lapak.anggota = Admin.query.filter(Admin.id.in_(anggota_ids)).all()
        db.session.add(new_lapak)
        db.session.commit()
        return jsonify({"success": True, "message": "Lapak berhasil ditambahkan"})
    except IntegrityError:
        db.session.rollback()
        return jsonify({"success": False, "message": "Nama lokasi lapak sudah ada."}), 400

@app.route('/api/update_lapak/<int:lapak_id>', methods=['PUT'])
def update_lapak(lapak_id):
    data = request.json
    lapak = Lapak.query.get_or_404(lapak_id)
    try:
        lapak.lokasi = data['lokasi']
        lapak.user_id = data['user_id']
        anggota_ids = data.get('anggota_ids', [])
        lapak.anggota = Admin.query.filter(Admin.id.in_(anggota_ids)).all()
        db.session.commit()
        return jsonify({"success": True, "message": "Data Lapak berhasil diperbarui"})
    except IntegrityError:
        db.session.rollback()
        return jsonify({"success": False, "message": "Nama lokasi lapak sudah digunakan."}), 400

@app.route('/api/delete_lapak/<int:lapak_id>', methods=['DELETE'])
def delete_lapak(lapak_id):
    lapak = Lapak.query.get_or_404(lapak_id)
    db.session.delete(lapak)
    db.session.commit()
    return jsonify({"success": True, "message": "Lapak berhasil dihapus"})

# --- REVISI: Logika baru untuk nomor registrasi ---
@app.route('/api/get_next_supplier_reg_number', methods=['GET'])
def get_next_supplier_reg_number():
    used_numbers = set()
    suppliers = Supplier.query.filter(Supplier.nomor_register.like('REG%')).all()
    for s in suppliers:
        num_part = re.search(r'\d+', s.nomor_register)
        if num_part:
            used_numbers.add(int(num_part.group()))
    
    next_id = 1
    while next_id in used_numbers:
        next_id += 1
        
    return jsonify({"success": True, "reg_number": f"REG{next_id:03d}"})

# --- REVISI: Tambahkan metode pembayaran & no rekening ---
@app.route('/api/add_supplier', methods=['POST'])
def add_supplier():
    data = request.json
    if data['password'] != data['password_confirm']:
        return jsonify({"success": False, "message": "Password dan konfirmasi password tidak cocok."}), 400
    
    try:
        new_supplier = Supplier(
            nama_supplier=data['nama_supplier'],
            username=data.get('username'),
            kontak=data.get('kontak'),
            nomor_register=data.get('nomor_register'),
            alamat=data.get('alamat'),
            password=data['password'],
            metode_pembayaran=data.get('metode_pembayaran'),
            nomor_rekening=data.get('nomor_rekening')
        )
        new_supplier.balance = SupplierBalance(balance=0.0)
        db.session.add(new_supplier)
        db.session.commit()
        return jsonify({"success": True, "message": "Supplier berhasil ditambahkan"})
    except IntegrityError:
        db.session.rollback()
        return jsonify({"success": False, "message": "Gagal: Username atau Nomor Register sudah ada."}), 400
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error adding supplier: {str(e)}")
        return jsonify({"success": False, "message": f"Terjadi kesalahan server: {str(e)}"}), 500

# --- REVISI: Update metode pembayaran & no rekening ---
@app.route('/api/update_supplier/<int:supplier_id>', methods=['PUT'])
def update_supplier(supplier_id):
    data = request.json
    supplier = Supplier.query.get_or_404(supplier_id)

    if data.get('password') and data['password'] != data['password_confirm']:
        return jsonify({"success": False, "message": "Password dan konfirmasi password tidak cocok."}), 400

    try:
        supplier.nama_supplier = data['nama_supplier']
        supplier.username = data.get('username')
        supplier.kontak = data.get('kontak')
        supplier.alamat = data.get('alamat')
        supplier.metode_pembayaran = data.get('metode_pembayaran')
        supplier.nomor_rekening = data.get('nomor_rekening')
        if data.get('password'):
            supplier.password = data['password']
        
        db.session.commit()
        return jsonify({"success": True, "message": "Data Supplier berhasil diperbarui"})
    except IntegrityError:
        db.session.rollback()
        return jsonify({"success": False, "message": "Gagal: Username sudah digunakan oleh supplier lain."}), 400
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error updating supplier: {str(e)}")
        return jsonify({"success": False, "message": f"Terjadi kesalahan server: {str(e)}"}), 500

@app.route('/api/delete_supplier/<int:supplier_id>', methods=['DELETE'])
def delete_supplier(supplier_id):
    supplier = Supplier.query.get_or_404(supplier_id)
    db.session.delete(supplier)
    db.session.commit()
    return jsonify({"success": True, "message": "Supplier berhasil dihapus"})

@app.route('/api/get_owner_supplier_history/<int:supplier_id>', methods=['GET'])
def get_owner_supplier_history(supplier_id):
    try:
        # Ambil parameter tanggal dari request
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')

        # Query dasar untuk pembayaran
        payments_query = PembayaranSupplier.query.filter_by(supplier_id=supplier_id)
        
        # Query dasar untuk penjualan
        sales_query = db.session.query(
            LaporanHarian.tanggal, Lapak.lokasi, Product.nama_produk,
            LaporanHarianProduk.jumlah_terjual, LaporanHarianProduk.total_harga_beli
        ).select_from(LaporanHarianProduk)\
         .join(Product, Product.id == LaporanHarianProduk.product_id)\
         .join(LaporanHarian, LaporanHarian.id == LaporanHarianProduk.laporan_id)\
         .join(Lapak, Lapak.id == LaporanHarian.lapak_id)\
         .filter(Product.supplier_id == supplier_id, LaporanHarian.status == 'Terkonfirmasi')

        # Terapkan filter tanggal jika ada
        if start_date_str:
            start_date = datetime.datetime.strptime(start_date_str, '%Y-%m-%d').date()
            payments_query = payments_query.filter(PembayaranSupplier.tanggal_pembayaran >= start_date)
            sales_query = sales_query.filter(LaporanHarian.tanggal >= start_date)
        
        if end_date_str:
            end_date = datetime.datetime.strptime(end_date_str, '%Y-%m-%d').date()
            payments_query = payments_query.filter(PembayaranSupplier.tanggal_pembayaran <= end_date)
            sales_query = sales_query.filter(LaporanHarian.tanggal <= end_date)

        # Eksekusi query setelah filter diterapkan
        payments = payments_query.order_by(PembayaranSupplier.tanggal_pembayaran.desc()).all()
        sales = sales_query.order_by(LaporanHarian.tanggal.desc(), Lapak.lokasi).all()

        # Proses hasil
        payment_list = [{"tanggal": p.tanggal_pembayaran.strftime('%Y-%m-%d'), "jumlah": p.jumlah_pembayaran, "metode": p.metode_pembayaran} for p in payments]
        sales_list = [{"tanggal": s.tanggal.strftime('%Y-%m-%d'), "lokasi": s.lokasi, "nama_produk": s.nama_produk, "terjual": s.jumlah_terjual, "total_harga_beli": s.total_harga_beli} for s in sales]
        
        return jsonify({"success": True, "payments": payment_list, "sales": sales_list})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
# --- OWNER API (Laporan & Pembayaran) ---
# TAMBAHKAN DUA FUNGSI BARU INI DI app.py

@app.route('/api/get_laporan_pendapatan_harian')
def get_laporan_pendapatan_harian():
    try:
        date_str = request.args.get('date')
        target_date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()

        reports = LaporanHarian.query.options(
            joinedload(LaporanHarian.lapak),
            joinedload(LaporanHarian.rincian_produk).joinedload(LaporanHarianProduk.product).joinedload(Product.supplier)
        ).filter(
            LaporanHarian.tanggal == target_date,
            LaporanHarian.status == 'Terkonfirmasi'
        ).all()

        total_harian = sum(r.total_pendapatan for r in reports)
        laporan_per_lapak = []

        for report in reports:
            rincian_pendapatan = []
            for item in report.rincian_produk:
                if item.jumlah_terjual > 0:
                    rincian_pendapatan.append({
                        "produk": item.product.nama_produk,
                        "supplier": item.product.supplier.nama_supplier if item.product.supplier else "N/A",
                        "stok_awal": item.stok_awal,
                        "stok_akhir": item.stok_akhir,
                        "jumlah": item.jumlah_terjual
                    })
            
            if rincian_pendapatan:
                 laporan_per_lapak.append({
                    "lokasi": report.lapak.lokasi,
                    "penanggung_jawab": report.lapak.penanggung_jawab.nama_lengkap,
                    "total_pendapatan": report.total_pendapatan,
                    "rincian_pendapatan": rincian_pendapatan
                })

        return jsonify({
            "total_harian": total_harian,
            "laporan_per_lapak": laporan_per_lapak
        })

    except Exception as e:
        logging.error(f"Error fetching pendapatan harian: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/get_laporan_biaya_harian')
def get_laporan_biaya_harian():
    try:
        date_str = request.args.get('date')
        target_date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()

        reports = LaporanHarian.query.options(
            joinedload(LaporanHarian.lapak),
            joinedload(LaporanHarian.rincian_produk).joinedload(LaporanHarianProduk.product).joinedload(Product.supplier)
        ).filter(
            LaporanHarian.tanggal == target_date,
            LaporanHarian.status == 'Terkonfirmasi'
        ).all()

        total_harian = sum(r.total_biaya_supplier for r in reports)
        laporan_per_lapak = []

        for report in reports:
            rincian_biaya = []
            for item in report.rincian_produk:
                 if item.jumlah_terjual > 0:
                    rincian_biaya.append({
                        "produk": item.product.nama_produk,
                        "supplier": item.product.supplier.nama_supplier if item.product.supplier else "N/A",
                        "jumlah": item.jumlah_terjual,
                        "biaya": item.total_harga_beli
                    })
            
            if rincian_biaya:
                laporan_per_lapak.append({
                    "lokasi": report.lapak.lokasi,
                    "penanggung_jawab": report.lapak.penanggung_jawab.nama_lengkap,
                    "total_biaya": report.total_biaya_supplier,
                    "rincian_biaya": rincian_biaya
                })

        return jsonify({
            "total_harian": total_harian,
            "laporan_per_lapak": laporan_per_lapak
        })

    except Exception as e:
        logging.error(f"Error fetching biaya harian: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/get_manage_reports')
def get_manage_reports():
    try:
        # Ambil semua parameter dari request
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        supplier_id = request.args.get('supplier_id')

        # Query dasar untuk semua laporan
        query = LaporanHarian.query.options(
            joinedload(LaporanHarian.lapak).joinedload(Lapak.penanggung_jawab)
        )

        # Terapkan filter tanggal jika ada
        if start_date_str:
            start_date = datetime.datetime.strptime(start_date_str, '%Y-%m-%d').date()
            query = query.filter(LaporanHarian.tanggal >= start_date)
        
        if end_date_str:
            end_date = datetime.datetime.strptime(end_date_str, '%Y-%m-%d').date()
            query = query.filter(LaporanHarian.tanggal <= end_date)
        
        # --- PERUBAHAN LOGIKA DI SINI ---
        # Terapkan filter supplier jika ada
        if supplier_id:
            # Join ke tabel-tabel terkait untuk menemukan supplier_id
            query = query.join(LaporanHarian.rincian_produk)\
                         .join(LaporanHarianProduk.product)\
                         .filter(Product.supplier_id == supplier_id)\
                         .distinct() # Gunakan distinct untuk menghindari duplikat laporan

        reports = query.order_by(LaporanHarian.tanggal.desc()).all()
        
        report_list = [{
            "id": r.id, 
            "lokasi": r.lapak.lokasi, 
            "penanggung_jawab": r.lapak.penanggung_jawab.nama_lengkap, 
            "tanggal": r.tanggal.isoformat(), 
            "total_pendapatan": r.total_pendapatan, 
            "total_produk_terjual": r.total_produk_terjual, 
            "status": r.status,
            "keuntungan_owner": r.keuntungan_owner, # Data baru
            "keuntungan_superowner": r.keuntungan_superowner # Data baru
        } for r in reports]
        return jsonify({"success": True, "reports": report_list})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

# GANTI FUNGSI LAMA DENGAN VERSI BARU INI
@app.route('/api/confirm_report/<int:report_id>', methods=['POST'])
def confirm_report(report_id):
    try:
        report = LaporanHarian.query.options(
            joinedload(LaporanHarian.rincian_produk).joinedload(LaporanHarianProduk.product).joinedload(Product.supplier).joinedload(Supplier.balance),
            joinedload(LaporanHarian.lapak).joinedload(Lapak.penanggung_jawab)
        ).get(report_id)

        if not report: return jsonify({"success": False, "message": "Laporan tidak ditemukan."}), 404
        if report.status == 'Terkonfirmasi': return jsonify({"success": False, "message": "Laporan ini sudah dikonfirmasi."}), 400

        report.status = 'Terkonfirmasi'
        
        for rincian in report.rincian_produk:
            if rincian.product.supplier and rincian.product.supplier.balance:
                rincian.product.supplier.balance.balance += rincian.total_harga_beli
            
        total_profit = report.total_pendapatan - report.total_biaya_supplier
        keuntungan_superowner = total_profit * PROFIT_SHARE_SUPEROWNER_RATIO
        keuntungan_owner = total_profit * PROFIT_SHARE_OWNER_RATIO
        report.keuntungan_owner = keuntungan_owner
        report.keuntungan_superowner = keuntungan_superowner
        
        # === LOGIKA BARU UNTUK MENEMUKAN OWNER YANG BENAR ===
        # Asumsi: Setiap PJ (Admin) dibuat oleh seorang Owner. Kita cari Owner tersebut.
        # Untuk struktur saat ini, kita asumsikan semua di bawah "Owner Utama" yang punya super_owner_id.
        managing_owner = Admin.query.filter(Admin.super_owner_id.isnot(None)).first()
        
        if managing_owner and managing_owner.super_owner_id:
            super_owner_id = managing_owner.super_owner_id
            so_balance = SuperOwnerBalance.query.filter_by(super_owner_id=super_owner_id, owner_id=managing_owner.id).first()
            if so_balance:
                so_balance.balance += keuntungan_superowner
            else:
                db.session.add(SuperOwnerBalance(super_owner_id=super_owner_id, owner_id=managing_owner.id, balance=keuntungan_superowner))
        # === AKHIR PERBAIKAN ===

        db.session.commit()
        logging.info(f"-> LAPORAN #{report.id} DIKONFIRMASI. Profit SuperOwner +{keuntungan_superowner}")
        return jsonify({"success": True, "message": "Laporan berhasil dikonfirmasi."})
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error confirming report: {str(e)}")
        return jsonify({"success": False, "message": f"Terjadi kesalahan server: {str(e)}"}), 500
        
@app.route('/api/get_pembayaran_data', methods=['GET'])
def get_pembayaran_data():
    try:
        # Mengambil data tagihan SEMUA supplier
        suppliers = Supplier.query.options(joinedload(Supplier.balance)).all()
        supplier_list = [{"supplier_id": s.id, "nama_supplier": s.nama_supplier, "total_tagihan": s.balance.balance if s.balance else 0.0, "metode_pembayaran": s.metode_pembayaran, "nomor_rekening": s.nomor_rekening} for s in suppliers]
        
        return jsonify({
            "success": True, 
            "supplier_balances": supplier_list
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

# --- REVISI: Hapus pemilihan metode, ambil dari data supplier ---
@app.route('/api/submit_pembayaran', methods=['POST'])
def submit_pembayaran():
    data = request.json
    supplier_id = data.get('supplier_id')
    jumlah_dibayar = float(data.get('jumlah_pembayaran', 0))
    supplier = Supplier.query.get(supplier_id)
    if not supplier or not supplier.metode_pembayaran:
        return jsonify({"success": False, "message": "Metode pembayaran untuk supplier ini belum diatur."}), 400
    balance = supplier.balance
    if not balance or balance.balance < (jumlah_dibayar - 0.01):
        return jsonify({"success": False, "message": f"Jumlah pembayaran melebihi total tagihan."}), 400
    try:
        new_payment = PembayaranSupplier(
            supplier_id=supplier_id, 
            jumlah_pembayaran=jumlah_dibayar, 
            metode_pembayaran=supplier.metode_pembayaran
        )
        db.session.add(new_payment)
        balance.balance -= jumlah_dibayar
        db.session.commit()
        return jsonify({"success": True, "message": f"Pembayaran berhasil dicatat."})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": f"Terjadi kesalahan: {str(e)}"}), 500

@app.route('/api/get_all_payment_history', methods=['GET'])
def get_all_payment_history():
    try:
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        metode = request.args.get('metode')

        query = PembayaranSupplier.query.options(joinedload(PembayaranSupplier.supplier))

        if start_date_str:
            start_date = datetime.datetime.strptime(start_date_str, '%Y-%m-%d').date()
            query = query.filter(PembayaranSupplier.tanggal_pembayaran >= start_date)
        if end_date_str:
            end_date = datetime.datetime.strptime(end_date_str, '%Y-%m-%d').date()
            query = query.filter(PembayaranSupplier.tanggal_pembayaran <= end_date)
        if metode and metode != 'semua':
            query = query.filter(PembayaranSupplier.metode_pembayaran == metode)
        
        payments = query.order_by(PembayaranSupplier.tanggal_pembayaran.desc()).all()

        payment_list = [{
            "tanggal": p.tanggal_pembayaran.strftime('%Y-%m-%d'),
            "nama_supplier": p.supplier.nama_supplier,
            "jumlah": p.jumlah_pembayaran,
            "metode": p.metode_pembayaran
        } for p in payments]
        
        return jsonify({"success": True, "history": payment_list})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    
@app.route('/api/get_chart_data', methods=['GET'])
def get_chart_data():
    try:
        year = int(request.args.get('year', datetime.date.today().year))
        month = int(request.args.get('month', datetime.date.today().month))

        # Tentukan jumlah hari dalam bulan yang dipilih
        _, num_days = monthrange(year, month)
        # Buat label untuk semua hari dalam bulan (misal: "1", "2", ..., "31")
        labels = [str(i) for i in range(1, num_days + 1)]
        
        # Inisialisasi data dengan 0 untuk setiap hari
        pendapatan_data = {day: 0 for day in labels}
        biaya_data = {day: 0 for day in labels}

        # 1. Ambil data pendapatan harian (dari laporan terkonfirmasi)
        pendapatan_results = db.session.query(
            func.extract('day', LaporanHarian.tanggal),
            func.sum(LaporanHarian.total_pendapatan)
        ).filter(
            func.extract('year', LaporanHarian.tanggal) == year,
            func.extract('month', LaporanHarian.tanggal) == month,
            LaporanHarian.status == 'Terkonfirmasi'
        ).group_by(func.extract('day', LaporanHarian.tanggal)).all()

        for day, total in pendapatan_results:
            pendapatan_data[str(int(day))] = total

        # 2. Ambil data biaya harian (dari pembayaran supplier)
        biaya_results = db.session.query(
            func.extract('day', PembayaranSupplier.tanggal_pembayaran),
            func.sum(PembayaranSupplier.jumlah_pembayaran)
        ).filter(
            func.extract('year', PembayaranSupplier.tanggal_pembayaran) == year,
            func.extract('month', PembayaranSupplier.tanggal_pembayaran) == month
        ).group_by(func.extract('day', PembayaranSupplier.tanggal_pembayaran)).all()
        
        for day, total in biaya_results:
            biaya_data[str(int(day))] = total
        
        return jsonify({
            "success": True,
            "labels": labels,
            "pendapatanData": list(pendapatan_data.values()),
            "biayaData": list(biaya_data.values())
        })

    except Exception as e:
        logging.error(f"Error getting chart data: {str(e)}")
        return jsonify({"success": False, "message": str(e)}), 500
# --- LAPAK API ---
# GANTI FUNGSI LAMA DENGAN VERSI BARU INI
@app.route('/api/get_data_buat_catatan/<int:lapak_id>', methods=['GET'])
def get_data_buat_catatan(lapak_id):
    today = datetime.date.today()
    # Pengecekan laporan yang sudah ada tetap berlaku
    if LaporanHarian.query.filter_by(lapak_id=lapak_id, tanggal=today).first():
        return jsonify({"success": False, "message": "Laporan untuk hari ini sudah dibuat.", "already_exists": True}), 409
    
    # Ambil SEMUA supplier beserta produk mereka
    all_suppliers = Supplier.query.options(joinedload(Supplier.products)).order_by(Supplier.nama_supplier).all()
    
    suppliers_data = []
    for s in all_suppliers:
        suppliers_data.append({
            "id": s.id,
            "name": s.nama_supplier,
            # === PERBAIKAN UTAMA ADA DI SINI ===
            "metode_pembayaran": s.metode_pembayaran, # Tambahkan baris ini
            # =====================================
            "products": [{
                "id": p.id,
                "name": p.nama_produk,
                "harga_jual": p.harga_jual,
                "harga_beli": p.harga_beli
            } for p in s.products]
        })
        
    return jsonify({"success": True, "data": suppliers_data})

@app.route('/api/submit_catatan_harian', methods=['POST'])
def submit_catatan_harian():
    data = request.json
    lapak_id = data.get('lapak_id')
    today = datetime.date.today()
    if LaporanHarian.query.filter_by(lapak_id=lapak_id, tanggal=today).first():
        return jsonify({"success": False, "message": "Laporan untuk hari ini sudah pernah dibuat."}), 400
    try:
        total_pendapatan_auto, total_biaya_auto, total_terjual_auto = 0.0, 0.0, 0
        
        new_report = LaporanHarian(lapak_id=lapak_id, tanggal=today, total_pendapatan=0, total_biaya_supplier=0,
            pendapatan_cash=float(data['rekap_pembayaran'].get('cash') or 0),
            pendapatan_qris=float(data['rekap_pembayaran'].get('qris') or 0),
            pendapatan_bca=float(data['rekap_pembayaran'].get('bca') or 0), total_produk_terjual=0,
            manual_pendapatan_cash=float(data['rekap_pembayaran'].get('cash') or 0),
            manual_pendapatan_qris=float(data['rekap_pembayaran'].get('qris') or 0),
            manual_pendapatan_bca=float(data['rekap_pembayaran'].get('bca') or 0),
            manual_total_pendapatan=float(data['rekap_pembayaran'].get('total') or 0)
        )
        db.session.add(new_report)
        db.session.flush()
        for prod_data in data.get('products', []):
            product_id = prod_data.get('id')
            stok_awal = int(prod_data.get('stok_awal') or 0)
            stok_akhir = int(prod_data.get('stok_akhir') or 0)
            if stok_awal == 0 and stok_akhir == 0: continue
            
            if not product_id:
                if prod_data.get('nama_produk'):
                    lapak = Lapak.query.get(lapak_id)
                    new_product = Product(nama_produk=prod_data['nama_produk'],
                        supplier_id=prod_data.get('supplier_id') if str(prod_data.get('supplier_id')).lower() != 'manual' else None,
                        harga_beli=HARGA_BELI_DEFAULT, harga_jual=HARGA_JUAL_DEFAULT, is_manual=True)
                    new_product.lapaks.append(lapak)
                    db.session.add(new_product)
                    db.session.flush()
                    product_id = new_product.id
                else: continue 

            product = Product.query.get(product_id)
            if not product: continue
            
            jumlah_terjual = max(0, stok_awal - stok_akhir)
            total_harga_jual = jumlah_terjual * product.harga_jual
            total_harga_beli = jumlah_terjual * product.harga_beli

            rincian = LaporanHarianProduk(laporan_id=new_report.id, product_id=product.id, stok_awal=stok_awal, stok_akhir=stok_akhir, jumlah_terjual=jumlah_terjual, total_harga_jual=total_harga_jual, total_harga_beli=total_harga_beli)
            db.session.add(rincian)
            db.session.add(StokHarian(lapak_id=lapak_id, product_id=product.id, jumlah_sisa=stok_akhir, tanggal=today))
            total_pendapatan_auto += total_harga_jual
            total_biaya_auto += total_harga_beli
            total_terjual_auto += jumlah_terjual
        
        new_report.total_pendapatan = total_pendapatan_auto
        new_report.total_biaya_supplier = total_biaya_auto
        new_report.total_produk_terjual = total_terjual_auto

        db.session.commit()
        return jsonify({"success": True, "message": "Laporan harian berhasil dikirim!"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": f"Gagal menyimpan laporan: {str(e)}"}), 500

@app.route('/api/get_history_laporan/<int:lapak_id>', methods=['GET'])
def get_history_laporan(lapak_id):
    try:
        reports = LaporanHarian.query.filter_by(lapak_id=lapak_id).order_by(LaporanHarian.tanggal.desc()).all()
        report_list = [{"id": r.id, "tanggal": r.tanggal.isoformat(), "total_pendapatan": r.total_pendapatan, "total_produk_terjual": r.total_produk_terjual, "status": r.status} for r in reports]
        return jsonify({"success": True, "reports": report_list})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/add_manual_product_to_supplier', methods=['POST'])
def add_manual_product():
    data = request.json
    product_name = data.get('nama_produk')
    supplier_id = data.get('supplier_id')
    lapak_id = data.get('lapak_id') # Kita ambil lapak_id juga

    if not all([product_name, supplier_id, lapak_id]):
        return jsonify({"success": False, "message": "Data tidak lengkap."}), 400

    try:
        # Cek apakah produk dengan nama yang sama sudah ada untuk supplier ini
        existing_product = Product.query.filter_by(nama_produk=product_name, supplier_id=supplier_id).first()
        if existing_product:
            return jsonify({"success": False, "message": "Produk dengan nama ini sudah ada untuk supplier tersebut."}), 409

        # Buat produk baru
        new_product = Product(
            nama_produk=product_name,
            supplier_id=supplier_id,
            harga_beli=HARGA_BELI_DEFAULT,
            harga_jual=HARGA_JUAL_DEFAULT,
            is_manual=True # Tandai sebagai produk manual
        )
        
        # Alokasikan produk ini ke lapak yang menambahkannya
        lapak = Lapak.query.get(lapak_id)
        if lapak:
            new_product.lapaks.append(lapak)

        db.session.add(new_product)
        db.session.commit()

        # Kirim kembali data produk yang baru dibuat agar bisa di-update di frontend
        product_data = {
            "id": new_product.id,
            "name": new_product.nama_produk,
            "harga_jual": new_product.harga_jual,
            "harga_beli": new_product.harga_beli,
            "supplier_id": new_product.supplier_id
        }

        return jsonify({"success": True, "message": "Produk berhasil ditambahkan!", "product": product_data}), 201

    except Exception as e:
        db.session.rollback()
        logging.error(f"Error adding manual product: {str(e)}")
        return jsonify({"success": False, "message": "Terjadi kesalahan server."}), 500

# (Letakkan ini di dalam file app.py, di bagian LAPAK API)

# GANTI FUNGSI LAMA DENGAN VERSI BARU INI
@app.route('/api/notify_supplier', methods=['POST'])
def notify_supplier():
    data = request.json
    product_id = data.get('product_id')
    lapak_id = data.get('lapak_id')

    product = Product.query.get(product_id)
    lapak = Lapak.query.get(lapak_id)

    # Validasi input
    if not all([product, lapak]):
        return jsonify({"success": False, "message": "Data produk atau lapak tidak valid."}), 404
    
    # Pastikan produk memiliki supplier
    if not product.supplier_id:
        return jsonify({"success": False, "message": "Produk ini tidak terhubung ke supplier manapun."}), 400

    try:
        # Buat entri notifikasi baru di database
        notifikasi_baru = Notifikasi(
            product_id=product.id,
            lapak_id=lapak.id,
            supplier_id=product.supplier_id
        )
        db.session.add(notifikasi_baru)
        db.session.commit()

        # Cetak ke terminal (untuk debugging)
        logging.info(f"-> NOTIFIKASI TERSIMPAN: Stok produk '{product.nama_produk}' habis di '{lapak.lokasi}'.")

        return jsonify({"success": True, "message": "Notifikasi berhasil dikirim."})

    except Exception as e:
        db.session.rollback()
        logging.error(f"Error saving notification: {str(e)}")
        return jsonify({"success": False, "message": "Terjadi kesalahan server saat menyimpan notifikasi."}), 500

# --- SUPPLIER API ---
@app.route('/api/get_data_supplier/<int:supplier_id>', methods=['GET'])
def get_data_supplier(supplier_id):
    try:
        today = datetime.date.today()
        start_of_month = today.replace(day=1)
        balance_info = SupplierBalance.query.filter_by(supplier_id=supplier_id).first()
        total_tagihan = balance_info.balance if balance_info else 0.0
        penjualan_bulan_ini = db.session.query(
            func.sum(LaporanHarianProduk.total_harga_beli)
        ).join(LaporanHarian, LaporanHarian.id == LaporanHarianProduk.laporan_id)\
         .join(Product, Product.id == LaporanHarianProduk.product_id)\
         .filter(Product.supplier_id == supplier_id, LaporanHarian.tanggal >= start_of_month, LaporanHarian.status == 'Terkonfirmasi').scalar() or 0
        return jsonify({"success": True, "summary": {"total_tagihan": total_tagihan, "penjualan_bulan_ini": penjualan_bulan_ini}})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/get_supplier_history/<int:supplier_id>', methods=['GET'])
def get_supplier_history(supplier_id):
    try:
        # Ambil semua parameter dari request
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        lapak_id = request.args.get('lapak_id') # Parameter baru

        # Query pembayaran tidak berubah
        payments_query = PembayaranSupplier.query.filter_by(supplier_id=supplier_id)
        if start_date_str:
            start_date = datetime.datetime.strptime(start_date_str, '%Y-%m-%d').date()
            payments_query = payments_query.filter(PembayaranSupplier.tanggal_pembayaran >= start_date)
        if end_date_str:
            end_date = datetime.datetime.strptime(end_date_str, '%Y-%m-%d').date()
            payments_query = payments_query.filter(PembayaranSupplier.tanggal_pembayaran <= end_date)
        
        payments = payments_query.order_by(PembayaranSupplier.tanggal_pembayaran.desc()).all()
        payment_list = [{"tanggal": p.tanggal_pembayaran.strftime('%Y-%m-%d'), "jumlah": p.jumlah_pembayaran, "metode": p.metode_pembayaran} for p in payments]

        # Query dasar untuk penjualan
        sales_query = db.session.query(
            LaporanHarian.tanggal, Lapak.lokasi, Product.nama_produk,
            LaporanHarianProduk.jumlah_terjual
        ).select_from(LaporanHarianProduk)\
         .join(Product, Product.id == LaporanHarianProduk.product_id)\
         .join(LaporanHarian, LaporanHarian.id == LaporanHarianProduk.laporan_id)\
         .join(Lapak, Lapak.id == LaporanHarian.lapak_id)\
         .filter(Product.supplier_id == supplier_id, LaporanHarian.status == 'Terkonfirmasi')

        # Terapkan filter tanggal pada penjualan
        if start_date_str:
            start_date = datetime.datetime.strptime(start_date_str, '%Y-%m-%d').date()
            sales_query = sales_query.filter(LaporanHarian.tanggal >= start_date)
        if end_date_str:
            end_date = datetime.datetime.strptime(end_date_str, '%Y-%m-%d').date()
            sales_query = sales_query.filter(LaporanHarian.tanggal <= end_date)
        
        # --- PERUBAHAN LOGIKA DI SINI ---
        # Terapkan filter lapak jika ada
        if lapak_id:
            sales_query = sales_query.filter(LaporanHarian.lapak_id == lapak_id)

        sales = sales_query.order_by(LaporanHarian.tanggal.desc(), Lapak.lokasi).all()
        sales_list = [{"tanggal": s.tanggal.strftime('%Y-%m-%d'), "lokasi": s.lokasi, "nama_produk": s.nama_produk, "terjual": s.jumlah_terjual} for s in sales]
        
        # Ambil daftar lapak untuk mengisi dropdown di frontend
        all_lapaks = Lapak.query.order_by(Lapak.lokasi).all()
        lapak_list = [{"id": l.id, "lokasi": l.lokasi} for l in all_lapaks]
        
        return jsonify({"success": True, "payments": payment_list, "sales": sales_list, "lapaks": lapak_list})
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error getting supplier history: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

# (Letakkan ini di dalam file app.py, di bagian SUPPLIER API)

@app.route('/api/get_supplier_notifications/<int:supplier_id>', methods=['GET'])
def get_supplier_notifications(supplier_id):
    try:
        # Ambil notifikasi yang belum diarsipkan, urutkan dari yang terbaru
        notifications = Notifikasi.query.filter(
            Notifikasi.supplier_id == supplier_id,
            Notifikasi.status != 'diarsipkan'
        ).order_by(Notifikasi.waktu_dikirim.desc()).all()

        notif_list = [{
            "id": n.id,
            "product_name": n.product.nama_produk,
            "lapak_name": n.lapak.lokasi,
            "time": n.waktu_dikirim.isoformat(),
            "status": n.status
        } for n in notifications]
        
        return jsonify({"success": True, "notifications": notif_list})
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error getting supplier notifications: {str(e)}")
        return jsonify({"success": False, "message": "Gagal mengambil notifikasi."}), 500
      
# (Letakkan ini setelah fungsi get_supplier_notifications)

# Ganti fungsi lama dengan versi baru ini
@app.route('/api/update_notification_status/<int:notification_id>', methods=['POST'])
def update_notification_status(notification_id):
    data = request.json
    new_status = data.get('status')

    # PERUBAHAN DI SINI: Izinkan 'baru' sebagai status baru
    if new_status not in ['dibaca', 'diarsipkan', 'baru']:
        return jsonify({"success": False, "message": "Status tidak valid."}), 400

    try:
        # (Sisa dari fungsi ini tetap sama, tidak perlu diubah)
        notification = Notifikasi.query.get(notification_id)
        if not notification:
            return jsonify({"success": False, "message": "Notifikasi tidak ditemukan."}), 404

        notification.status = new_status
        db.session.commit()
        
        logging.info(f"-> STATUS NOTIFIKASI #{notification_id} diubah menjadi '{new_status}'.")
        return jsonify({"success": True, "message": f"Notifikasi ditandai sebagai {new_status}."})

    except Exception as e:
        db.session.rollback()
        logging.error(f"Error updating notification status: {str(e)}")
        return jsonify({"success": False, "message": "Gagal memperbarui status notifikasi."}), 500

@app.route('/api/get_archived_notifications/<int:supplier_id>', methods=['GET'])
def get_archived_notifications(supplier_id):
    try:
        # Ambil hanya notifikasi yang statusnya 'diarsipkan'
        notifications = Notifikasi.query.filter_by(
            supplier_id=supplier_id,
            status='diarsipkan'
        ).order_by(Notifikasi.waktu_dikirim.desc()).all()

        notif_list = [{
            "id": n.id,
            "product_name": n.product.nama_produk,
            "lapak_name": n.lapak.lokasi,
            "time": n.waktu_dikirim.isoformat(),
        } for n in notifications]
        
        return jsonify({"success": True, "notifications": notif_list})
    except Exception as e:
        return jsonify({"success": False, "message": "Gagal mengambil arsip notifikasi."}), 500
      
# (Letakkan ini setelah 'get_archived_notifications' dan sebelum 'get_report_details')

# --- SUPEROWNER API ---
# GANTI FUNGSI LAMA DENGAN VERSI BARU INI
@app.route('/api/get_superowner_dashboard_data/<int:superowner_id>', methods=['GET'])
def get_superowner_dashboard_data(superowner_id):
    try:
        balances = SuperOwnerBalance.query.filter_by(super_owner_id=superowner_id).options(joinedload(SuperOwnerBalance.owner)).all()
        total_saldo_profit = sum(b.balance for b in balances)
        rincian_per_owner = [{"owner_id": b.owner.id, "owner_name": b.owner.nama_lengkap, "balance": b.balance} for b in balances]

        today = datetime.date.today()
        start_of_month = today.replace(day=1)
        
        # === LOGIKA BARU UNTUK MENGHITUNG PROFIT BULAN INI ===
        # Tidak lagi memfilter berdasarkan PJ, tapi langsung dari total keuntungan superowner di laporan
        profit_bulan_ini = db.session.query(func.sum(LaporanHarian.keuntungan_superowner))\
            .filter(
                LaporanHarian.tanggal >= start_of_month,
                LaporanHarian.status == 'Terkonfirmasi'
            ).scalar() or 0
        # === AKHIR PERBAIKAN ===

        owner_terprofit = "N/A"
        if balances:
            top_owner_balance = max(balances, key=lambda b: b.balance, default=None)
            if top_owner_balance:
                owner_terprofit = top_owner_balance.owner.nama_lengkap

        return jsonify({
            "success": True, "total_saldo": total_saldo_profit, "rincian_per_owner": rincian_per_owner,
            "kpi": { "profit_bulan_ini": profit_bulan_ini, "owner_terprofit": owner_terprofit }
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": "Gagal mengambil data dashboard."}), 500

@app.route('/api/get_superowner_profit_details/<int:owner_id>', methods=['GET'])
def get_superowner_profit_details(owner_id):
    try:
        # Kita asumsikan 'owner_id' adalah ID dari admin yang berperan sebagai Owner.
        # Query ini mencari semua laporan terkonfirmasi yang menghasilkan profit
        # dan terkait dengan lapak yang dikelola oleh admin/owner tersebut.
        # Ini adalah asumsi sederhana, jika satu owner bisa punya banyak lapak,
        # kita perlu join melalui relasi tersebut.
        
        profit_history = db.session.query(
            LaporanHarian.tanggal,
            Lapak.lokasi,
            LaporanHarian.keuntungan_superowner
        ).join(Lapak, LaporanHarian.lapak_id == Lapak.id)\
         .filter(
            LaporanHarian.status == 'Terkonfirmasi',
            LaporanHarian.keuntungan_superowner > 0,
            Lapak.user_id == owner_id # Filter berdasarkan Penanggung Jawab Lapak, asumsi PJ = Owner
            # Jika struktur lebih kompleks, filter ini perlu disesuaikan
        ).order_by(LaporanHarian.tanggal.desc()).all()

        history_list = [{
            "tanggal": item.tanggal.strftime('%d %B %Y'),
            "sumber": f"Laporan dari {item.lokasi}",
            "profit": item.keuntungan_superowner
        } for item in profit_history]

        return jsonify({"success": True, "history": history_list})

    except Exception as e:
        db.session.rollback()
        logging.error(f"Error getting superowner profit details: {str(e)}")
        return jsonify({"success": False, "message": "Gagal mengambil detail profit."}), 500
      
# (Letakkan ini setelah fungsi 'get_superowner_profit_details')

@app.route('/api/superowner_withdraw', methods=['POST'])
def superowner_withdraw():
    data = request.json
    superowner_id = data.get('superowner_id')
    
    try:
        balances = SuperOwnerBalance.query.filter_by(super_owner_id=superowner_id).all()
        total_penarikan = sum(b.balance for b in balances)

        if total_penarikan <= 0:
            return jsonify({"success": False, "message": "Tidak ada saldo untuk ditarik."}), 400

        # Catat transaksi penarikan
        penarikan = RiwayatPenarikanSuperOwner(
            super_owner_id=superowner_id,
            jumlah_penarikan=total_penarikan
        )
        db.session.add(penarikan)

        # Reset saldo semua owner terkait menjadi 0
        for b in balances:
            b.balance = 0.0
        
        db.session.commit()
        logging.info(f"-> PENARIKAN BERHASIL: SuperOwner #{superowner_id} menarik saldo sebesar {total_penarikan}.")
        return jsonify({"success": True, "message": f"Penarikan saldo sebesar {total_penarikan:,.0f} berhasil dicatat."})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": "Gagal memproses penarikan."}), 500

# GANTI FUNGSI LAMA DENGAN VERSI BARU INI
@app.route('/api/get_superowner_profit_reports/<int:superowner_id>', methods=['GET'])
def get_superowner_profit_reports(superowner_id):
    try:
        # === LOGIKA BARU UNTUK MENGAMBIL LAPORAN ===
        # Query ini sekarang langsung mencari semua laporan yang menghasilkan profit untuk Superowner
        reports = db.session.query(
            LaporanHarian.id, LaporanHarian.tanggal, Lapak.lokasi,
            Admin.nama_lengkap.label('owner_name'), LaporanHarian.keuntungan_superowner
        ).join(Lapak, LaporanHarian.lapak_id == Lapak.id)\
         .join(Admin, Lapak.user_id == Admin.id)\
         .filter(
            LaporanHarian.status == 'Terkonfirmasi',
            LaporanHarian.keuntungan_superowner > 0
        ).order_by(LaporanHarian.tanggal.desc()).all()
        # === AKHIR PERBAIKAN ===

        report_list = [{
            "report_id": r.id, "tanggal": r.tanggal.strftime('%d %B %Y'),
            "sumber": f"Laporan dari {r.lokasi}", "owner": r.owner_name, "profit": r.keuntungan_superowner
        } for r in reports]

        return jsonify({"success": True, "reports": report_list})
    except Exception as e:
        return jsonify({"success": False, "message": "Gagal mengambil laporan profit."}), 500

# (Letakkan ini setelah fungsi get_superowner_profit_reports)

@app.route('/api/get_superowner_payout_history/<int:superowner_id>', methods=['GET'])
def get_superowner_payout_history(superowner_id):
    try:
        history = RiwayatPenarikanSuperOwner.query.filter_by(
            super_owner_id=superowner_id
        ).order_by(RiwayatPenarikanSuperOwner.tanggal_penarikan.desc()).all()

        history_list = [{
            "tanggal": h.tanggal_penarikan.strftime('%d %B %Y, %H:%M'),
            "jumlah": h.jumlah_penarikan
        } for h in history]

        return jsonify({"success": True, "history": history_list})
    except Exception as e:
        return jsonify({"success": False, "message": "Gagal mengambil riwayat penarikan."}), 500

# (Letakkan ini di dalam file app.py, di bagian SUPEROWNER API)

@app.route('/api/get_superowner_owners/<int:superowner_id>', methods=['GET'])
def get_superowner_owners(superowner_id):
    try:
        # Ambil semua admin yang terhubung ke superowner ini
        owners = Admin.query.filter_by(super_owner_id=superowner_id).all()
        owner_list = [{
            "id": o.id,
            "nama_lengkap": o.nama_lengkap,
            "username": o.username,
            "email": o.email,
            "nomor_kontak": o.nomor_kontak,
            "password": o.password
        } for o in owners]
        return jsonify({"success": True, "owners": owner_list})
    except Exception as e:
        return jsonify({"success": False, "message": "Gagal mengambil data owner."}), 500

@app.route('/api/get_report_details/<int:report_id>')
def get_report_details(report_id):
    try:
        report = LaporanHarian.query.options(
            joinedload(LaporanHarian.lapak).joinedload(Lapak.penanggung_jawab),
            joinedload(LaporanHarian.rincian_produk).joinedload(LaporanHarianProduk.product).joinedload(Product.supplier)
        ).get(report_id)

        if not report:
            return jsonify({"success": False, "message": "Laporan tidak ditemukan"}), 404

        # --- PERUBAHAN LOGIKA DIMULAI DI SINI ---
        # Mengelompokkan produk berdasarkan supplier
        rincian_per_supplier = {}
        for item in report.rincian_produk:
            supplier_name = item.product.supplier.nama_supplier if item.product.supplier else "Produk Manual"
            
            if supplier_name not in rincian_per_supplier:
                rincian_per_supplier[supplier_name] = []
            
            rincian_per_supplier[supplier_name].append({
                "nama_produk": item.product.nama_produk,
                "stok_awal": item.stok_awal,
                "stok_akhir": item.stok_akhir,
                "terjual": item.jumlah_terjual,
                "harga_jual": item.product.harga_jual,
                "total_pendapatan": item.total_harga_jual,
            })
        # --- AKHIR PERUBAHAN LOGIKA ---

        data = {
            "id": report.id,
            "tanggal": report.tanggal.strftime('%d %B %Y'),
            "status": report.status,
            "lokasi": report.lapak.lokasi,
            "penanggung_jawab": report.lapak.penanggung_jawab.nama_lengkap,
            "rincian_per_supplier": rincian_per_supplier, # <--- Menggunakan data yang sudah dikelompokkan
            "rekap_otomatis": {
                "terjual_cash": report.pendapatan_cash,
                "terjual_qris": report.pendapatan_qris,
                "terjual_bca": report.pendapatan_bca,
                "total_produk_terjual": report.total_produk_terjual,
                "total_pendapatan": report.total_pendapatan,
                "total_biaya_supplier": report.total_biaya_supplier
            },
            "rekap_manual": {
                "terjual_cash": report.manual_pendapatan_cash,
                "terjual_qris": report.manual_pendapatan_qris,
                "terjual_bca": report.manual_pendapatan_bca,
                # Menggunakan total dari rekap otomatis untuk konsistensi
                "total_produk_terjual": report.total_produk_terjual,
                "total_pendapatan": report.manual_total_pendapatan
            }
        }
        return jsonify({"success": True, "data": data})

    except Exception as e:
        logging.error(f"Error getting report details: {e}")
        return jsonify({"success": False, "message": "Terjadi kesalahan pada server"}), 500


if __name__ == '__main__':
    app.run(debug=True, port=5001)