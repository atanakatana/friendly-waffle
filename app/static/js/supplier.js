// --- SUPPLIER FUNCTIONS ---
// GANTI FUNGSI LAMA DENGAN VERSI BARU INI
async function populateSupplierDashboard() {
  try {
    const supplierId = AppState.currentUser.user_info.supplier_id;
    const resp = await fetch(`/api/get_data_supplier/${supplierId}`);
    if (!resp.ok) throw new Error("Gagal mengambil data dashboard supplier");
    const result = await resp.json();
    if (result.success) {
      document.getElementById("supplier-total-tagihan").textContent = formatCurrency(result.summary.total_tagihan);
      document.getElementById("supplier-penjualan-bulan-ini").textContent = formatCurrency(result.summary.penjualan_bulan_ini);
    } else { throw new Error(result.message); }

    // PERUBAHAN DI SINI: Panggil fungsi untuk memuat notifikasi
    await populateNotifications();

  } catch (error) {
    showToast(error.message || "Gagal memuat data dashboard.", false);
  }
}
async function populateSupplierHistoryPage() {
  const loadingEl = document.getElementById('supplier-history-loading'),
    contentEl = document.getElementById('supplier-history-content'),
    salesBody = document.getElementById('supplier-sales-history-body'),
    paymentsBody = document.getElementById('supplier-payment-history-body'),
    lapakSelect = document.getElementById('supplier-history-lapak-filter');

  loadingEl.style.display = 'block';
  contentEl.style.display = 'none';

  // Ambil semua nilai dari filter
  const startDate = document.getElementById('supplier-history-start-date').value;
  const endDate = document.getElementById('supplier-history-end-date').value;
  const lapakId = lapakSelect.value;

  const params = new URLSearchParams();
  if (startDate) params.append('start_date', startDate);
  if (endDate) params.append('end_date', endDate);
  if (lapakId) params.append('lapak_id', lapakId); // Tambahkan lapak_id ke parameter
  const queryString = params.toString();

  try {
    const apiUrl = `/api/get_supplier_history/${AppState.currentUser.user_info.supplier_id}?${queryString}`;
    const resp = await fetch(apiUrl);
    const result = await resp.json();

    if (!result.success) throw new Error(result.message);

    // --- PERUBAHAN DI SINI: Mengisi dropdown lapak saat pertama kali dijalankan ---
    if (lapakSelect.options.length <= 1) { // Cek agar tidak diisi berulang kali
      if (result.lapaks) {
        result.lapaks.forEach(l => {
          lapakSelect.innerHTML += `<option value="${l.id}">${l.lokasi}</option>`;
        });
      }
    }

    // Bagian untuk mengisi tabel pembayaran (tidak berubah)
    if (result.payments.length === 0) {
      paymentsBody.innerHTML = `<tr><td colspan="3" class="text-center text-muted">Belum ada pembayaran.</td></tr>`;
    } else {
      paymentsBody.innerHTML = result.payments.map(p => `
                    <tr>
                        <td>${new Date(p.tanggal + 'T00:00:00').toLocaleDateString('id-ID')}</td>
                        <td>${formatCurrency(p.jumlah)}</td>
                        <td><span class="badge bg-info">${p.metode}</span></td>
                    </tr>`).join('');
    }

    // Bagian untuk mengisi tabel penjualan (tidak berubah)
    if (result.sales.length === 0) {
      salesBody.innerHTML = `<tr><td colspan="4" class="text-center text-muted">Belum ada penjualan.</td></tr>`;
    } else {
      salesBody.innerHTML = result.sales.map(s => `
                    <tr>
                        <td>${new Date(s.tanggal + 'T00:00:00').toLocaleDateString('id-ID')}</td>
                        <td>${s.lokasi}</td>
                        <td>${s.nama_produk}</td>
                        <td>${s.terjual} Pcs</td>
                    </tr>`).join('');
    }

    loadingEl.style.display = 'none';
    contentEl.style.display = 'block';
  } catch (e) {
    loadingEl.innerHTML = `<div class="alert alert-danger">${e.message}</div>`;
  }
}

// FUNGSI BARU UNTUK MENGISI NOTIFIKASI
// GANTI FUNGSI LAMA DENGAN VERSI BARU INI
async function populateNotifications() {
  const container = document.getElementById("notification-list-container");
  container.innerHTML = `<div id="notification-loading" class="list-group-item text-center p-4"><div class="spinner-border spinner-border-sm"></div><p class="mb-0 mt-2 text-muted">Memuat notifikasi...</p></div>`;

  try {
    const supplierId = AppState.currentUser.user_info.supplier_id;
    const resp = await fetch(`/api/get_supplier_notifications/${supplierId}`);
    const result = await resp.json();
    if (!result.success) throw new Error(result.message);

    if (result.notifications.length === 0) {
      container.innerHTML = `<div class="list-group-item text-center text-muted p-4">Tidak ada notifikasi stok habis saat ini.</div>`;
      updateNotificationBadge(); // Pastikan badge kosong
      return;
    }

    container.innerHTML = result.notifications.map(n => {
      const isNew = n.status === 'baru' ? 'list-group-item-warning' : '';
      // PERUBAHAN DI SINI: Tombol sekarang memanggil fungsi aksi
      const readButtonDisabled = n.status === 'dibaca' ? 'disabled' : '';
      return `
                    <div class="list-group-item d-flex justify-content-between align-items-center ${isNew}" id="notif-${n.id}">
                        <div>
                            Produk <strong>${n.product_name}</strong> habis di <strong>${n.lapak_name}</strong>.
                            <small class="d-block text-muted">${new Date(n.time).toLocaleString('id-ID')}</small>
                        </div>
                        <div class="btn-group">
                            <button class="btn btn-sm btn-outline-secondary" onclick="markNotificationAsRead(${n.id}, this)" ${readButtonDisabled}>
                                <i class="bi bi-check2"></i> Baca
                            </button>
                            <button class="btn btn-sm btn-outline-danger" onclick="archiveNotification(${n.id})">
                                <i class="bi bi-archive-fill"></i> Arsip
                            </button>
                        </div>
                    </div>
                `;
    }).join('');

    updateNotificationBadge(); // Panggil untuk pertama kali
  } catch (e) {
    container.innerHTML = `<div class="list-group-item text-center text-danger p-4">Gagal memuat notifikasi: ${e.message}</div>`;
  }
}

// (Letakkan ini setelah fungsi populateNotifications)

// FUNGSI BARU 1: Untuk mengubah status di backend
async function updateNotificationStatus(id, status) {
  try {
    const resp = await fetch(`/api/update_notification_status/${id}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: status })
    });
    return await resp.json();
  } catch (e) {
    return { success: false, message: 'Gagal terhubung ke server.' };
  }
}

// FUNGSI BARU 2: Aksi saat tombol "Baca" diklik
async function markNotificationAsRead(id, buttonElement) {
  const result = await updateNotificationStatus(id, 'dibaca');
  if (result.success) {
    const notifItem = document.getElementById(`notif-${id}`);
    notifItem.classList.remove('list-group-item-warning');
    buttonElement.disabled = true;
    updateNotificationBadge();
  }
  showToast(result.message, result.success);
}

// FUNGSI BARU 3: Aksi saat tombol "Arsip" diklik
async function archiveNotification(id) {
  if (!confirm("Arsipkan notifikasi ini? Notifikasi akan hilang dari daftar.")) return;
  const result = await updateNotificationStatus(id, 'diarsipkan');
  if (result.success) {
    document.getElementById(`notif-${id}`).remove();
    updateNotificationBadge();
  }
  showToast(result.message, result.success);
}

// FUNGSI BARU 4: Untuk menghitung ulang badge notifikasi
function updateNotificationBadge() {
  const badge = document.getElementById("notification-badge");
  const newNotificationCount = document.querySelectorAll('.list-group-item-warning').length;
  if (newNotificationCount > 0) {
    badge.textContent = newNotificationCount;
    badge.style.display = 'block';
  } else {
    badge.style.display = 'none';
  }
}

// (Letakkan ini setelah fungsi updateNotificationBadge)

// FUNGSI BARU 1: Untuk mengisi halaman arsip
async function populateArchivedNotifications() {
  const container = document.getElementById("archived-notification-list-container");
  container.innerHTML = `<div class="list-group-item text-center p-4"><div class="spinner-border spinner-border-sm"></div></div>`;

  try {
    const supplierId = AppState.currentUser.user_info.supplier_id;
    const resp = await fetch(`/api/get_archived_notifications/${supplierId}`);
    const result = await resp.json();

    if (!result.success) throw new Error(result.message);

    if (result.notifications.length === 0) {
      container.innerHTML = `<div class="list-group-item text-center text-muted p-4">Arsip notifikasi kosong.</div>`;
      return;
    }

    container.innerHTML = result.notifications.map(n => `
            <div class="list-group-item d-flex justify-content-between align-items-center" id="archived-notif-${n.id}">
                <div>
                    Produk <strong>${n.product_name}</strong> habis di <strong>${n.lapak_name}</strong>.
                    <small class="d-block text-muted">Diarsipkan pada ${new Date(n.time).toLocaleString('id-ID')}</small>
                </div>
                <button class="btn btn-sm btn-outline-primary" onclick="unarchiveNotification(${n.id})">
                    <i class="bi bi-box-arrow-up"></i> Pulihkan
                </button>
            </div>
          `).join('');

  } catch (e) {
    container.innerHTML = `<div class="list-group-item text-center text-danger p-4">Gagal memuat arsip: ${e.message}</div>`;
  }
}

// FUNGSI BARU 2: Aksi saat tombol "Pulihkan" diklik
async function unarchiveNotification(id) {
  const result = await updateNotificationStatus(id, 'baru'); // Kembalikan statusnya ke 'baru'
  if (result.success) {
    showPage('supplier-dashboard'); // Kembali ke dashboard untuk melihat notifikasi yang dipulihkan
  }
  showToast(result.message, result.success);
}