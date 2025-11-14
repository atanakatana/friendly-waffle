import datetime
import re
import random
from datetime import timedelta
from sqlalchemy.exc import IntegrityError
from sqlalchemy.sql import func, or_
from sqlalchemy.orm import joinedload
from calendar import monthrange
from app import db
from werkzeug.security import generate_password_hash, check_password_hash

HARGA_BELI_DEFAULT = 8000.0
HARGA_JUAL_DEFAULT = 10000.0

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
    username = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(120), nullable=False) 
    nomor_kontak = db.Column(db.String(20), nullable=True)
    password = db.Column(db.String(120), nullable=False)
    super_owner_id= db.Column(db.Integer, db.ForeignKey('super_owner.id'), nullable=True)
    created_by_owner_id = db.Column(db.Integer, db.ForeignKey('admin.id'), nullable=True)
    __table_args__ = (
        db.UniqueConstraint('created_by_owner_id', 'username', name='_owner_username_uc'),
        db.UniqueConstraint('created_by_owner_id', 'email', name='_owner_email_uc')
    )
    def set_password(self, password):
        # membuat hash dari password
        self.password = generate_password_hash(password)
    def check_password(self, password):
        # membaca hash password
        return check_password_hash(self.password, password)

class SuperOwner(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nama_lengkap = db.Column(db.String(100), nullable=True)
    username = db.Column(db.String(80), unique=True, nullable=False) 
    email = db.Column(db.String(120), unique=True, nullable=True)
    nomor_kontak = db.Column(db.String(20), nullable=True)
    password = db.Column(db.String(120), nullable=False)
    owners= db.relationship('Admin', backref='super_owner', lazy=True)
    def set_password(self, password):
        self.password = generate_password_hash(password)
    def check_password(self, password):
        return check_password_hash(self.password, password)

class Supplier(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nama_supplier = db.Column(db.String(100), nullable=False)
    username = db.Column(db.String(80), nullable=False)
    kontak = db.Column(db.String(20), nullable=True)
    nomor_register = db.Column(db.String(50), nullable=True) 
    alamat = db.Column(db.Text, nullable=True)
    password = db.Column(db.String(120), nullable=False)
    metode_pembayaran = db.Column(db.String(20), nullable=True)
    nomor_rekening = db.Column(db.String(50), nullable=True)
    owner_id = db.Column(db.Integer, db.ForeignKey('admin.id'), nullable=False)
    products = db.relationship('Product', backref='supplier', lazy=True, cascade="all, delete-orphan")
    balance = db.relationship('SupplierBalance', backref='supplier', uselist=False, cascade="all, delete-orphan")
    __table_args__ = (
        db.UniqueConstraint('owner_id', 'username', name='_owner_supplier_username_uc'),
        db.UniqueConstraint('owner_id', 'nomor_register', name='_owner_supplier_reg_uc')
    )
    def set_password(self, password):
        self.password = generate_password_hash(password)
    def check_password(self, password):
        return check_password_hash(self.password, password)
    
class Lapak(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lokasi = db.Column(db.String(200), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('admin.id'), nullable=False)
    owner_id = db.Column(db.Integer, db.ForeignKey('admin.id'), nullable=False)
    penanggung_jawab = db.relationship('Admin', foreign_keys=[user_id], backref=db.backref('lapak_pj', uselist=False))
    anggota = db.relationship('Admin', secondary=lapak_anggota_association, lazy='subquery',
                              backref=db.backref('lapak_anggota', lazy=True))
    reports = db.relationship('LaporanHarian', backref='lapak', lazy=True, cascade="all, delete-orphan")
    __table_args__ = (
        db.UniqueConstraint('owner_id', 'lokasi', name='_owner_lapak_lokasi_uc'),
    )

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

class Notifikasi(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    lapak_id = db.Column(db.Integer, db.ForeignKey('lapak.id'), nullable=False)
    supplier_id = db.Column(db.Integer, db.ForeignKey('supplier.id'), nullable=False)
    waktu_dikirim = db.Column(db.DateTime, server_default=func.now())
    status = db.Column(db.String(20), default='baru', nullable=False) 
    product = db.relationship('Product')
    lapak = db.relationship('Lapak')
    supplier = db.relationship('Supplier')
 
class RiwayatPenarikanSuperOwner(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    super_owner_id = db.Column(db.Integer, db.ForeignKey('super_owner.id'), nullable=False)
    owner_id = db.Column(db.Integer, db.ForeignKey('admin.id'), nullable=True) 
    jumlah_penarikan = db.Column(db.Float, nullable=False)
    tanggal_penarikan = db.Column(db.DateTime, server_default=func.now())

    super_owner = db.relationship('SuperOwner')
    owner = db.relationship('Admin')