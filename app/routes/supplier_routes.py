from flask import Blueprint, jsonify, current_app, request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.sql import func
from sqlalchemy.orm import joinedload
import datetime
import logging

from app import db
from app.models import (
  Admin, Lapak, Supplier, Product, LaporanHarian, LaporanHarianProduk, SupplierBalance, SuperOwnerBalance, PembayaranSupplier, Notifikasi
)

supplier_bp = Blueprint('supplier', __name__, url_prefix='/api/supplier')

@supplier_bp.route('/get_data_supplier/<int:supplier_id>', methods=['GET'])
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

@supplier_bp.route('/get_supplier_history/<int:supplier_id>', methods=['GET'])
def get_supplier_history(supplier_id):
    try:
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        lapak_id = request.args.get('lapak_id') 
        payments_query = PembayaranSupplier.query.filter_by(supplier_id=supplier_id)
        if start_date_str:
            start_date = datetime.datetime.strptime(start_date_str, '%Y-%m-%d').date()
            payments_query = payments_query.filter(PembayaranSupplier.tanggal_pembayaran >= start_date)
        if end_date_str:
            end_date = datetime.datetime.strptime(end_date_str, '%Y-%m-%d').date()
            payments_query = payments_query.filter(PembayaranSupplier.tanggal_pembayaran <= end_date)
        
        payments = payments_query.order_by(PembayaranSupplier.tanggal_pembayaran.desc()).all()
        payment_list = [{"tanggal": p.tanggal_pembayaran.strftime('%Y-%m-%d'), "jumlah": p.jumlah_pembayaran, "metode": p.metode_pembayaran} for p in payments]

        sales_query = db.session.query(
            LaporanHarian.tanggal, Lapak.lokasi, Product.nama_produk,
            LaporanHarianProduk.jumlah_terjual
        ).select_from(LaporanHarianProduk)\
         .join(Product, Product.id == LaporanHarianProduk.product_id)\
         .join(LaporanHarian, LaporanHarian.id == LaporanHarianProduk.laporan_id)\
         .join(Lapak, Lapak.id == LaporanHarian.lapak_id)\
         .filter(Product.supplier_id == supplier_id, LaporanHarian.status == 'Terkonfirmasi')

        if start_date_str:
            start_date = datetime.datetime.strptime(start_date_str, '%Y-%m-%d').date()
            sales_query = sales_query.filter(LaporanHarian.tanggal >= start_date)
        if end_date_str:
            end_date = datetime.datetime.strptime(end_date_str, '%Y-%m-%d').date()
            sales_query = sales_query.filter(LaporanHarian.tanggal <= end_date)
        
        if lapak_id:
            sales_query = sales_query.filter(LaporanHarian.lapak_id == lapak_id)

        sales = sales_query.order_by(LaporanHarian.tanggal.desc(), Lapak.lokasi).all()
        sales_list = [{"tanggal": s.tanggal.strftime('%Y-%m-%d'), "lokasi": s.lokasi, "nama_produk": s.nama_produk, "terjual": s.jumlah_terjual} for s in sales]
        
        all_lapaks = Lapak.query.order_by(Lapak.lokasi).all()
        lapak_list = [{"id": l.id, "lokasi": l.lokasi} for l in all_lapaks]
        
        return jsonify({"success": True, "payments": payment_list, "sales": sales_list, "lapaks": lapak_list})
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error getting supplier history: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@supplier_bp.route('/get_supplier_notifications/<int:supplier_id>', methods=['GET'])
def get_supplier_notifications(supplier_id):
    try:
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
      
@supplier_bp.route('/update_notification_status/<int:notification_id>', methods=['POST'])
def update_notification_status(notification_id):
    data = request.json
    new_status = data.get('status')

    if new_status not in ['dibaca', 'diarsipkan', 'baru']:
        return jsonify({"success": False, "message": "Status tidak valid."}), 400

    try:
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

@supplier_bp.route('/get_archived_notifications/<int:supplier_id>', methods=['GET'])
def get_archived_notifications(supplier_id):
    try:
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
