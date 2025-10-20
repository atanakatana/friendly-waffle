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

class Supplier(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nama_supplier = db.Column(db.String(100), nullable=False)
    username = db.Column(db.String(80), unique=True, nullable=False)
    kontak = db.Column(db.String(20), nullable=True)
    nomor_register = db.Column(db.String(50), unique=True, nullable=True)
    alamat = db.Column(db.Text, nullable=True)
    password = db.Column(db.String(120), nullable=False)
    # --- Kolom baru untuk info pembayaran ---
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
    # --- PERUBAHAN DI SINI: Kolom baru untuk menandai produk buatan admin ---
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
    # --- PERUBAHAN DI SINI: Menambahkan kolom untuk menyimpan data inputan manual dari admin lapak ---
    manual_pendapatan_cash = db.Column(db.Float, nullable=True)
    manual_pendapatan_qris = db.Column(db.Float, nullable=True)
    manual_pendapatan_bca = db.Column(db.Float, nullable=True)
    manual_total_pendapatan = db.Column(db.Float, nullable=True)
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

class PembayaranSupplier(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey('supplier.id'), nullable=False)
    tanggal_pembayaran = db.Column(db.Date, nullable=False, default=datetime.date.today)
    jumlah_pembayaran = db.Column(db.Float, nullable=False)
    metode_pembayaran = db.Column(db.String(20), nullable=False)
    supplier = db.relationship('Supplier')

# ===================================================================
# CLI & Rute Halaman
# ===================================================================
@app.cli.command("init-db")
def init_db_command():
    db.create_all()
    print("Database telah diinisialisasi.")

# --- PERUBAHAN DI SINI: Seeder diupdate untuk mencerminkan alur data baru ---
@app.cli.command("seed-db")
def seed_db_command():
    """Menghapus database dan membuat data demo komprehensif untuk 90 hari."""
    db.drop_all()
    db.create_all()
    print("Database dibersihkan...")

    # 1. Buat Pengguna Inti (Owner & Admin)
    owner = Admin(nama_lengkap="Owner Utama", nik="0000000000000000", username="owner", email="owner@app.com", nomor_kontak="0", password="owner")
    admin_andi = Admin(nama_lengkap="Andi (PJ Kopo)", nik="1111111111111111", username="andi", email="andi@app.com", nomor_kontak="0811", password="andi")
    admin_budi = Admin(nama_lengkap="Budi (PJ Buah Batu)", nik="2222222222222222", username="budi", email="budi@app.com", nomor_kontak="0812", password="budi")
    db.session.add_all([owner, admin_andi, admin_budi])
    db.session.commit()
    print("=> Pengguna (Owner, Admin) berhasil dibuat.")

    # 2. Buat Lapak
    lapak_kopo = Lapak(lokasi="Lapak Kopo", penanggung_jawab=admin_andi)
    lapak_buah_batu = Lapak(lokasi="Lapak Buah Batu", penanggung_jawab=admin_budi)
    db.session.add_all([lapak_kopo, lapak_buah_batu])
    db.session.commit()
    print("=> Lapak (Kopo, Buah Batu) berhasil dibuat.")

    # 3. Buat Supplier & Produk (Master Data oleh Owner)
    supplier_roti = Supplier(nama_supplier="Roti Lezat Bakery", username="roti", kontak="0851", nomor_register="REG001", password="roti", metode_pembayaran="BCA", nomor_rekening="112233")
    supplier_roti.balance = SupplierBalance(balance=0.0)
    supplier_minuman = Supplier(nama_supplier="Minuman Segar Haus", username="minuman", kontak="0852", nomor_register="REG002", password="minuman", metode_pembayaran="DANA", nomor_rekening="08521234")
    supplier_minuman.balance = SupplierBalance(balance=0.0)
    supplier_snack = Supplier(nama_supplier="Cemilan Gurih Nusantara", username="snack", kontak="0853", nomor_register="REG003", password="snack", metode_pembayaran="BCA", nomor_rekening="445566")
    supplier_snack.balance = SupplierBalance(balance=0.0)
    db.session.add_all([supplier_roti, supplier_minuman, supplier_snack])
    db.session.commit()

    db.session.add_all([
        Product(nama_produk="Roti Tawar Gandum", supplier_id=supplier_roti.id, harga_beli=12000, harga_jual=15000),
        Product(nama_produk="Roti Sobek Coklat", supplier_id=supplier_roti.id, harga_beli=10000, harga_jual=13000),
        Product(nama_produk="Es Teh Manis", supplier_id=supplier_minuman.id, harga_beli=3000, harga_jual=5000),
        Product(nama_produk="Kopi Susu Gula Aren", supplier_id=supplier_minuman.id, harga_beli=15000, harga_jual=18000),
        Product(nama_produk="Keripik Singkong Balado", supplier_id=supplier_snack.id, harga_beli=8000, harga_jual=10000),
    ])
    db.session.commit()
    print("=> 3 Supplier dengan 5 produk master berhasil dibuat.")

    # 4. Buat Data Transaksi Historis (Laporan & Pembayaran)
    print("Membuat data transaksi historis (90 hari)...")
    today = datetime.date.today()
    all_lapaks = [lapak_kopo, lapak_buah_batu]
    all_products = Product.query.all()

    for i in range(90, 0, -1):
        current_date = today - timedelta(days=i)
        for lapak in all_lapaks:
            if random.random() < 0.9: # 90% chance a report is made
                # Laporan yang umurnya < 10 hari, 50% kemungkinan belum dikonfirmasi
                status = 'Menunggu Konfirmasi' if i <= 10 and random.random() < 0.5 else 'Terkonfirmasi'
                
                report = LaporanHarian(lapak_id=lapak.id, tanggal=current_date, status=status,
                                        total_pendapatan=0, total_biaya_supplier=0, total_produk_terjual=0,
                                        pendapatan_cash=0, pendapatan_qris=0, pendapatan_bca=0)
                db.session.add(report)
                db.session.flush()

                total_pendapatan_harian, total_biaya_harian, total_terjual_harian = 0, 0, 0
                
                # Admin lapak memilih beberapa produk acak untuk dijual hari itu
                products_for_the_day = random.sample(all_products, k=random.randint(2, 4))

                for product in products_for_the_day:
                    stok_awal = random.randint(15, 40)
                    terjual = random.randint(5, stok_awal - 2)
                    stok_akhir = stok_awal - terjual
                    
                    total_harga_jual = terjual * product.harga_jual
                    total_harga_beli = terjual * product.harga_beli
                    
                    rincian = LaporanHarianProduk(laporan_id=report.id, product_id=product.id,
                                                  stok_awal=stok_awal, stok_akhir=stok_akhir,
                                                  jumlah_terjual=terjual, total_harga_jual=total_harga_jual,
                                                  total_harga_beli=total_harga_beli)
                    db.session.add(rincian)

                    total_pendapatan_harian += total_harga_jual
                    total_biaya_harian += total_harga_beli
                    total_terjual_harian += terjual

                    # Jika laporan dikonfirmasi, update saldo tagihan supplier
                    if status == 'Terkonfirmasi' and product.supplier:
                        product.supplier.balance.balance += total_harga_beli
                
                report.total_pendapatan = total_pendapatan_harian
                report.total_biaya_supplier = total_biaya_harian
                report.total_produk_terjual = total_terjual_harian
                # Simulasikan rekap manual dan otomatis
                report.pendapatan_qris = total_pendapatan_harian * 0.5
                report.pendapatan_cash = total_pendapatan_harian * 0.3
                report.pendapatan_bca = total_pendapatan_harian * 0.2
                report.manual_total_pendapatan = total_pendapatan_harian + random.randint(-5000, 5000) # sedikit selisih
                report.manual_pendapatan_qris = report.pendapatan_qris
                report.manual_pendapatan_cash = report.pendapatan_cash
                report.manual_pendapatan_bca = report.pendapatan_bca
    
    # Buat beberapa pembayaran acak
    for supplier in [supplier_roti, supplier_minuman, supplier_snack]:
        if supplier.balance.balance > 50000:
            payment_amount = round(supplier.balance.balance * random.uniform(0.3, 0.7) / 1000) * 1000
            payment = PembayaranSupplier(
                supplier=supplier,
                tanggal_pembayaran=today - timedelta(days=random.randint(5, 30)),
                jumlah_pembayaran=payment_amount,
                metode_pembayaran=supplier.metode_pembayaran
            )
            supplier.balance.balance -= payment_amount
            db.session.add(payment)

    db.session.commit()
    print("=> Data historis berhasil dibuat.")
    print("\nDatabase siap untuk demo! Silakan jalankan aplikasi.")

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
            # Cari apakah admin ini PJ atau anggota
            lapak_info = Lapak.query.filter(or_(Lapak.user_id == admin.id, Lapak.anggota.any(id=admin.id))).first()
            if lapak_info:
                return jsonify({"success": True, "role": "lapak", "user_info": {"nama_lengkap": admin.nama_lengkap, "lapak_id": lapak_info.id, "id": admin.id}})
            else:
                 return jsonify({"success": False, "message": "Admin ini belum terdaftar di lapak manapun"}), 403
    
    supplier = Supplier.query.filter(db.func.lower(Supplier.username) == username).first()
    if supplier and supplier.password == password:
        return jsonify({"success": True, "role": "supplier", "user_info": {"nama_supplier": supplier.nama_supplier,"supplier_id": supplier.id}})
    
    return jsonify({"success": False, "message": "Username atau password salah"}), 401

# --- OWNER API ---
@app.route('/api/get_data_owner', methods=['GET'])
def get_owner_data():
    try:
        admins = Admin.query.filter(Admin.username != 'owner').all()
        lapaks = Lapak.query.options(joinedload(Lapak.penanggung_jawab), joinedload(Lapak.anggota)).all()
        suppliers = Supplier.query.all()
        
        admin_list = [{"id": u.id, "nama_lengkap": u.nama_lengkap, "nik": u.nik, "username": u.username, "email": u.email, "nomor_kontak": u.nomor_kontak, "password": u.password} for u in admins]
        lapak_list = [{"id": l.id, "lokasi": l.lokasi, "penanggung_jawab": f"{l.penanggung_jawab.nama_lengkap}", "user_id": l.user_id, "anggota": [{"id": a.id, "nama": a.nama_lengkap} for a in l.anggota], "anggota_ids": [a.id for a in l.anggota]} for l in lapaks]
        supplier_list = [{"id": s.id, "nama_supplier": s.nama_supplier, "username": s.username, "kontak": s.kontak, "nomor_register": s.nomor_register, "alamat": s.alamat, "password": s.password, "metode_pembayaran": s.metode_pembayaran, "nomor_rekening": s.nomor_rekening} for s in suppliers]
        
        today = datetime.date.today()
        start_of_month = today.replace(day=1)
        total_pendapatan_bulan_ini = db.session.query(func.sum(LaporanHarian.total_pendapatan)).filter(LaporanHarian.tanggal >= start_of_month, LaporanHarian.status == 'Terkonfirmasi').scalar() or 0
        total_biaya_bulan_ini = db.session.query(func.sum(PembayaranSupplier.jumlah_pembayaran)).filter(PembayaranSupplier.tanggal_pembayaran >= start_of_month).scalar() or 0
        
        return jsonify({"admin_data": admin_list, "lapak_data": lapak_list, "supplier_data": supplier_list, "summary": {"pendapatan_bulan_ini": total_pendapatan_bulan_ini, "biaya_bulan_ini": total_biaya_bulan_ini}})
    except Exception as e:
        return jsonify({"success": False, "message": f"Terjadi kesalahan server: {str(e)}"}), 500

@app.route('/api/get_next_supplier_reg_number', methods=['GET'])
def get_next_supplier_reg_number():
    last_supplier = Supplier.query.filter(Supplier.nomor_register.like('REG%')).order_by(Supplier.nomor_register.desc()).first()
    if last_supplier:
        last_num = int(last_supplier.nomor_register.replace('REG', ''))
        next_num = last_num + 1
    else:
        next_num = 1
    return jsonify({"reg_number": f"REG{next_num:03d}"})

@app.route('/api/add_admin', methods=['POST'])
def add_admin():
    data = request.json
    if data['password'] != data['password_confirm']: return jsonify({"success": False, "message": "Password dan konfirmasi password tidak cocok."}), 400
    try:
        new_admin = Admin(nama_lengkap=data['nama_lengkap'], nik=data['nik'], username=data['username'], email=data['email'], nomor_kontak=data['nomor_kontak'], password=data['password'])
        db.session.add(new_admin)
        db.session.commit()
        return jsonify({"success": True, "message": "Admin berhasil ditambahkan"})
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

@app.route('/api/add_supplier', methods=['POST'])
def add_supplier():
    data = request.json
    if data['password'] != data['password_confirm']: return jsonify({"success": False, "message": "Password dan konfirmasi password tidak cocok."}), 400
    try:
        new_supplier = Supplier(nama_supplier=data['nama_supplier'], username=data.get('username'), kontak=data.get('kontak'), nomor_register=data.get('nomor_register'), alamat=data.get('alamat'), password=data['password'], metode_pembayaran=data.get('metode_pembayaran'), nomor_rekening=data.get('nomor_rekening'))
        new_supplier.balance = SupplierBalance(balance=0.0)
        db.session.add(new_supplier)
        db.session.commit()
        return jsonify({"success": True, "message": "Supplier berhasil ditambahkan"})
    except IntegrityError:
        db.session.rollback()
        return jsonify({"success": False, "message": "Gagal: Username atau Nomor Register sudah ada."}), 400

@app.route('/api/update_supplier/<int:supplier_id>', methods=['PUT'])
def update_supplier(supplier_id):
    data = request.json
    supplier = Supplier.query.get_or_404(supplier_id)
    if data.get('password') and data['password'] != data['password_confirm']: return jsonify({"success": False, "message": "Password dan konfirmasi password tidak cocok."}), 400
    try:
        supplier.nama_supplier = data['nama_supplier']
        supplier.username = data.get('username')
        supplier.kontak = data.get('kontak')
        supplier.alamat = data.get('alamat')
        supplier.metode_pembayaran = data.get('metode_pembayaran')
        supplier.nomor_rekening = data.get('nomor_rekening')
        if data.get('password'): supplier.password = data['password']
        db.session.commit()
        return jsonify({"success": True, "message": "Data Supplier berhasil diperbarui"})
    except IntegrityError:
        db.session.rollback()
        return jsonify({"success": False, "message": "Gagal: Username sudah digunakan oleh supplier lain."}), 400

@app.route('/api/delete_supplier/<int:supplier_id>', methods=['DELETE'])
def delete_supplier(supplier_id):
    supplier = Supplier.query.get_or_404(supplier_id)
    db.session.delete(supplier)
    db.session.commit()
    return jsonify({"success": True, "message": "Supplier berhasil dihapus"})

# --- OWNER API (Laporan & Pembayaran) ---
@app.route('/api/get_laporan_pendapatan_harian')
def get_laporan_pendapatan_harian():
    try:
        date_str = request.args.get('date')
        target_date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
        reports = LaporanHarian.query.options(joinedload(LaporanHarian.lapak), joinedload(LaporanHarian.rincian_produk).joinedload(LaporanHarianProduk.product).joinedload(Product.supplier)).filter(LaporanHarian.tanggal == target_date, LaporanHarian.status == 'Terkonfirmasi').all()
        total_harian = sum(r.total_pendapatan for r in reports)
        laporan_per_lapak = []
        for report in reports:
            rincian_pendapatan = [{"produk": item.product.nama_produk, "supplier": item.product.supplier.nama_supplier if item.product.supplier else "N/A", "stok_awal": item.stok_awal, "stok_akhir": item.stok_akhir, "jumlah": item.jumlah_terjual} for item in report.rincian_produk if item.jumlah_terjual > 0]
            if rincian_pendapatan:
                 laporan_per_lapak.append({"lokasi": report.lapak.lokasi, "penanggung_jawab": report.lapak.penanggung_jawab.nama_lengkap, "total_pendapatan": report.total_pendapatan, "rincian_pendapatan": rincian_pendapatan})
        return jsonify({"total_harian": total_harian, "laporan_per_lapak": laporan_per_lapak})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/get_laporan_biaya_harian')
def get_laporan_biaya_harian():
    try:
        date_str = request.args.get('date')
        target_date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
        reports = LaporanHarian.query.options(joinedload(LaporanHarian.lapak), joinedload(LaporanHarian.rincian_produk).joinedload(LaporanHarianProduk.product).joinedload(Product.supplier)).filter(LaporanHarian.tanggal == target_date, LaporanHarian.status == 'Terkonfirmasi').all()
        total_harian = sum(r.total_biaya_supplier for r in reports)
        laporan_per_lapak = []
        for report in reports:
            rincian_biaya = [{"produk": item.product.nama_produk, "supplier": item.product.supplier.nama_supplier if item.product.supplier else "N/A", "jumlah": item.jumlah_terjual, "biaya": item.total_harga_beli} for item in report.rincian_produk if item.jumlah_terjual > 0]
            if rincian_biaya:
                laporan_per_lapak.append({"lokasi": report.lapak.lokasi, "penanggung_jawab": report.lapak.penanggung_jawab.nama_lengkap, "total_biaya": report.total_biaya_supplier, "rincian_biaya": rincian_biaya})
        return jsonify({"total_harian": total_harian, "laporan_per_lapak": laporan_per_lapak})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

# --- PERUBAHAN DI SINI: API ini sekarang bisa filter berdasarkan supplier ---
@app.route('/api/get_manage_reports')
def get_manage_reports():
    try:
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        supplier_id = request.args.get('supplier_id')
        query = LaporanHarian.query.options(joinedload(LaporanHarian.lapak).joinedload(Lapak.penanggung_jawab))
        if start_date_str: query = query.filter(LaporanHarian.tanggal >= datetime.datetime.strptime(start_date_str, '%Y-%m-%d').date())
        if end_date_str: query = query.filter(LaporanHarian.tanggal <= datetime.datetime.strptime(end_date_str, '%Y-%m-%d').date())
        if supplier_id:
            query = query.join(LaporanHarian.rincian_produk).join(LaporanHarianProduk.product).filter(Product.supplier_id == supplier_id).distinct()
        reports = query.order_by(LaporanHarian.tanggal.desc(), LaporanHarian.id.desc()).all()
        report_list = [{"id": r.id, "lokasi": r.lapak.lokasi, "penanggung_jawab": r.lapak.penanggung_jawab.nama_lengkap, "tanggal": r.tanggal.isoformat(), "total_pendapatan": r.total_pendapatan, "total_produk_terjual": r.total_produk_terjual, "status": r.status} for r in reports]
        return jsonify({"success": True, "reports": report_list})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

# --- PERUBAHAN DI SINI: Logika konfirmasi sekarang mengupdate saldo supplier ---
@app.route('/api/confirm_report/<int:report_id>', methods=['POST'])
def confirm_report(report_id):
    try:
        report = LaporanHarian.query.options(joinedload(LaporanHarian.rincian_produk).joinedload(LaporanHarianProduk.product)).get(report_id)
        if not report: return jsonify({"success": False, "message": "Laporan tidak ditemukan."}), 404
        if report.status == 'Terkonfirmasi': return jsonify({"success": False, "message": "Laporan ini sudah dikonfirmasi."}), 400
        
        report.status = 'Terkonfirmasi'
        
        supplier_costs = {}
        for rincian in report.rincian_produk:
            if rincian.product.supplier_id:
                sid = rincian.product.supplier_id
                cost = rincian.total_harga_beli
                supplier_costs[sid] = supplier_costs.get(sid, 0) + cost
        
        for supplier_id, cost in supplier_costs.items():
            balance = SupplierBalance.query.filter_by(supplier_id=supplier_id).first()
            if balance:
                balance.balance += cost
            else:
                db.session.add(SupplierBalance(supplier_id=supplier_id, balance=cost))

        db.session.commit()
        return jsonify({"success": True, "message": "Laporan berhasil dikonfirmasi dan tagihan supplier telah diperbarui."})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/get_pembayaran_data', methods=['GET'])
def get_pembayaran_data():
    try:
        suppliers = Supplier.query.options(joinedload(Supplier.balance)).all()
        supplier_list = [{"supplier_id": s.id, "nama_supplier": s.nama_supplier, "total_tagihan": s.balance.balance if s.balance else 0.0, "metode_pembayaran": s.metode_pembayaran, "nomor_rekening": s.nomor_rekening} for s in suppliers]
        return jsonify({"success": True, "supplier_balances": supplier_list})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/submit_pembayaran', methods=['POST'])
def submit_pembayaran():
    data = request.json
    supplier_id = data.get('supplier_id')
    jumlah_dibayar = float(data.get('jumlah_pembayaran', 0))
    supplier = Supplier.query.get(supplier_id)
    if not supplier or not supplier.metode_pembayaran: return jsonify({"success": False, "message": "Metode pembayaran untuk supplier ini belum diatur."}), 400
    balance = supplier.balance
    if not balance or balance.balance < (jumlah_dibayar - 0.01): return jsonify({"success": False, "message": f"Jumlah pembayaran melebihi total tagihan."}), 400
    try:
        new_payment = PembayaranSupplier(supplier_id=supplier_id, jumlah_pembayaran=jumlah_dibayar, metode_pembayaran=supplier.metode_pembayaran)
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
        if start_date_str: query = query.filter(PembayaranSupplier.tanggal_pembayaran >= datetime.datetime.strptime(start_date_str, '%Y-%m-%d').date())
        if end_date_str: query = query.filter(PembayaranSupplier.tanggal_pembayaran <= datetime.datetime.strptime(end_date_str, '%Y-%m-%d').date())
        if metode and metode != 'semua': query = query.filter(PembayaranSupplier.metode_pembayaran == metode)
        payments = query.order_by(PembayaranSupplier.tanggal_pembayaran.desc()).all()
        payment_list = [{"tanggal": p.tanggal_pembayaran.strftime('%Y-%m-%d'), "nama_supplier": p.supplier.nama_supplier, "jumlah": p.jumlah_pembayaran, "metode": p.metode_pembayaran} for p in payments]
        return jsonify({"success": True, "history": payment_list})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/get_owner_supplier_history/<int:supplier_id>', methods=['GET'])
def get_owner_supplier_history(supplier_id):
    try:
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        payments_query = PembayaranSupplier.query.filter_by(supplier_id=supplier_id)
        sales_query = db.session.query(LaporanHarian.tanggal, Lapak.lokasi, Product.nama_produk, LaporanHarianProduk.jumlah_terjual, LaporanHarianProduk.total_harga_beli).select_from(LaporanHarianProduk).join(Product, Product.id == LaporanHarianProduk.product_id).join(LaporanHarian, LaporanHarian.id == LaporanHarianProduk.laporan_id).join(Lapak, Lapak.id == LaporanHarian.lapak_id).filter(Product.supplier_id == supplier_id, LaporanHarian.status == 'Terkonfirmasi')
        if start_date_str:
            start_date = datetime.datetime.strptime(start_date_str, '%Y-%m-%d').date()
            payments_query = payments_query.filter(PembayaranSupplier.tanggal_pembayaran >= start_date)
            sales_query = sales_query.filter(LaporanHarian.tanggal >= start_date)
        if end_date_str:
            end_date = datetime.datetime.strptime(end_date_str, '%Y-%m-%d').date()
            payments_query = payments_query.filter(PembayaranSupplier.tanggal_pembayaran <= end_date)
            sales_query = sales_query.filter(LaporanHarian.tanggal <= end_date)
        payments = payments_query.order_by(PembayaranSupplier.tanggal_pembayaran.desc()).all()
        sales = sales_query.order_by(LaporanHarian.tanggal.desc(), Lapak.lokasi).all()
        payment_list = [{"tanggal": p.tanggal_pembayaran.strftime('%Y-%m-%d'), "jumlah": p.jumlah_pembayaran, "metode": p.metode_pembayaran} for p in payments]
        sales_list = [{"tanggal": s.tanggal.strftime('%Y-%m-%d'), "lokasi": s.lokasi, "nama_produk": s.nama_produk, "terjual": s.jumlah_terjual, "total_harga_beli": s.total_harga_beli} for s in sales]
        return jsonify({"success": True, "payments": payment_list, "sales": sales_list})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/get_chart_data', methods=['GET'])
def get_chart_data():
    try:
        year = int(request.args.get('year', datetime.date.today().year))
        month = int(request.args.get('month', datetime.date.today().month))
        _, num_days = monthrange(year, month)
        labels = [str(i) for i in range(1, num_days + 1)]
        pendapatan_data = {day: 0 for day in labels}
        biaya_data = {day: 0 for day in labels}
        pendapatan_results = db.session.query(func.extract('day', LaporanHarian.tanggal), func.sum(LaporanHarian.total_pendapatan)).filter(func.extract('year', LaporanHarian.tanggal) == year, func.extract('month', LaporanHarian.tanggal) == month, LaporanHarian.status == 'Terkonfirmasi').group_by(func.extract('day', LaporanHarian.tanggal)).all()
        for day, total in pendapatan_results: pendapatan_data[str(int(day))] = total
        biaya_results = db.session.query(func.extract('day', PembayaranSupplier.tanggal_pembayaran), func.sum(PembayaranSupplier.jumlah_pembayaran)).filter(func.extract('year', PembayaranSupplier.tanggal_pembayaran) == year, func.extract('month', PembayaranSupplier.tanggal_pembayaran) == month).group_by(func.extract('day', PembayaranSupplier.tanggal_pembayaran)).all()
        for day, total in biaya_results: biaya_data[str(int(day))] = total
        return jsonify({"success": True, "labels": labels, "pendapatanData": list(pendapatan_data.values()), "biayaData": list(biaya_data.values())})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

# --- LAPAK API ---
# --- PERUBAHAN DI SINI: API ini sekarang mengambil SEMUA supplier dan produknya ---
@app.route('/api/get_data_buat_catatan/<int:lapak_id>', methods=['GET'])
def get_data_buat_catatan(lapak_id):
    today = datetime.date.today()
    # Pengecekan apakah laporan sudah ada tetap dipertahankan
    if LaporanHarian.query.filter_by(lapak_id=lapak_id, tanggal=today).first():
        return jsonify({"success": False, "message": "Laporan untuk hari ini sudah dibuat.", "already_exists": True}), 409
    
    # HANYA mengambil data supplier, bukan produknya
    all_suppliers = Supplier.query.order_by(Supplier.nama_supplier).all()
    suppliers_data = [{"id": s.id, "name": s.nama_supplier} for s in all_suppliers]
        
    return jsonify({"success": True, "suppliers": suppliers_data})

# --- PERUBAHAN DI SINI: Logika submit laporan dirombak total untuk menangani produk dinamis ---
@app.route('/api/submit_catatan_harian', methods=['POST'])
def submit_catatan_harian():
    data = request.json
    lapak_id = data.get('lapak_id')
    today = datetime.date.today()
    if LaporanHarian.query.filter_by(lapak_id=lapak_id, tanggal=today).first():
        return jsonify({"success": False, "message": "Laporan untuk hari ini sudah pernah dibuat."}), 400
    try:
        total_pendapatan_auto, total_biaya_auto, total_terjual_auto = 0.0, 0.0, 0
        
        rekap_manual = data.get('rekap_pembayaran', {})
        new_report = LaporanHarian(
            lapak_id=lapak_id, tanggal=today, total_pendapatan=0, total_biaya_supplier=0,
            pendapatan_cash=0, pendapatan_qris=0, pendapatan_bca=0, total_produk_terjual=0,
            manual_pendapatan_cash=float(rekap_manual.get('cash', 0)),
            manual_pendapatan_qris=float(rekap_manual.get('qris', 0)),
            manual_pendapatan_bca=float(rekap_manual.get('bca', 0)),
            manual_total_pendapatan=float(rekap_manual.get('total', 0))
        )
        db.session.add(new_report)
        db.session.flush()

        # Iterasi melalui produk yang dikirim dari frontend
        for prod_data in data.get('products', []):
            stok_awal = int(prod_data.get('stok_awal', 0))
            if stok_awal == 0: continue # Lewati jika stok awal tidak diisi

            # Karena semua produk sekarang manual, kita buat entri produk baru
            # Tidak perlu lagi mencari product_id
            new_product = Product(
                nama_produk=prod_data['nama_produk'],
                supplier_id=prod_data.get('supplier_id'),
                harga_beli=float(prod_data.get('harga_beli', HARGA_BELI_DEFAULT)),
                harga_jual=float(prod_data.get('harga_jual', HARGA_JUAL_DEFAULT)),
                is_manual=True # Tandai sebagai produk manual
            )
            db.session.add(new_product)
            db.session.flush() # flush() untuk mendapatkan ID dari produk baru
            
            stok_akhir = int(prod_data.get('stok_akhir', 0))
            jumlah_terjual = max(0, stok_awal - stok_akhir)
            total_harga_jual = jumlah_terjual * new_product.harga_jual
            total_harga_beli = jumlah_terjual * new_product.harga_beli

            rincian = LaporanHarianProduk(
                laporan_id=new_report.id, 
                product_id=new_product.id,  # Gunakan ID produk yang baru dibuat
                stok_awal=stok_awal, 
                stok_akhir=stok_akhir, 
                jumlah_terjual=jumlah_terjual, 
                total_harga_jual=total_harga_jual, 
                total_harga_beli=total_harga_beli
            )
            db.session.add(rincian)
            
            total_pendapatan_auto += total_harga_jual
            total_biaya_auto += total_harga_beli
            total_terjual_auto += jumlah_terjual
        
        new_report.total_pendapatan = total_pendapatan_auto
        new_report.total_biaya_supplier = total_biaya_auto
        new_report.total_produk_terjual = total_terjual_auto
        new_report.pendapatan_cash = float(rekap_manual.get('cash', 0))
        new_report.pendapatan_qris = float(rekap_manual.get('qris', 0))
        new_report.pendapatan_bca = float(rekap_manual.get('bca', 0))

        db.session.commit()
        return jsonify({"success": True, "message": "Laporan harian berhasil dikirim!"})
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error submitting catatan harian: {e}")
        return jsonify({"success": False, "message": f"Gagal menyimpan laporan: {str(e)}"}), 500


@app.route('/api/get_history_laporan/<int:lapak_id>', methods=['GET'])
def get_history_laporan(lapak_id):
    try:
        reports = LaporanHarian.query.filter_by(lapak_id=lapak_id).order_by(LaporanHarian.tanggal.desc()).all()
        report_list = [{"id": r.id, "tanggal": r.tanggal.isoformat(), "total_pendapatan": r.total_pendapatan, "total_produk_terjual": r.total_produk_terjual, "status": r.status} for r in reports]
        return jsonify({"success": True, "reports": report_list})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

# --- SUPPLIER API ---
@app.route('/api/get_data_supplier/<int:supplier_id>', methods=['GET'])
def get_data_supplier(supplier_id):
    try:
        today = datetime.date.today()
        start_of_month = today.replace(day=1)
        balance_info = SupplierBalance.query.filter_by(supplier_id=supplier_id).first()
        total_tagihan = balance_info.balance if balance_info else 0.0
        penjualan_bulan_ini = db.session.query(func.sum(LaporanHarianProduk.total_harga_beli)).join(LaporanHarian, LaporanHarian.id == LaporanHarianProduk.laporan_id).join(Product, Product.id == LaporanHarianProduk.product_id).filter(Product.supplier_id == supplier_id, LaporanHarian.tanggal >= start_of_month, LaporanHarian.status == 'Terkonfirmasi').scalar() or 0
        return jsonify({"success": True, "summary": {"total_tagihan": total_tagihan, "penjualan_bulan_ini": penjualan_bulan_ini}})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

# --- PERUBAHAN DI SINI: API ini sekarang bisa filter berdasarkan lapak ---
@app.route('/api/get_supplier_history/<int:supplier_id>', methods=['GET'])
def get_supplier_history(supplier_id):
    try:
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        lapak_id = request.args.get('lapak_id')

        payments_query = PembayaranSupplier.query.filter_by(supplier_id=supplier_id)
        if start_date_str: payments_query = payments_query.filter(PembayaranSupplier.tanggal_pembayaran >= datetime.datetime.strptime(start_date_str, '%Y-%m-%d').date())
        if end_date_str: payments_query = payments_query.filter(PembayaranSupplier.tanggal_pembayaran <= datetime.datetime.strptime(end_date_str, '%Y-%m-%d').date())
        payments = payments_query.order_by(PembayaranSupplier.tanggal_pembayaran.desc()).all()
        payment_list = [{"tanggal": p.tanggal_pembayaran.strftime('%Y-%m-%d'), "jumlah": p.jumlah_pembayaran, "metode": p.metode_pembayaran} for p in payments]

        sales_query = db.session.query(LaporanHarian.tanggal, Lapak.lokasi, Product.nama_produk, LaporanHarianProduk.jumlah_terjual).select_from(LaporanHarianProduk).join(Product, Product.id == LaporanHarianProduk.product_id).join(LaporanHarian, LaporanHarian.id == LaporanHarianProduk.laporan_id).join(Lapak, Lapak.id == LaporanHarian.lapak_id).filter(Product.supplier_id == supplier_id, LaporanHarian.status == 'Terkonfirmasi')
        if start_date_str: sales_query = sales_query.filter(LaporanHarian.tanggal >= datetime.datetime.strptime(start_date_str, '%Y-%m-%d').date())
        if end_date_str: sales_query = sales_query.filter(LaporanHarian.tanggal <= datetime.datetime.strptime(end_date_str, '%Y-%m-%d').date())
        if lapak_id: sales_query = sales_query.filter(LaporanHarian.lapak_id == lapak_id)
        sales = sales_query.order_by(LaporanHarian.tanggal.desc(), Lapak.lokasi).all()
        sales_list = [{"tanggal": s.tanggal.strftime('%Y-%m-%d'), "lokasi": s.lokasi, "nama_produk": s.nama_produk, "terjual": s.jumlah_terjual} for s in sales]
        
        all_lapaks = Lapak.query.order_by(Lapak.lokasi).all()
        lapak_list = [{"id": l.id, "lokasi": l.lokasi} for l in all_lapaks]
        
        return jsonify({"success": True, "payments": payment_list, "sales": sales_list, "lapaks": lapak_list})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

# --- PERUBAHAN DI SINI: Detail laporan sekarang dikelompokkan per supplier untuk kemudahan tampilan ---
@app.route('/api/get_report_details/<int:report_id>')
def get_report_details(report_id):
    try:
        report = LaporanHarian.query.options(joinedload(LaporanHarian.lapak).joinedload(Lapak.penanggung_jawab), joinedload(LaporanHarian.rincian_produk).joinedload(LaporanHarianProduk.product).joinedload(Product.supplier)).get(report_id)
        if not report: return jsonify({"success": False, "message": "Laporan tidak ditemukan"}), 404

        rincian_per_supplier = {}
        for item in report.rincian_produk:
            supplier_name = item.product.supplier.nama_supplier if item.product.supplier else "Produk Manual"
            if supplier_name not in rincian_per_supplier: rincian_per_supplier[supplier_name] = []
            rincian_per_supplier[supplier_name].append({"nama_produk": item.product.nama_produk, "stok_awal": item.stok_awal, "stok_akhir": item.stok_akhir, "terjual": item.jumlah_terjual, "harga_jual": item.product.harga_jual, "total_pendapatan": item.total_harga_jual})

        data = {
            "id": report.id, "tanggal": report.tanggal.strftime('%d %B %Y'), "status": report.status,
            "lokasi": report.lapak.lokasi, "penanggung_jawab": report.lapak.penanggung_jawab.nama_lengkap,
            "rincian_per_supplier": rincian_per_supplier,
            "rekap_otomatis": {"terjual_cash": report.pendapatan_cash, "terjual_qris": report.pendapatan_qris, "terjual_bca": report.pendapatan_bca, "total_produk_terjual": report.total_produk_terjual, "total_pendapatan": report.total_pendapatan, "total_biaya_supplier": report.total_biaya_supplier},
            "rekap_manual": {"terjual_cash": report.manual_pendapatan_cash, "terjual_qris": report.manual_pendapatan_qris, "terjual_bca": report.manual_pendapatan_bca, "total_produk_terjual": report.total_produk_terjual, "total_pendapatan": report.manual_total_pendapatan}
        }
        return jsonify({"success": True, "data": data})
    except Exception as e:
        return jsonify({"success": False, "message": "Terjadi kesalahan pada server"}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5001)