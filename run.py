from app import create_app, db
# mengimpor semua model agar bisa ditemukan saat pembuatan tabel
from app.models import (
  Admin, SuperOwner, Supplier, Lapak, Product, StokHarian, LaporanHarian, LaporanHarianProduk, SupplierBalance, SuperOwnerBalance, PembayaranSupplier, Notifikasi, RiwayatPenarikanSuperOwner, product_lapak_association, lapak_anggota_association
)
import logging
app = create_app()
logging.basicConfig(level=logging.INFO)

# PERINTAH CLI UNTUK INISIALISASI DAN SEEDING DATABASE
@app.cli.command("init-db")
def init_db_command():
    db.create_all()
    print("Database telah diinisialisasi.")
    
@app.cli.command("seed-db")
def seed_db_command():
    """Menghapus database dan membuat data seed yang lengkap."""
    db.drop_all()
    db.create_all()
    print("Database dibersihkan dan struktur baru dibuat...")

    try:
        # 1. Buat SuperOwner
        super_owner = SuperOwner(username="cinda", nama_lengkap="Pemilik UMKM Cinda")
        super_owner.set_password("cinda")
        db.session.add(super_owner)
        db.session.flush()  # Dapatkan ID super_owner
        print(f"SuperOwner '{super_owner.username}' dibuat (ID: {super_owner.id}).")

        # 2. Data untuk 3 Owner
        owner_data = [
            {"nama": "Ata", "user": "ata", "email": "ata@owner.com"},
            {"nama": "Rio", "user": "rio", "email": "rio@owner.com"},
            {"nama": "Nur", "user": "nur", "email": "nur@owner.com"},
        ]
        
        owner_objects = [] # Simpan objek owner untuk loop berikutnya

        for data in owner_data:
            owner = Admin(
                nama_lengkap=data["nama"],
                username=data["user"],
                email=data["email"],
                super_owner_id=super_owner.id # Tautkan ke SuperOwner
            )
            owner.set_password(data["user"])
            db.session.add(owner)
            db.session.flush() # Dapatkan ID owner
            
            # Buat SuperOwnerBalance untuk owner ini
            so_balance = SuperOwnerBalance(
                super_owner_id=super_owner.id,
                owner_id=owner.id,
                balance=0.0
            )
            db.session.add(so_balance)
            owner_objects.append(owner)
            print(f"  > Owner '{data['user']}' dibuat (ID: {owner.id}).")

        # 3. Buat Admin, Lapak, dan Supplier untuk SETIAP Owner
        for owner in owner_objects:
            print(f"\nMembuat data untuk Owner: {owner.username}...")
            
            # 3a. Buat 3 Admin + 3 Lapak untuk owner ini
            admin_data = [
                {"nama": f"Andi ({owner.username})", "user": f"andi_{owner.username}", "email": f"andi@{owner.username}.com", "lapak": f"Lapak Kopo ({owner.username})"},
                {"nama": f"Budi ({owner.username})", "user": f"budi_{owner.username}", "email": f"budi@{owner.username}.com", "lapak": f"Lapak Regol ({owner.username})"},
                {"nama": f"Caca ({owner.username})", "user": f"caca_{owner.username}", "email": f"caca@{owner.username}.com", "lapak": f"Lapak Sarijadi ({owner.username})"},
            ]
            
            for data in admin_data:
                # Buat Admin
                admin = Admin(
                    nama_lengkap=data["nama"],
                    username=data["user"],
                    email=data["email"],
                    created_by_owner_id=owner.id # Tautkan ke Owner-nya
                )
                admin.set_password(data["user"])
                db.session.add(admin)
                db.session.flush() # Dapatkan ID admin
                
                # Buat 1 Lapak untuk admin ini
                lapak = Lapak(
                    lokasi=data["lapak"],
                    user_id=admin.id, # Admin ini adalah Penanggung Jawab
                    owner_id=owner.id # Tautkan ke Owner-nya
                )
                db.session.add(lapak)
                print(f"    > Admin '{data['user']}' dan Lapak '{data['lapak']}' dibuat.")
                
            # 3b. Buat 2 Supplier untuk owner ini
            supplier_data = [
                {"nama": f"Supplier A ({owner.username})", "user": f"supp_a_{owner.username}", "reg": f"REGA-{owner.id:03d}", "metode": "BCA", "rek": "123456789"},
                {"nama": f"Supplier B ({owner.username})", "user": f"supp_b_{owner.username}", "reg": f"REGB-{owner.id:03d}", "metode": "DANA", "rek": "08123456789"},
            ]
            
            for data in supplier_data:
                supplier = Supplier(
                    nama_supplier=data["nama"],
                    username=data["user"],
                    nomor_register=data["reg"],
                    metode_pembayaran=data["metode"],
                    nomor_rekening=data["rek"],
                    owner_id=owner.id # Tautkan ke Owner-nya
                )
                supplier.set_password(data["user"])
                # Buat SupplierBalance untuk supplier ini
                supplier.balance = SupplierBalance(balance=0.0) 
                db.session.add(supplier)
                print(f"    > Supplier '{data['user']}' dibuat.")

        # 4. Commit semua perubahan ke database
        db.session.commit()
        print("\nSemua data seed berhasil dibuat.")
        print("Database siap digunakan.")
        print("\nAkun yang tersedia:")
        print("  SuperOwner: cinda / cinda")
        print("  Owners: ata/ata, rio/rio, nur/nur")
        print("  Admins (Contoh): andi_ata/andi_ata, budi_rio/budi_rio, caca_nur/caca_nur")
        print("  Suppliers (Contoh): supp_a_ata/supp_a_ata, supp_b_rio/supp_b_rio")

    except Exception as e:
        db.session.rollback()
        print(f"\nTERJADI ERROR SAAT SEEDING DATABASE: {e}")
        print("Melakukan rollback...")
    finally:
        db.session.close()
        
if __name__ == '__main__':
    app.run(debug=True, port=5001)