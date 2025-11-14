from flask import Blueprint, jsonify, current_app, request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.sql import func
from sqlalchemy.orm import joinedload
import datetime
import logging

from app import db
from app.models import (
  Admin, Lapak, Supplier, Product, LaporanHarian, LaporanHarianProduk, SupplierBalance, SuperOwnerBalance, PembayaranSupplier, RiwayatPenarikanSuperOwner
)

superowner_bp = Blueprint('superowner', __name__, url_prefix='/api/superowner')

@superowner_bp.route('/get_superowner_dashboard_data/<int:superowner_id>', methods=['GET'])
def get_superowner_dashboard_data(superowner_id):
    try:
        all_owners = Admin.query.filter_by(super_owner_id=superowner_id).all()
        
        all_balances = SuperOwnerBalance.query.filter_by(super_owner_id=superowner_id).all()
        balance_map = {b.owner_id: b.balance for b in all_balances}

        rincian_per_owner = []
        for owner in all_owners:
            current_balance = balance_map.get(owner.id, 0.0) 
            rincian_per_owner.append({
                "owner_id": owner.id, 
                "owner_name": owner.nama_lengkap, 
            })
        
        total_saldo_profit = sum(b['balance'] for b in rincian_per_owner)

        today = datetime.date.today()
        start_of_month = today.replace(day=1)
        profit_bulan_ini = db.session.query(func.sum(LaporanHarian.keuntungan_superowner))\
            .join(Lapak, LaporanHarian.lapak_id == Lapak.id)\
            .join(Admin, Lapak.owner_id == Admin.id)\
            .filter(
                Admin.super_owner_id == superowner_id,
                LaporanHarian.tanggal >= start_of_month,
                LaporanHarian.status.in_(['Terkonfirmasi', 'Difinalisasi'])
            ).scalar() or 0

        owner_terprofit = "Belum Ada" 
        
        if rincian_per_owner:
            top_owner = max(rincian_per_owner, key=lambda o: o['balance'])
            
        if top_owner['balance'] > 0:
            owner_terprofit = top_owner['owner_name']
        
        return jsonify({
            "success": True, 
            "total_saldo": total_saldo_profit, 
            "rincian_per_owner": rincian_per_owner,
            "kpi": { 
                "profit_bulan_ini": profit_bulan_ini, 
                "owner_terprofit": owner_terprofit 
            }
        })
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error getting SO dashboard data: {str(e)}")
        return jsonify({"success": False, "message": f"Gagal mengambil data dashboard: {str(e)}"}), 500

@superowner_bp.route('/get_superowner_profit_details/<int:owner_id>', methods=['GET'])
def get_superowner_profit_details(owner_id):
    try:
        profit_history = db.session.query(
            LaporanHarian.id,
            LaporanHarian.tanggal,
            Lapak.lokasi,
            LaporanHarian.keuntungan_superowner
        ).join(Lapak, LaporanHarian.lapak_id == Lapak.id)\
         .filter(
            LaporanHarian.status.in_(['Terkonfirmasi', 'Difinalisasi']),
            LaporanHarian.keuntungan_superowner > 0,
            Lapak.owner_id == owner_id 
        ).order_by(LaporanHarian.tanggal.desc()).all()

        history_list = [{
            "report_id": item.id,
            "tanggal": item.tanggal.strftime('%d %B %Y'),
            "sumber": f"Laporan dari {item.lokasi}",
            "profit": item.keuntungan_superowner
        } for item in profit_history]

        return jsonify({"success": True, "history": history_list})

    except Exception as e:
        db.session.rollback()
        logging.error(f"Error getting superowner profit details: {str(e)}")
        return jsonify({"success": False, "message": "Gagal mengambil detail profit."}), 500

@superowner_bp.route('/get_superowner_report_profit_detail/<int:report_id>')
def get_superowner_report_profit_detail(report_id):
    try:
        report = LaporanHarian.query.options(
            joinedload(LaporanHarian.lapak)
        ).get(report_id)

        if not report:
            return jsonify({"success": False, "message": "Laporan tidak ditemukan"}), 404

        data = {
            "id": report.id,
            "tanggal": report.tanggal.strftime('%d %B %Y'),
            "status": report.status,
            "lokasi": report.lapak.lokasi,
            "keuntungan_owner": report.keuntungan_owner,
            "keuntungan_superowner": report.keuntungan_superowner
        }
        return jsonify({"success": True, "data": data})

    except Exception as e:
        logging.error(f"Error getting SO profit detail: {str(e)}")
        return jsonify({"success": False, "message": "Terjadi kesalahan server"}), 500

@superowner_bp.route('/superowner_withdraw', methods=['POST'])
def superowner_withdraw():
    data = request.json
    superowner_id = data.get('superowner_id')
    
    try:
        balances = SuperOwnerBalance.query.filter_by(super_owner_id=superowner_id).all()
        total_penarikan = sum(b.balance for b in balances)

        if total_penarikan <= 0:
            return jsonify({"success": False, "message": "Tidak ada saldo untuk ditarik."}), 400

        penarikan = RiwayatPenarikanSuperOwner(
            super_owner_id=superowner_id,
            jumlah_penarikan=total_penarikan
        )
        db.session.add(penarikan)
        
        for b in balances:
            b.balance = 0.0
        
        db.session.commit()
        logging.info(f"-> PENARIKAN BERHASIL: SuperOwner #{superowner_id} menarik saldo sebesar {total_penarikan}.")
        return jsonify({"success": True, "message": f"Penarikan saldo sebesar {total_penarikan:,.0f} berhasil dicatat."})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": "Gagal memproses penarikan."}), 500

@superowner_bp.route('/superowner_withdraw_from_owner', methods=['POST'])
def superowner_withdraw_from_owner():
    data = request.json
    superowner_id = data.get('superowner_id')
    owner_id = data.get('owner_id')

    if not superowner_id or not owner_id:
        return jsonify({"success": False, "message": "ID Superowner atau Owner tidak lengkap."}), 400

    try:
        balance_record = SuperOwnerBalance.query.filter_by(
            super_owner_id=superowner_id,
            owner_id=owner_id
        ).first()

        if not balance_record or balance_record.balance <= 0:
            return jsonify({"success": False, "message": "Tidak ada saldo untuk ditarik."}), 400

        jumlah_penarikan = balance_record.balance

        penarikan = RiwayatPenarikanSuperOwner(
            super_owner_id=superowner_id,
            owner_id=owner_id,
            jumlah_penarikan=jumlah_penarikan
        )
        db.session.add(penarikan)

        balance_record.balance = 0.0
        
        db.session.commit()
        
        owner_name = Admin.query.get(owner_id).nama_lengkap
        logging.info(f"-> PENARIKAN (PENANDAAN) BERHASIL: Saldo dari {owner_name} (Rp {jumlah_penarikan}) telah di-nol-kan.")
        return jsonify({"success": True, "message": f"Saldo dari {owner_name} berhasil ditandai sebagai lunas."})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": "Gagal memproses penarikan."}), 500
      
@superowner_bp.route('/get_superowner_profit_reports/<int:superowner_id>', methods=['GET'])
def get_superowner_profit_reports(superowner_id):
    try:
        reports = db.session.query(
            LaporanHarian.id, LaporanHarian.tanggal, Lapak.lokasi,
            Admin.nama_lengkap.label('owner_name'), LaporanHarian.keuntungan_superowner
        ).join(Lapak, LaporanHarian.lapak_id == Lapak.id)\
         .join(Admin, Lapak.user_id == Admin.id)\
         .filter(
            LaporanHarian.status == 'Terkonfirmasi',
            LaporanHarian.keuntungan_superowner > 0
        ).order_by(LaporanHarian.tanggal.desc()).all()

        report_list = [{
            "report_id": r.id, "tanggal": r.tanggal.strftime('%d %B %Y'),
            "sumber": f"Laporan dari {r.lokasi}", "owner": r.owner_name, "profit": r.keuntungan_superowner
        } for r in reports]

        return jsonify({"success": True, "reports": report_list})
    except Exception as e:
        return jsonify({"success": False, "message": "Gagal mengambil laporan profit."}), 500

@superowner_bp.route('/get_superowner_transactions/<int:superowner_id>', methods=['GET'])
def get_superowner_transactions(superowner_id):
    try:
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')

        start_date, end_date = None, None
        if start_date_str:
            start_date = datetime.datetime.strptime(start_date_str, '%Y-%m-%d').date()
        if end_date_str:
            end_date = datetime.datetime.strptime(end_date_str, '%Y-%m-%d').date()

        all_transactions = []

        profit_query = db.session.query(
            LaporanHarian.tanggal,
            Admin.nama_lengkap.label('owner_name'),
            func.sum(LaporanHarian.keuntungan_superowner).label('total_profit')
        ).join(Lapak, LaporanHarian.lapak_id == Lapak.id)\
         .join(Admin, Lapak.owner_id == Admin.id)\
         .filter(
            Admin.super_owner_id == superowner_id,
            LaporanHarian.status == 'Terkonfirmasi',
            LaporanHarian.keuntungan_superowner > 0
        )
        
        if start_date:
            profit_query = profit_query.filter(LaporanHarian.tanggal >= start_date)
        if end_date:
            profit_query = profit_query.filter(LaporanHarian.tanggal <= end_date)
            
        profit_results = profit_query.group_by(LaporanHarian.tanggal, Admin.nama_lengkap).all()

        for p in profit_results:
            all_transactions.append({
                "tanggal": p.tanggal,
                "keterangan": f"Profit dari {p.owner_name}",
                "tipe": "profit",
                "jumlah": p.total_profit
            })

        payout_query = RiwayatPenarikanSuperOwner.query.options(
            joinedload(RiwayatPenarikanSuperOwner.owner)
        ).filter(RiwayatPenarikanSuperOwner.super_owner_id == superowner_id)
        
        if start_date:
            payout_query = payout_query.filter(func.date(RiwayatPenarikanSuperOwner.tanggal_penarikan) >= start_date)
        if end_date:
            payout_query = payout_query.filter(func.date(RiwayatPenarikanSuperOwner.tanggal_penarikan) <= end_date)
            
        payouts = payout_query.all()

        for h in payouts:
            all_transactions.append({
                "tanggal": h.tanggal_penarikan.date(),
                "keterangan": f"Penarikan dari {h.owner.nama_lengkap if h.owner else 'Saldo Global'}",
                "tipe": "penarikan",
                "jumlah": -h.jumlah_penarikan
            })
            
        all_transactions.sort(key=lambda x: x['tanggal'], reverse=True)
        
        tx_list = [
            {**item, "tanggal": item['tanggal'].strftime('%Y-%m-%d')}
            for item in all_transactions
        ]

        return jsonify({"success": True, "transactions": tx_list})
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error getting superowner transactions: {str(e)}")
        return jsonify({"success": False, "message": "Gagal mengambil riwayat transaksi."}), 500

@superowner_bp.route('/get_superowner_owner_reports/<int:superowner_id>', methods=['GET'])
def get_superowner_owner_reports(superowner_id):
    try:
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')

        start_date, end_date = None, None
        if start_date_str:
            start_date = datetime.datetime.strptime(start_date_str, '%Y-%m-%d').date()
        if end_date_str:
            end_date = datetime.datetime.strptime(end_date_str, '%Y-%m-%d').date()

        owners = Admin.query.filter_by(super_owner_id=superowner_id).all()
        owner_reports = []
        
        for owner in owners:
            lapaks = Lapak.query.filter_by(owner_id=owner.id).all()
            lapak_ids = [l.id for l in lapaks]
            lapak_names = [l.lokasi for l in lapaks]

            if not lapak_ids:
                owner_reports.append({
                    "owner_id": owner.id, "owner_name": owner.nama_lengkap, "lapak_names": [],
                    "total_biaya_supplier": 0, "total_keuntungan_owner": 0, "total_keuntungan_superowner": 0
                })
                continue

            query = db.session.query(
                func.sum(LaporanHarian.total_biaya_supplier).label('total_biaya'),
                func.sum(LaporanHarian.keuntungan_owner).label('total_profit_owner'),
                func.sum(LaporanHarian.keuntungan_superowner).label('total_profit_superowner')
            ).filter(
                LaporanHarian.lapak_id.in_(lapak_ids),
                LaporanHarian.status == 'Terkonfirmasi'
            )
            
            if start_date:
                query = query.filter(LaporanHarian.tanggal >= start_date)
            if end_date:
                query = query.filter(LaporanHarian.tanggal <= end_date)

            aggregated_data = query.first()

            owner_reports.append({
                "owner_id": owner.id, "owner_name": owner.nama_lengkap, "lapak_names": lapak_names,
                "total_biaya_supplier": aggregated_data.total_biaya or 0,
                "total_keuntungan_owner": aggregated_data.total_profit_owner or 0,
                "total_keuntungan_superowner": aggregated_data.total_profit_superowner or 0
            })

        return jsonify({"success": True, "reports": owner_reports})

    except Exception as e:
        db.session.rollback()
        logging.error(f"Error getting superowner aggregated reports: {str(e)}")
        return jsonify({"success": False, "message": "Gagal mengambil laporan agregat owner."}), 500

@superowner_bp.route('/get_superowner_owners/<int:superowner_id>', methods=['GET'])
def get_superowner_owners(superowner_id):
    try:
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

@superowner_bp.route('/get_report_details/<int:report_id>')
def get_report_details(report_id):
    try:
        report = LaporanHarian.query.options(
            joinedload(LaporanHarian.lapak).joinedload(Lapak.penanggung_jawab),
            joinedload(LaporanHarian.rincian_produk).joinedload(LaporanHarianProduk.product).joinedload(Product.supplier)
        ).get(report_id)

        if not report:
            return jsonify({"success": False, "message": "Laporan tidak ditemukan"}), 404

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

        data = {
            "id": report.id,
            "tanggal": report.tanggal.strftime('%d %B %Y'),
            "status": report.status,
            "lokasi": report.lapak.lokasi,
            "penanggung_jawab": report.lapak.penanggung_jawab.nama_lengkap,
            "rincian_per_supplier": rincian_per_supplier,
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
                "total_produk_terjual": report.total_produk_terjual,
                "total_pendapatan": report.manual_total_pendapatan
            }
        }
        return jsonify({"success": True, "data": data})

    except Exception as e:
        logging.error(f"Error getting report details: {e}")
        return jsonify({"success": False, "message": "Terjadi kesalahan pada server"}), 500