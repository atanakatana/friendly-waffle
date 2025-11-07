// --- SUPEROWNER FUNCTIONS ---
// GANTI FUNGSI LAMA DENGAN VERSI BARU INI
// (Ganti fungsi lama di baris 2200)
// (Ganti fungsi lama di baris 2200 di index.html)

async function populateSuperownerDashboard() {
  const loadingEl = document.getElementById('superowner-loading');
  const contentEl = document.getElementById('superowner-content');
  const totalSaldoEl = document.getElementById('superowner-total-saldo');
  const profitBulanIniEl = document.getElementById('superowner-profit-bulan-ini');
  const ownerTerprofitEl = document.getElementById('superowner-owner-terprofit');
  const tableBody = document.getElementById('superowner-owner-table-body');

  loadingEl.style.display = 'block';
  contentEl.style.display = 'none';

  try {
    const superownerId = AppState.currentUser.user_info.id;
    const resp = await fetch(`/api/get_superowner_dashboard_data/${superownerId}`);
    const result = await resp.json();
    if (!result.success) throw new Error(result.message);

    // Isi card KPI
    totalSaldoEl.textContent = formatCurrency(result.total_saldo);
    profitBulanIniEl.textContent = formatCurrency(result.kpi.profit_bulan_ini);
    ownerTerprofitEl.textContent = result.kpi.owner_terprofit;

    // Isi tabel rincian
    if (result.rincian_per_owner.length === 0) {
      tableBody.innerHTML = `<tr><td colspan="3" class="text-center text-muted">Belum ada Owner yang terdaftar.</td></tr>`;
    } else {
      tableBody.innerHTML = result.rincian_per_owner.map(owner => `
            <tr>
              <td>${owner.owner_name}</td>
              <td class="text-end fw-bold">${formatCurrency(owner.balance)}</td>
              <td class="text-center">
                <div class="btn-group">
                  <button class="btn btn-sm btn-info" onclick="openProfitDetailPage(${owner.owner_id}, '${owner.owner_name}')">
                    <i class="bi bi-eye-fill"></i> Detail
                  </button>
                  <button class="btn btn-sm btn-success" onclick="openWithdrawModalForOwner(${owner.owner_id}, '${owner.owner_name}', ${owner.balance})" ${owner.balance <= 0 ? 'disabled' : ''}>
                    <i class="bi bi-check-circle-fill"></i> Tandai Lunas
                  </button>
                </div>
              </td>
            </tr>
          `).join('');
    }
    // Tampilkan konten jika sukses
    contentEl.style.display = 'block';
    loadingEl.style.display = 'none'; // Sembunyikan loading HANYA jika sukses

  } catch (e) {
    // Tampilkan error di dalam elemen loading
    loadingEl.innerHTML = `<div class="alert alert-danger">${e.message}</div>`;
    loadingEl.style.display = 'block'; // Pastikan elemen loading terlihat
    contentEl.style.display = 'none';
  }
  // Tidak ada blok 'finally' lagi
}

// FUNGSI BARU 1: Untuk membuka halaman detail
function openProfitDetailPage(ownerId, ownerName) {
  // Simpan data sementara untuk digunakan oleh fungsi berikutnya
  AppState.currentDetailOwner = { id: ownerId, name: ownerName };
  showPage('superowner-profit-detail-page');
}

// FUNGSI BARU 2: Untuk mengisi halaman detail
// (Ganti seluruh fungsi populateSuperownerProfitDetails di index.html)
async function populateSuperownerProfitDetails() {
  const loadingEl = document.getElementById('profit-detail-loading');
  const contentEl = document.getElementById('profit-detail-content');
  const tableBody = document.getElementById('profit-detail-table-body');
  const ownerNameEl = document.getElementById('detail-owner-name');

  const { id, name } = AppState.currentDetailOwner;
  ownerNameEl.textContent = name;

  loadingEl.style.display = 'block';
  contentEl.style.display = 'none';

  try {
    const resp = await fetch(`/api/get_superowner_profit_details/${id}`);
    const result = await resp.json();

    if (!result.success) throw new Error(result.message);

    // PERBAIKAN 1: Ganti colspan jadi 4
    if (result.history.length === 0) {
      tableBody.innerHTML = `<tr><td colspan="4" class="text-center text-muted">Belum ada riwayat profit dari owner ini.</td></tr>`;
    } else {
      // PERBAIKAN 2: Tambahkan tombol dan panggil FUNGSI BARU
      tableBody.innerHTML = result.history.map(item => `
          <tr>
            <td>${item.tanggal}</td>
            <td>${item.sumber}</td>
            <td class="text-end fw-bold text-success">${formatCurrency(item.profit)}</td>
            <td class="text-center">
              <button class="btn btn-sm btn-info" onclick="showSuperOwnerProfitModal(${item.report_id})">
                <i class="bi bi-eye-fill"></i> Detail
              </button>
            </td>
          </tr>
        `).join('');
    }
    contentEl.style.display = 'block';
  } catch (e) {
    contentEl.innerHTML = `<div class="alert alert-danger">${e.message}</div>`;
  } finally {
    loadingEl.style.display = 'none';
  }
}


// (Tambahkan fungsi BARU ini di index.html, di bagian SUPEROWNER FUNCTIONS)

async function showSuperOwnerProfitModal(reportId) {
  const container = document.getElementById("invoice-content");
  container.innerHTML = `<div class="text-center p-5"><div class="spinner-border"></div></div>`;
  modals.reportDetail.show(); // Kita tetap pakai modal yang sama

  try {
    // Panggil API BARU yang kita buat
    const resp = await fetch(`/api/get_superowner_report_profit_detail/${reportId}`);
    const result = await resp.json();
    if (!result.success) throw new Error(result.message);

    const data = result.data;

    // Ini adalah template HTML SEDERHANA (profit-only)
    container.innerHTML = `
      <table>
        <tr class="top">
          <td colspan="2">
            <table>
              <tr>
                <td class="title"><h4>Rincian Profit</h4></td>
                <td style="text-align: right;">
                  ID Laporan: #${data.id}<br>
                  Tanggal: ${data.tanggal}<br>
                  Status: ${data.status}
                </td>
              </tr>
            </table>
          </td>
        </tr>
        <tr class="information">
          <td colspan="2">
            <table>
              <tr><td>Lapak Sumber:<br><strong>${data.lokasi}</strong></td></tr>
            </table>
          </td>
        </tr>
        <tr class="heading">
          <td>Deskripsi Profit</td>
          <td style="text-align: right;">Jumlah</td>
        </tr>
        <tr class="item">
          <td>Profit untuk Owner</td>
          <td style="text-align: right;">${formatCurrency(data.keuntungan_owner)}</td>
        </tr>
        <tr class="item last">
          <td>Profit untuk SuperOwner</td>
          <td style="text-align: right;">${formatCurrency(data.keuntungan_superowner)}</td>
        </tr>
        <tr class="total">
          <td></td>
          <td style="text-align: right; border-top: 2px solid #eee; font-weight: bold;">
             <strong>Total: ${formatCurrency(data.keuntungan_owner + data.keuntungan_superowner)}</strong>
          </td>
        </tr>
      </table>
    `;
  } catch (e) {
    container.innerHTML = `<div class="alert alert-danger">${e.message}</div>`;
  }
}
// (Letakkan ini setelah fungsi populateSuperownerProfitDetails)

// (Ganti fungsi 'openWithdrawModal' LAMA)
function openWithdrawModalForOwner(ownerId, ownerName, balance) {
  document.getElementById('withdraw-owner-id').value = ownerId; // <-- Simpan ID
  document.getElementById('withdraw-owner-name-confirm').textContent = ownerName; // <-- Tampilkan Nama
  document.getElementById('withdraw-amount-confirm').textContent = formatCurrency(balance);
  modals.withdraw.show();
}

// (Ganti fungsi 'handleSuperownerWithdraw' LAMA)
async function handleSuperownerWithdrawForOwner() {
  const superownerId = AppState.currentUser.user_info.id;
  const ownerId = document.getElementById('withdraw-owner-id').value; // <-- Ambil ID

  try {
    const resp = await fetch('/api/superowner_withdraw_from_owner', { // <-- Panggil API baru
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ superowner_id: superownerId, owner_id: ownerId }) // <-- Kirim kedua ID
    });
    const result = await resp.json();
    showToast(result.message, result.success);
    if (result.success) {
      modals.withdraw.hide();
      await populateSuperownerDashboard(); // Refresh dashboard
    }
  } catch (e) {
    showToast('Gagal terhubung ke server.', false);
  }
}

// GANTI FUNGSI LAMA DENGAN VERSI BARU INI
async function populateSuperownerReports() {
  const loadingEl = document.getElementById('superowner-reports-loading');
  const contentEl = document.getElementById('superowner-reports-content');

  loadingEl.style.display = 'block';
  contentEl.style.display = 'none';
  contentEl.innerHTML = ''; // Kosongkan konten lama

  // (Sekitar baris 2319 di index.html)
  try {
    const superownerId = AppState.currentUser.user_info.id;

    // === LOGIKA FILTER BARU ===
    const params = new URLSearchParams();
    const startDate = document.getElementById('so-report-start-date').value;
    const endDate = document.getElementById('so-report-end-date').value;
    if (startDate) params.append('start_date', startDate);
    if (endDate) params.append('end_date', endDate);
    // === AKHIR LOGIKA BARU ===

    // 1. PANGGIL API BARU KITA DENGAN PARAMETER
    const resp = await fetch(`/api/get_superowner_owner_reports/${superownerId}?${params.toString()}`);
    const result = await resp.json();
    if (!result.success) throw new Error(result.message);

    if (result.reports.length === 0) {
      contentEl.innerHTML = `<div class="alert alert-info text-center">Belum ada laporan profit dari owner manapun.</div>`;
    } else {
      // 2. BANGUN TAMPILAN ACCORDION
      contentEl.innerHTML = result.reports.map((r, index) => {
        // Buat daftar lapak (sesuai permintaan Anda)
        const lapakListHtml = r.lapak_names.length === 0
          ? '<li class="list-group-item text-muted">Owner ini belum memiliki lapak.</li>'
          : r.lapak_names.map(name => `<li class="list-group-item">${name}</li>`).join('');

        const isFirstItem = index === 0;

        return `
                <div class="accordion-item">
                  <h2 class="accordion-header" id="heading-owner-${r.owner_id}">
                    <button class="accordion-button ${isFirstItem ? '' : 'collapsed'}" type="button" data-bs-toggle="collapse" data-bs-target="#collapse-owner-${r.owner_id}">
                      <strong>${r.owner_name}</strong>
                    </button>
                  </h2>
                  <div id="collapse-owner-${r.owner_id}" class="accordion-collapse collapse ${isFirstItem ? 'show' : ''}" data-bs-parent="#superowner-reports-content">
                    <div class="accordion-body">
                      <div class="row g-4">
                        <div class="col-md-5">
                          <h6>Daftar Lapak</h6>
                          <ul class="list-group list-group-flush">${lapakListHtml}</ul>
                        </div>
                        <div class="col-md-7">
                          <h6>Ringkasan Keuangan (Terkonfirmasi)</h6>
                          <table class="table table-sm table-bordered">
                            <tbody>
                              <tr>
                                <td>Total Biaya ke Supplier</td>
                                <td class="text-end fw-bold">${formatCurrency(r.total_biaya_supplier)}</td>
                              </tr>
                              <tr>
                                <td>Total Pendapatan Owner</td>
                                <td class="text-end fw-bold text-success">${formatCurrency(r.total_keuntungan_owner)}</td>
                              </tr>
                              <tr>
                                <td>Total Pendapatan Superowner</td>
                                <td class="text-end fw-bold text-primary">${formatCurrency(r.total_keuntungan_superowner)}</td>
                              </tr>
                            </tbody>
                          </table>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              `;
      }).join('');
    }
    // 3. Ubah display menjadi 'block' (bukan 'flex' lagi)
    contentEl.style.display = 'block';
  } catch (e) {
    contentEl.innerHTML = `<div class="alert alert-danger">${e.message}</div>`;
    contentEl.style.display = 'block';
  } finally {
    loadingEl.style.display = 'none';
  }
}

// FUNGSI BARU 4: Untuk mengisi halaman Riwayat Penarikan
// (Ganti fungsi lama di baris 2359)
async function populateSuperownerTransactions() {
  const loadingEl = document.getElementById('so-tx-loading');
  const contentEl = document.getElementById('so-tx-content');
  const tableBody = document.getElementById('so-tx-table-body');

  loadingEl.style.display = 'block';
  contentEl.style.display = 'none';
  tableBody.innerHTML = '';

  // === LOGIKA FILTER BARU ===
  const params = new URLSearchParams();
  const advancedFilterEl = document.getElementById('so-advanced-tx-filter');
  const isAdvanced = advancedFilterEl.classList.contains('show');
  let startDate, endDate;

  if (isAdvanced) {
    startDate = document.getElementById('so-tx-start-date').value;
    endDate = document.getElementById('so-tx-end-date').value;
  } else {
    const dailyDate = document.getElementById('so-tx-daily-date').value;
    startDate = dailyDate;
    endDate = dailyDate;
  }

  if (startDate) params.append('start_date', startDate);
  if (endDate) params.append('end_date', endDate);
  // === AKHIR LOGIKA FILTER ===

  try {
    const superownerId = AppState.currentUser.user_info.id;
    const resp = await fetch(`/api/get_superowner_transactions/${superownerId}?${params.toString()}`);
    const result = await resp.json();

    if (!result.success) throw new Error(result.message);

    if (result.transactions.length === 0) {
      tableBody.innerHTML = `<tr><td colspan="4" class="text-center text-muted">Tidak ada transaksi pada rentang tanggal ini.</td></tr>`;
    } else {
      tableBody.innerHTML = result.transactions.map(tx => {
        const isProfit = tx.tipe === 'profit';
        const badge = isProfit
          ? `<span class="badge bg-success">Profit Masuk</span>`
          : `<span class="badge bg-danger">Penarikan</span>`;
        const amountClass = isProfit ? 'text-success' : 'text-danger';
        const amountPrefix = isProfit ? '+' : ''; // Tanda minus sudah ada dari backend

        return `
              <tr>
                <td>${new Date(tx.tanggal + 'T00:00:00').toLocaleDateString('id-ID')}</td>
                <td>${tx.keterangan}</td>
                <td>${badge}</td>
                <td class="text-end fw-bold ${amountClass}">${amountPrefix}${formatCurrency(tx.jumlah)}</td>
              </tr>
            `;
      }).join('');
    }
    contentEl.style.display = 'block';
  } catch (e) {
    loadingEl.innerHTML = `<div class="alert alert-danger">${e.message}</div>`;
  } finally {
    loadingEl.style.display = 'none';
  }
}

// (Letakkan ini di dalam SUPEROWNER FUNCTIONS)

// FUNGSI BARU 1: Untuk mengisi halaman Manajemen Owner
async function populateSuperownerManageOwners() {
  const tableBody = document.getElementById('superowner-owners-table-body');
  tableBody.innerHTML = `<tr><td colspan="6" class="text-center"><div class="spinner-border spinner-border-sm"></div></td></tr>`;
  try {
    const superownerId = AppState.currentUser.user_info.id;
    const resp = await fetch(`/api/get_superowner_owners/${superownerId}`);
    const result = await resp.json();
    if (!result.success) throw new Error(result.message);
    if (result.owners.length === 0) {
      tableBody.innerHTML = `<tr><td colspan="6" class="text-center text-muted">Belum ada Owner yang terdaftar.</td></tr>`;
    } else {
      tableBody.innerHTML = result.owners.map(o => `
                      <tr>
                          <td>${o.nama_lengkap}</td><td>${o.username}</td><td>${o.email}</td><td>${o.nomor_kontak}</td>
                          <td class="password-cell"><span class="password-text me-2" data-password="${o.password}">••••••••</span><i class="bi bi-eye-slash" style="cursor: pointer;" onclick="toggleTablePasswordVisibility(this)"></i></td>
                          <td><div class="btn-group">
                              <button class="btn btn-sm btn-warning" onclick='openSuperownerEditOwnerModal(${o.id})'><i class="bi bi-pencil-fill"></i></button>
                              <button class="btn btn-sm btn-danger" onclick='handleSuperownerDeleteOwner(${o.id})'><i class="bi bi-trash-fill"></i></button>
                          </div></td>
                      </tr>`).join('');
    }
  } catch (e) {
    tableBody.innerHTML = `<tr><td colspan="6" class="text-center text-danger">${e.message}</td></tr>`;
  }
}

// GANTI FUNGSI LAMA DENGAN VERSI BARU INI
async function openSuperownerEditOwnerModal(id = null) {
  const form = document.getElementById("superowner-edit-owner-form");
  form.reset();
  const isEdit = id !== null;
  document.getElementById("superowner-owner-modal-title").textContent = isEdit ? "Edit Owner" : "Tambah Owner Baru";
  document.getElementById("superowner-edit-owner-id").value = id || "";

  if (isEdit) {
    // Logika untuk Mode EDIT
    const superownerId = AppState.currentUser.user_info.id;
    const resp = await fetch(`/api/get_superowner_owners/${superownerId}`);
    const result = await resp.json();
    const ownerData = result.owners.find(o => o.id === id);
    if (ownerData) {
      document.getElementById("superowner-edit-owner-nama").value = ownerData.nama_lengkap;
      document.getElementById("superowner-edit-owner-username").value = ownerData.username;
      document.getElementById("superowner-edit-owner-email").value = ownerData.email;
      document.getElementById("superowner-edit-owner-kontak").value = ownerData.nomor_kontak;
    }
  }
  // Untuk mode TAMBAH BARU, kita tidak melakukan apa-apa,
  // sehingga form NIK akan kosong dan siap diisi manual.

  modals.superownerEditOwner.show();
}

// FUNGSI BARU 3: Untuk submit form Owner
async function handleSuperownerOwnerFormSubmit(e) {
  e.preventDefault();
  const form = e.target;
  const id = form.elements["superowner-edit-owner-id"].value;
  const isEdit = id !== "";
  const url = isEdit ? `/api/update_admin/${id}` : `/api/add_admin`;
  const method = isEdit ? "PUT" : "POST";
  const password = form.elements["superowner-edit-owner-password"].value;
  const passwordConfirm = form.elements["superowner-edit-owner-password-confirm"].value;
  if (password && password !== passwordConfirm) return showToast("Password dan konfirmasi tidak cocok.", false);

  const payload = {
    nama_lengkap: form.elements["superowner-edit-owner-nama"].value,
    username: form.elements["superowner-edit-owner-username"].value,
    email: form.elements["superowner-edit-owner-email"].value,
    nomor_kontak: form.elements["superowner-edit-owner-kontak"].value,
    password, password_confirm: passwordConfirm,
    super_owner_id: AppState.currentUser.user_info.id // Kirim ID Superowner
  };

  const resp = await fetch(url, { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
  const result = await resp.json();
  showToast(result.message, resp.ok);
  if (resp.ok) {
    modals.superownerEditOwner.hide();
    await populateSuperownerManageOwners();
  }
}

// FUNGSI BARU 4: Untuk menghapus Owner
async function handleSuperownerDeleteOwner(id) {
  if (!confirm("Yakin ingin menghapus Owner ini?")) return;
  const resp = await fetch(`/api/delete_admin/${id}`, { method: 'DELETE' });
  const result = await resp.json();
  showToast(result.message, resp.ok);
  if (resp.ok) await populateSuperownerManageOwners();
}