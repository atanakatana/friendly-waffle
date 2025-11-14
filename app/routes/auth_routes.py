from flask import (Blueprint, request, jsonify, render_template, redirect, url_for)
from app.models import Admin, Supplier, SuperOwner, Lapak
from app import db

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login')
def login_page():
    return render_template('login.html')

@auth_bp.route('/login', methods=['POST'])
def handle_login():
    data = request.json
    username = data.get('username', '').lower()
    password = data.get('password')
    
    admin = Admin.query.filter(db.func.lower(Admin.username) == username).first()
    if admin and admin.check_password(password):
        if admin.super_owner_id:
            return jsonify({"success": True, "role": "owner", "user_info": {"nama_lengkap": admin.nama_lengkap, "id": admin.id}})
        else:
            lapak_info = Lapak.query.filter_by(user_id=admin.id).first()
            if not lapak_info:
                lapak_info = Lapak.query.filter(Lapak.anggota.any(id=admin.id)).first()
            
            return jsonify({"success": True, "role": "lapak", "user_info": {"nama_lengkap": admin.nama_lengkap, "lapak_id": lapak_info.id if lapak_info else None, "id": admin.id}})
          
    supplier = Supplier.query.filter(db.func.lower(Supplier.username) == username).first()
    if supplier and supplier.check_password(password):
        return jsonify({"success": True, "role": "supplier", "user_info": {"nama_supplier": supplier.nama_supplier,"supplier_id": supplier.id}})
      
    superowner = SuperOwner.query.filter(db.func.lower(SuperOwner.username) == username).first()
    if superowner and superowner.check_password(password):
        return jsonify({"success": True, "role": "superowner", "user_info": {"username": superowner.username, "id": superowner.id}})
    return jsonify({"success": False, "message": "Username atau password salah"}), 401
  
