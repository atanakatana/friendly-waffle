# import dari library luar milik python
from flask import Blueprint, jsonify, current_app, request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.sql import func
from sqlalchemy.orm import joinedload
import datetime
import logging
import re
from calendar import monthrange

# import dari repo internal (lokal)
from app import db
from app.models import (
  Admin, Lapak, Supplier, Product, LaporanHarian, LaporanHarianProduk, SupplierBalance, SuperOwnerBalance, PembayaranSupplier
)

owner_bp = Blueprint('owner', __name__, url_prefix='/api/owner')

# --- OWNER API ---
@owner_bp.route('/get_data_owner/<int:owner_id>', methods=['GET'])
def get_owner_data(owner_id):
    try:
        # Bagian ini (mengambil admin, lapak, supplier) sudah benar
        admins = Admin.query.filter(
            Admin.created_by_owner_id == owner_id,
            Admin.super_owner_id.is_(None)
        ).all()
        lapaks = Lapak.query.options(
            joinedload(Lapak.penanggung_jawab), 
            joinedload(Lapak.anggota)
        ).filter_by(owner_id=owner_id).all()
        suppliers = Supplier.query.filter_by(owner_id=owner_id).all()

        admin_list = [{"id": u.id, "nama_lengkap": u.nama_lengkap, "username": u.username, "email": u.email, "nomor_kontak": u.nomor_kontak, "password": u.password} for u in admins]
        lapak_list = [{"id": l.id, "lokasi": l.lokasi, "penanggung_jawab": f"{l.penanggung_jawab.nama_lengkap}", "user_id": l.user_id, "anggota": [{"id": a.id, "nama": a.nama_lengkap} for a in l.anggota], "anggota_ids": [a.id for a in l.anggota]} for l in lapaks]
        supplier_list = []
        for s in suppliers:
            supplier_list.append({
                "id": s.id, "nama_supplier": s.nama_supplier, "username": s.username, "kontak": s.kontak,
                "nomor_register": s.nomor_register, "alamat": s.alamat, "password": s.password,
                "metode_pembayaran": s.metode_pembayaran, "nomor_rekening": s.nomor_rekening
            })

        # === PERBAIKAN KPI DIMULAI DI SINI ===
        today = datetime.date.today()
        start_of_month = today.replace(day=1)
        
        lapak_ids = [l.id for l in lapaks] 

        total_pendapatan_bulan_ini = 0
        total_biaya_bulan_ini = 0
        profit_owner_bulan_ini = 0
        profit_superowner_bulan_ini = 0

        if lapak_ids:
            kpi_data = db.session.query(
                func.sum(LaporanHarian.total_pendapatan).label('total_pendapatan'),
                func.sum(LaporanHarian.total_biaya_supplier).label('total_biaya'),
                func.sum(LaporanHarian.keuntungan_owner).label('total_profit_owner'),
                func.sum(LaporanHarian.keuntungan_superowner).label('total_profit_superowner')
            ).filter(
                LaporanHarian.lapak_id.in_(lapak_ids),
                
                # --- INI ADALAH PERBAIKANNYA ---
                # Ubah dari '==' menjadi '.in_()'
                LaporanHarian.status.in_(['Terkonfirmasi', 'Difinalisasi']),
                # ------------------------------
                
                LaporanHarian.tanggal >= start_of_month,
                LaporanHarian.tanggal <= today
            ).first()

            if kpi_data:
                total_pendapatan_bulan_ini = kpi_data.total_pendapatan or 0
                total_biaya_bulan_ini = kpi_data.total_biaya or 0
                profit_owner_bulan_ini = kpi_data.total_profit_owner or 0
                profit_superowner_bulan_ini = kpi_data.total_profit_superowner or 0
        # === AKHIR PERBAIKAN KPI ===

        summary_data = {
            "pendapatan_bulan_ini": total_pendapatan_bulan_ini,
            "biaya_bulan_ini": total_biaya_bulan_ini,
            "profit_owner_bulan_ini": profit_owner_bulan_ini,
            "profit_superowner_bulan_ini": profit_superowner_bulan_ini
        }

        return jsonify({"admin_data": admin_list, "lapak_data": lapak_list, "supplier_data": supplier_list, "summary": summary_data})
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error getting owner data: {str(e)}")
        return jsonify({"success": False, "message": f"Terjadi kesalahan server: {str(e)}"}), 500

# GANTI FUNGSI LAMA DENGAN VERSI BARU INI
@owner_bp.route('/get_owner_verification_reports/<int:owner_id>', methods=['GET'])
def get_owner_verification_reports(owner_id):
    try:
        # === LOGIKA BARU ===
        # Ambil semua laporan dari lapak yang 'owner_id'-nya cocok
        reports = LaporanHarian.query.join(Lapak).filter(
            Lapak.owner_id == owner_id,
            LaporanHarian.status == 'Terkonfirmasi' # <-- INI LOGIKA BARU (Sudah dikonfirmasi)
        ).options(
            joinedload(LaporanHarian.lapak)
        ).order_by(LaporanHarian.tanggal.desc()).all()

        report_list = [{
            "id": r.id,
            "tanggal": r.tanggal.strftime('%d %B %Y'),
            "lokasi": r.lapak.lokasi,
            "total_pendapatan": r.total_pendapatan,
            "total_produk_terjual": r.total_produk_terjual
        } for r in reports]

        return jsonify({"success": True, "reports": report_list})
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error getting verification reports: {str(e)}")
        return jsonify({"success": False, "message": "Gagal mengambil data verifikasi laporan."}), 500
      
# GANTI FUNGSI LAMA DENGAN VERSI BARU INI
@owner_bp.route('/add_admin', methods=['POST'])
def add_admin():
    data = request.json
    if data['password'] != data['password_confirm']: return jsonify({"success": False, "message": "Password dan konfirmasi password tidak cocok."}), 400
    try:
        new_admin = Admin(
            nama_lengkap=data['nama_lengkap'],
            username=data['username'], 
            email=data['email'], 
            nomor_kontak=data['nomor_kontak'], 
            password=data['password'],
            # PERUBAHAN DI SINI: Terima super_owner_id jika ada
            super_owner_id=data.get('super_owner_id'),
            created_by_owner_id=data.get('created_by_owner_id'),
        )
        db.session.add(new_admin)
        db.session.commit()
        return jsonify({"success": True, "message": "Admin/Owner berhasil ditambahkan"})
    except IntegrityError as e:
        db.session.rollback()
        err_msg = str(e.orig).lower()
        message = "Gagal: Terjadi duplikasi data."
        if '_owner_nik_uc' in err_msg or 'admin.nik' in err_msg:
            message = "Gagal: NIK ini sudah terdaftar untuk admin lain di bawah Anda."
        elif '_owner_username_uc' in err_msg or 'admin.username' in err_msg:
            message = "Gagal: Username ini sudah terdaftar untuk admin lain di bawah Anda."
        elif '_owner_email_uc' in err_msg or 'admin.email' in err_msg:
            message = "Gagal: Email ini sudah terdaftar untuk admin lain di bawah Anda."
        return jsonify({"success": False, "message": message}), 400

@owner_bp.route('/update_admin/<int:admin_id>', methods=['PUT'])
def update_admin(admin_id):
    data = request.json
    admin = Admin.query.get_or_404(admin_id)
    if data.get('password') and data['password'] != data['password_confirm']: return jsonify({"success": False, "message": "Password dan konfirmasi password tidak cocok."}), 400
    try:
        admin.nama_lengkap = data['nama_lengkap']
        admin.username = data['username']
        admin.email = data['email']
        admin.nomor_kontak = data['nomor_kontak']
        if data.get('password'): admin.password = data['password']
        db.session.commit()
        return jsonify({"success": True, "message": "Data Admin berhasil diperbarui"})
    except IntegrityError as e:
        db.session.rollback()
        err_msg = str(e.orig).lower()
        message = "Gagal: Terjadi duplikasi data."
        if '_owner_nik_uc' in err_msg or 'admin.nik' in err_msg:
            message = "Gagal: NIK ini sudah terdaftar untuk admin lain di bawah Anda."
        elif '_owner_username_uc' in err_msg or 'admin.username' in err_msg:
            message = "Gagal: Username ini sudah terdaftar untuk admin lain di bawah Anda."
        elif '_owner_email_uc' in err_msg or 'admin.email' in err_msg:
            message = "Gagal: Email ini sudah terdaftar untuk admin lain di bawah Anda."
        return jsonify({"success": False, "message": message}), 400

@owner_bp.route('/delete_admin/<int:admin_id>', methods=['DELETE'])
def delete_admin(admin_id):
    admin = Admin.query.get_or_404(admin_id)
    if Lapak.query.filter_by(user_id=admin_id).first(): return jsonify({"success": False, "message": "Gagal menghapus: Admin ini adalah Penanggung Jawab sebuah lapak."}), 400
    db.session.delete(admin)
    db.session.commit()
    return jsonify({"success": True, "message": "Admin berhasil dihapus"})

@owner_bp.route('/add_lapak', methods=['POST'])
def add_lapak():
    data = request.json
    try:
        new_lapak = Lapak(lokasi=data['lokasi'], user_id=data['user_id'], owner_id=data['owner_id'])
        anggota_ids = data.get('anggota_ids', [])
        if anggota_ids: new_lapak.anggota = Admin.query.filter(Admin.id.in_(anggota_ids)).all()
        db.session.add(new_lapak)
        db.session.commit()
        return jsonify({"success": True, "message": "Lapak berhasil ditambahkan"})
    except IntegrityError as e:
        db.session.rollback()
        message = "Gagal: Nama lokasi lapak sudah Anda gunakan."
        if '_owner_lapak_lokasi_uc' not in str(e.orig).lower():
            message = "Gagal: Terjadi kesalahan database."
        return jsonify({"success": False, "message": message}), 400

@owner_bp.route('/update_lapak/<int:lapak_id>', methods=['PUT'])
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
    except IntegrityError as e:
        db.session.rollback()
        message = "Gagal: Nama lokasi lapak sudah Anda gunakan."
        if '_owner_lapak_lokasi_uc' not in str(e.orig).lower():
            message = "Gagal: Terjadi kesalahan database."
        return jsonify({"success": False, "message": message}), 400

@owner_bp.route('/delete_lapak/<int:lapak_id>', methods=['DELETE'])
def delete_lapak(lapak_id):
    lapak = Lapak.query.get_or_404(lapak_id)
    db.session.delete(lapak)
    db.session.commit()
    return jsonify({"success": True, "message": "Lapak berhasil dihapus"})

# --- REVISI: Logika baru untuk nomor registrasi ---
# --- REVISI: Ubah rute untuk menerima owner_id ---
@owner_bp.route('/get_next_supplier_reg_number/<int:owner_id>', methods=['GET'])
def get_next_supplier_reg_number(owner_id): # <-- Terima owner_id
    used_numbers = set()
    
    # --- REVISI: Filter supplier berdasarkan owner_id ---
    suppliers = Supplier.query.filter_by(owner_id=owner_id).filter(Supplier.nomor_register.like('REG%')).all()
    
    for s in suppliers:
        num_part = re.search(r'\d+', s.nomor_register)
        if num_part:
            used_numbers.add(int(num_part.group()))
    
    next_id = 1 # <-- Selalu mulai dari 1 (untuk owner ini)
    while next_id in used_numbers:
        next_id += 1
        
    return jsonify({"success": True, "reg_number": f"REG{next_id:03d}"})
  
# --- REVISI: Tambahkan metode pembayaran & no rekening ---
@owner_bp.route('/add_supplier', methods=['POST'])
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
            nomor_rekening=data.get('nomor_rekening'),
            owner_id=data.get('owner_id'),
        )
        new_supplier.balance = SupplierBalance(balance=0.0)
        db.session.add(new_supplier)
        db.session.commit()
        return jsonify({"success": True, "message": "Supplier berhasil ditambahkan"})
    except IntegrityError as e:
        db.session.rollback()
        err_msg = str(e.orig).lower()
        message = "Gagal: Terjadi duplikasi data."
        if '_owner_supplier_username_uc' in err_msg or 'supplier.username' in err_msg:
            message = "Gagal: Username ini sudah terdaftar untuk supplier lain di bawah Anda."
        elif '_owner_supplier_reg_uc' in err_msg or 'supplier.nomor_register' in err_msg:
            message = "Gagal: Nomor Register ini sudah terdaftar untuk supplier lain di bawah Anda."
        return jsonify({"success": False, "message": message}), 400
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error adding supplier: {str(e)}")
        return jsonify({"success": False, "message": f"Terjadi kesalahan server: {str(e)}"}), 500

# --- REVISI: Update metode pembayaran & no rekening ---
@owner_bp.route('/update_supplier/<int:supplier_id>', methods=['PUT'])
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

@owner_bp.route('/delete_supplier/<int:supplier_id>', methods=['DELETE'])
def delete_supplier(supplier_id):
    supplier = Supplier.query.get_or_404(supplier_id)
    db.session.delete(supplier)
    db.session.commit()
    return jsonify({"success": True, "message": "Supplier berhasil dihapus"})

@owner_bp.route('/get_owner_supplier_history/<int:supplier_id>', methods=['GET'])
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

@owner_bp.route('/get_laporan_pendapatan_harian')
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

@owner_bp.route('/get_laporan_biaya_harian')
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

# (Sekitar baris 828 di app.py)
# (Sekitar baris 828 di app.py)
@owner_bp.route('/get_manage_reports')
def get_manage_reports():
    try:
        # Ambil semua parameter dari request
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        supplier_id = request.args.get('supplier_id')
        status = request.args.get('status')
        owner_id = request.args.get('owner_id') # <-- 1. AMBIL OWNER ID

        # Query dasar untuk semua laporan
        query = LaporanHarian.query.options(
            joinedload(LaporanHarian.lapak).joinedload(Lapak.penanggung_jawab)
        )

        # === 2. TAMBAHKAN FILTER OWNER INI ===
        if owner_id:
            query = query.join(Lapak, LaporanHarian.lapak_id == Lapak.id)\
                         .filter(Lapak.owner_id == owner_id)
        # === AKHIR FILTER OWNER ===

        # === LOGIKA BARU UNTUK STATUS ===
        if status:
            if status == 'semua':
                pass # Jangan filter apa-apa
            else:
                query = query.filter(LaporanHarian.status == status)
        else:
            # Jika TIDAK ada parameter status, default ke 'Menunggu Konfirmasi'
            query = query.filter(LaporanHarian.status == 'Menunggu Konfirmasi')
        # === AKHIR LOGIKA BARU ===

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
# (Ganti fungsi lama di baris 908)
# (Ganti fungsi lama di baris 908)
@owner_bp.route('/confirm_report/<int:report_id>', methods=['POST'])
def confirm_report(report_id):
    try:
        # 1. Ambil owner_id yang sedang login (misal: Ata)
        data = request.json
        owner_id = data.get('owner_id')
        if not owner_id:
            return jsonify({"success": False, "message": "ID Owner tidak ditemukan."}), 400

        report = LaporanHarian.query.options(
            joinedload(LaporanHarian.rincian_produk).joinedload(LaporanHarianProduk.product).joinedload(Product.supplier).joinedload(Supplier.balance),
            joinedload(LaporanHarian.lapak)
        ).get(report_id)

        if not report: return jsonify({"success": False, "message": "Laporan tidak ditemukan."}), 404
        if report.status == 'Terkonfirmasi': return jsonify({"success": False, "message": "Laporan ini sudah dikonfirmasi."}), 400

        report.status = 'Terkonfirmasi'
        
        # Update saldo supplier (logika ini sudah benar)
        for rincian in report.rincian_produk:
            if rincian.product.supplier and rincian.product.supplier.balance:
                rincian.product.supplier.balance.balance += rincian.total_harga_beli
            
        # Hitung profit (logika ini sudah benar)
        total_profit = report.total_pendapatan - report.total_biaya_supplier
        keuntungan_superowner = total_profit * current_app.config['PROFIT_SHARE_SUPEROWNER_RATIO']
        keuntungan_owner = total_profit * current_app.config['PROFIT_SHARE_OWNER_RATIO']
        report.keuntungan_owner = keuntungan_owner
        report.keuntungan_superowner = keuntungan_superowner
        
        # 2. Ambil data 'managing_owner' (Ata) menggunakan owner_id
        managing_owner = Admin.query.get(owner_id) 
        
        if managing_owner and managing_owner.super_owner_id:
            super_owner_id = managing_owner.super_owner_id
            
            # 3. Cari SuperOwnerBalance yang cocok (milik Ata)
            so_balance = SuperOwnerBalance.query.filter_by(super_owner_id=super_owner_id, owner_id=managing_owner.id).first()
            if so_balance:
                # 4a. Tambahkan profit ke saldo Ata
                so_balance.balance += keuntungan_superowner
            else:
                # 4b. Buat saldo baru untuk Ata
                db.session.add(SuperOwnerBalance(super_owner_id=super_owner_id, owner_id=managing_owner.id, balance=keuntungan_superowner))

        db.session.commit()
        logging.info(f"-> LAPORAN #{report.id} DIKONFIRMASI OLEH OWNER #{owner_id}. Profit SuperOwner +{keuntungan_superowner}")
        return jsonify({"success": True, "message": "Laporan berhasil dikonfirmasi."})
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error confirming report: {str(e)}")
        return jsonify({"success": False, "message": f"Terjadi kesalahan server: {str(e)}"}), 500
        
# (Ganti fungsi lama di baris 906 dengan ini)

# (Sekitar baris 964 di app.py)
@owner_bp.route('/get_pembayaran_data', methods=['GET'])
def get_pembayaran_data():
    try:
        # === PERBAIKAN: Ambil owner_id dari request ===
        owner_id = request.args.get('owner_id')
        if not owner_id:
            return jsonify({"success": False, "message": "Owner ID tidak ditemukan."}), 400

        # === PERBAIKAN: Filter supplier berdasarkan owner_id ===
        suppliers = Supplier.query.filter_by(owner_id=owner_id).options(joinedload(Supplier.balance)).all()
        supplier_list = []
        
        for s in suppliers:
            tanggal_tagihan_masuk = None
            # Jika supplier punya tagihan (balance > 0)
            if s.balance and s.balance.balance > 0.01:
                # Cari tanggal laporan terkonfirmasi paling LAMA untuk supplier ini
                oldest_report_date = db.session.query(
                    func.min(LaporanHarian.tanggal)
                ).select_from(LaporanHarian).\
                  join(LaporanHarianProduk, LaporanHarian.id == LaporanHarianProduk.laporan_id).\
                  join(Product, LaporanHarianProduk.product_id == Product.id).\
                  filter(
                    Product.supplier_id == s.id,
                    LaporanHarian.status == 'Terkonfirmasi'
                  ).scalar()
                
                if oldest_report_date:
                    tanggal_tagihan_masuk = oldest_report_date.isoformat()

            supplier_list.append({
                "supplier_id": s.id, 
                "nama_supplier": s.nama_supplier, 
                "total_tagihan": s.balance.balance if s.balance else 0.0, 
                "metode_pembayaran": s.metode_pembayaran, 
                "nomor_rekening": s.nomor_rekening,
                "tanggal_masuk": tanggal_tagihan_masuk # <-- DATA BARU
            })
        
        return jsonify({
            "success": True, 
            "supplier_balances": supplier_list
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

# --- REVISI: Hapus pemilihan metode, ambil dari data supplier ---
@owner_bp.route('/submit_pembayaran', methods=['POST'])
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

# (Ganti fungsi lama di baris 1009 dengan ini)

@owner_bp.route('/get_all_payment_history', methods=['GET'])
def get_all_payment_history():
    try:
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        metode = request.args.get('metode')
        
        # === PERBAIKAN 1: Ambil owner_id ===
        owner_id = request.args.get('owner_id')
        if not owner_id:
            return jsonify({"success": False, "message": "Owner ID tidak ditemukan."}), 400

        start_date, end_date = None, None
        if start_date_str:
            start_date = datetime.datetime.strptime(start_date_str, '%Y-%m-%d').date()
        if end_date_str:
            end_date = datetime.datetime.strptime(end_date_str, '%Y-%m-%d').date()

        all_history = []

        # === PERBAIKAN 2: Tambahkan JOIN dan FILTER owner_id ===
        payments_query = PembayaranSupplier.query.join(Supplier).filter(
            Supplier.owner_id == owner_id
        ).options(joinedload(PembayaranSupplier.supplier))
        if start_date:
            payments_query = payments_query.filter(PembayaranSupplier.tanggal_pembayaran >= start_date)
        if end_date:
            payments_query = payments_query.filter(PembayaranSupplier.tanggal_pembayaran <= end_date)
        if metode and metode != 'semua':
            payments_query = payments_query.filter(PembayaranSupplier.metode_pembayaran == metode)
        
        payments = payments_query.all()
        for p in payments:
            all_history.append({
                "tanggal": p.tanggal_pembayaran,
                "supplier_name": p.supplier.nama_supplier,
                "jumlah": p.jumlah_pembayaran,
                "metode": p.metode_pembayaran,
                "keterangan": "Tagihan Lunas",
                "tipe": "pembayaran" # Untuk styling di frontend
            })

        # 2. Ambil "Tagihan Masuk" (Laporan terkonfirmasi)
        # Filter 'metode' tidak berlaku di sini, karena ini adalah tagihan, bukan pembayaran
        tagihan_query = db.session.query(
            LaporanHarian.tanggal,
            Supplier.nama_supplier,
            func.sum(LaporanHarianProduk.total_harga_beli).label('total_biaya_harian')
        ).select_from(LaporanHarian).\
          join(LaporanHarianProduk, LaporanHarian.id == LaporanHarianProduk.laporan_id).\
          join(Product, LaporanHarianProduk.product_id == Product.id).\
          join(Supplier, Product.supplier_id == Supplier.id).\
          filter(LaporanHarian.status == 'Terkonfirmasi')

        # === PERBAIKAN 3: Tambahkan FILTER owner_id ===
        tagihan_query = tagihan_query.filter(Supplier.owner_id == owner_id)
        if start_date:
            tagihan_query = tagihan_query.filter(LaporanHarian.tanggal >= start_date)
        if end_date:
            tagihan_query = tagihan_query.filter(LaporanHarian.tanggal <= end_date)
        
        # Kelompokkan berdasarkan tanggal dan supplier
        tagihan_results = tagihan_query.group_by(
            LaporanHarian.tanggal, Supplier.nama_supplier
        ).having(
            func.sum(LaporanHarianProduk.total_harga_beli) > 0.01
        ).all()

        for t in tagihan_results:
            all_history.append({
                "tanggal": t.tanggal,
                "supplier_name": t.nama_supplier,
                "jumlah": t.total_biaya_harian,
                "metode": "-",
                "keterangan": "Tagihan Masuk",
                "tipe": "tagihan" # Untuk styling di frontend
            })
        
        # 3. Urutkan semua riwayat berdasarkan tanggal (terbaru dulu)
        all_history.sort(key=lambda x: x['tanggal'], reverse=True)
        
        # 4. Ubah format tanggal menjadi string setelah diurutkan
        history_list = [
            {**item, "tanggal": item['tanggal'].strftime('%Y-%m-%d')}
            for item in all_history
        ]
        
        return jsonify({"success": True, "history": history_list})
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error getting combined payment history: {str(e)}")
        return jsonify({"success": False, "message": str(e)}), 500
    
@owner_bp.route('/get_chart_data', methods=['GET'])
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
      
# (Letakkan ini di dalam app.py, di bagian OWNER API)

# (Ganti fungsi lama di baris 1073)

@owner_bp.route('/finalize_reports', methods=['POST'])
def finalize_reports():
    data = request.json
    report_ids = data.get('report_ids', [])
    owner_id = data.get('owner_id') # Kita tetap ambil ID untuk logging

    if not report_ids or not owner_id:
        return jsonify({"success": False, "message": "Data tidak lengkap."}), 400

    try:
        # Ambil semua laporan yang akan difinalisasi
        reports_to_finalize = LaporanHarian.query.filter(
            LaporanHarian.id.in_(report_ids),
            LaporanHarian.status == 'Terkonfirmasi' # <-- PERBAIKAN 1: Periksa status yang benar
        ).all()

        if not reports_to_finalize:
            return jsonify({"success": False, "message": "Tidak ada laporan yang valid untuk difinalisasi."}), 400

        # Loop dan ubah statusnya
        for report in reports_to_finalize:
            report.status = 'Difinalisasi' # <-- PERBAIKAN 2: Set status baru (bukan 'Terkonfirmasi' lagi)

        # PERBAIKAN 3: Hapus semua logika perhitungan profit ganda
        
        db.session.commit()
        
        logging.info(f"-> FINALISASI BERHASIL: {len(reports_to_finalize)} laporan dari Owner #{owner_id} telah ditandai 'Difinalisasi'.")
        return jsonify({"success": True, "message": f"{len(reports_to_finalize)} laporan berhasil difinalisasi."})

    except Exception as e:
        db.session.rollback()
        logging.error(f"Error during finalization: {str(e)}")
        return jsonify({"success": False, "message": "Terjadi kesalahan server saat finalisasi."}), 500
 