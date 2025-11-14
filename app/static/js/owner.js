function changeReportDate(dayDelta) {
  const dateEl = document.getElementById('manage-reports-daily-date');
  const newDate = new Date(dateEl.value);
  newDate.setDate(newDate.getDate() + dayDelta);
  dateEl.value = newDate.toISOString().split('T')[0];
  // Otomatis tutup filter canggih & refresh
  bootstrap.Collapse.getOrCreateInstance('#advanced-reports-filter').hide();
  populateManageReportsPage();
}

function changePaymentDate(dayDelta) {
  const dateEl = document.getElementById('payment-history-daily-date');
  const newDate = new Date(dateEl.value);
  newDate.setDate(newDate.getDate() + dayDelta);
  dateEl.value = newDate.toISOString().split('T')[0];
  // Otomatis tutup filter canggih & refresh
  bootstrap.Collapse.getOrCreateInstance('#advanced-payment-filter').hide();
  populatePaymentHistory();
}

async function populateChartPage() {
  const monthSelect = document.getElementById('chart-month-select');
  const yearSelect = document.getElementById('chart-year-select');
  const currentMonth = new Date().getMonth() + 1;
  const currentYear = new Date().getFullYear();

  // Set bulan & tahun saat ini sebagai default
  monthSelect.value = currentMonth;

  // Isi pilihan tahun dari 2023 hingga tahun ini
  yearSelect.innerHTML = '';
  for (let y = currentYear; y >= 2023; y--) {
    yearSelect.innerHTML += `<option value="${y}">${y}</option>`;
  }
  yearSelect.value = currentYear;

  // Langsung panggil fungsi untuk menggambar grafik dengan filter default
  await fetchAndDrawCharts();
}

async function fetchAndDrawCharts() {
  const loadingEl = document.getElementById('chart-loading');
  const contentEl = document.getElementById('chart-content');
  loadingEl.style.display = 'block';
  contentEl.style.display = 'none';

  const month = document.getElementById('chart-month-select').value;
  const year = document.getElementById('chart-year-select').value;

  try {
    const resp = await fetch(`/api/get_chart_data?month=${month}&year=${year}`);
    const result = await resp.json();
    if (!result.success) throw new Error(result.message);

    const chartOptions = {
      responsive: true,
      scales: {
        y: {
          beginAtZero: true,
          ticks: {
            callback: function (value) { return formatCurrency(value); }
          }
        }
      },
      plugins: {
        tooltip: {
          callbacks: {
            label: function (context) {
              return context.dataset.label + ': ' + formatCurrency(context.raw);
            }
          }
        }
      }
    };

    // Hancurkan grafik lama sebelum menggambar yang baru
    if (pendapatanChartInstance) pendapatanChartInstance.destroy();
    if (biayaChartInstance) biayaChartInstance.destroy();

    // Gambar Grafik Pendapatan
    const ctxPendapatan = document.getElementById('pendapatanChart').getContext('2d');
    pendapatanChartInstance = new Chart(ctxPendapatan, {
      type: 'line',
      data: {
        labels: result.labels,
        datasets: [{
          label: 'Pendapatan',
          data: result.pendapatanData,
          borderColor: 'rgba(25, 135, 84, 1)',
          backgroundColor: 'rgba(25, 135, 84, 0.2)',
          fill: true,
          tension: 0.1
        }]
      },
      options: chartOptions
    });

    // Gambar Grafik Biaya
    const ctxBiaya = document.getElementById('biayaChart').getContext('2d');
    biayaChartInstance = new Chart(ctxBiaya, {
      type: 'line',
      data: {
        labels: result.labels,
        datasets: [{
          label: 'Biaya Supplier',
          data: result.biayaData,
          borderColor: 'rgba(220, 53, 69, 1)',
          backgroundColor: 'rgba(220, 53, 69, 0.2)',
          fill: true,
          tension: 0.1
        }]
      },
      options: chartOptions
    });

    contentEl.style.display = 'block';
  } catch (e) {
    showToast('Gagal memuat data grafik: ' + e.message, false);
  } finally {
    loadingEl.style.display = 'none';
  }
}

async function populateOwnerSupplierHistoryPage() {
  // Fungsi ini mengisi dropdown supplier saat halaman pertama kali dibuka
  const selectEl = document.getElementById('owner-supplier-select');
  // PERBAIKAN: Pastikan placeholder memiliki value=""
  selectEl.innerHTML = '<option selected value="">-- Pilih Supplier --</option>';

  // Kita gunakan data supplier dari AppState yang sudah ada
  if (AppState.ownerData && AppState.ownerData.supplier_data) {
    AppState.ownerData.supplier_data.forEach(s => {
      selectEl.innerHTML += `<option value="${s.id}">${s.nama_supplier}</option>`;
    });
  }
  // Sembunyikan konten & loading di awal
  document.getElementById('owner-supplier-history-content').style.display = 'none';
  document.getElementById('owner-supplier-history-loading').style.display = 'none';
}

async function fetchAndDisplayOwnerSupplierHistory() {
  const supplierId = document.getElementById('owner-supplier-select').value;
  // Jika belum ada supplier yang dipilih, sembunyikan konten dan jangan lakukan apa-apa
  if (!supplierId) {
    document.getElementById('owner-supplier-history-content').style.display = 'none';
    return;
  }

  const loadingEl = document.getElementById('owner-supplier-history-loading'),
    contentEl = document.getElementById('owner-supplier-history-content'),
    salesBody = document.getElementById('owner-supplier-sales-body'),
    paymentsBody = document.getElementById('owner-supplier-payment-body');

  loadingEl.style.display = 'block';
  contentEl.style.display = 'none';

  // Mengambil nilai tanggal dari input
  const startDate = document.getElementById('owner-history-start-date').value;
  const endDate = document.getElementById('owner-history-end-date').value;

  // Membangun query string
  const params = new URLSearchParams();
  if (startDate) params.append('start_date', startDate);
  if (endDate) params.append('end_date', endDate);
  const queryString = params.toString();

  try {
    const apiUrl = `/api/get_owner_supplier_history/${supplierId}?${queryString}`;
    const resp = await fetch(apiUrl);
    const result = await resp.json();
    if (!result.success) throw new Error(result.message);

    paymentsBody.innerHTML = result.payments.length === 0
      ? `<tr><td colspan="3" class="text-center text-muted">Tidak ada pembayaran.</td></tr>`
      : result.payments.map(p => `<tr><td>${new Date(p.tanggal + 'T00:00:00').toLocaleDateString('id-ID')}</td><td>${formatCurrency(p.jumlah)}</td><td><span class="badge bg-info">${p.metode}</span></td></tr>`).join('');

    salesBody.innerHTML = result.sales.length === 0
      ? `<tr><td colspan="5" class="text-center text-muted">Tidak ada penjualan.</td></tr>`
      : result.sales.map(s => `<tr><td>${new Date(s.tanggal + 'T00:00:00').toLocaleDateString('id-ID')}</td><td>${s.lokasi}</td><td>${s.nama_produk}</td><td>${s.terjual} Pcs</td><td class="text-end">${formatCurrency(s.total_harga_beli)}</td></tr>`).join('');

    loadingEl.style.display = 'none';
    contentEl.style.display = 'block';
  } catch (e) {
    loadingEl.innerHTML = `<div class="alert alert-danger">${e.message}</div>`;
  }
}

async function populateOwnerDashboard() {
  try {
    // PERBAIKAN DI SINI: Kirim ID Owner yang sedang login
    const ownerId = AppState.currentUser.user_info.id;
    const dataResp = await fetch(`/api/get_data_owner/${ownerId}`);

    if (!dataResp.ok) throw new Error("Gagal mengambil data owner");
    AppState.ownerData = await dataResp.json();

    // (Sisa dari fungsi ini tetap sama, tidak perlu diubah)
    document.getElementById("owner-pendapatan-card").textContent = formatCurrency(AppState.ownerData.summary.pendapatan_bulan_ini);
    document.getElementById("owner-biaya-card").textContent = formatCurrency(AppState.ownerData.summary.biaya_bulan_ini);
    document.getElementById("owner-profit-card").textContent = formatCurrency(AppState.ownerData.summary.profit_owner_bulan_ini);
    document.getElementById("owner-superowner-profit-card").textContent = formatCurrency(AppState.ownerData.summary.profit_superowner_bulan_ini);

    await populateOwnerDataPages();
  } catch (error) {
    showToast("Gagal memuat data owner.", false);
  }
}
async function populateOwnerDataPages() {
  const { admin_data, lapak_data, supplier_data } = AppState.ownerData;
  document.getElementById("admin-table-body").innerHTML = admin_data
    .map(
      (u) =>
        `<tr><td>${u.nama_lengkap}</td><td>${u.username}</td><td>${u.email}</td><td>${u.nomor_kontak}</td><td class="password-cell"><span class="password-text me-2" data-password="${u.password}">••••••••</span><i class="bi bi-eye-slash" style="cursor: pointer;" onclick="toggleTablePasswordVisibility(this)"></i></td><td><div class="btn-group"><button class="btn btn-sm btn-warning btn-action" onclick='openEditModal("admin", ${u.id})'><i class="bi bi-pencil-fill"></i></button><button class="btn btn-sm btn-danger btn-action" onclick='handleDelete("admin", ${u.id})'><i class="bi bi-trash-fill"></i></button></div></td></tr>`
    )
    .join("");
  document.getElementById("lapak-table-body").innerHTML = lapak_data
    .map(
      (l) =>
        `<tr><td>${l.lokasi}</td><td>${l.penanggung_jawab}</td><td>${l.anggota
          .map(
            (a) =>
              `<span class="badge bg-secondary me-1">${a.nama}</span>`
          )
          .join("") || "-"
        }</td><td><div class="btn-group"><button class="btn btn-sm btn-warning btn-action" onclick='openEditModal("lapak", ${l.id
        })'><i class="bi bi-pencil-fill"></i></button><button class="btn btn-sm btn-danger btn-action" onclick='handleDelete("lapak", ${l.id
        })'><i class="bi bi-trash-fill"></i></button></div></td></tr>`
    )
    .join("");
  document.getElementById("supplier-table-body").innerHTML = supplier_data
    .map(
      (s) =>
        `<tr><td>${s.nama_supplier}</td><td>${s.username || "-"
        }</td><td>${s.kontak}</td><td>${s.nomor_register || "-"
        }</td><td class="password-cell"><span class="password-text me-2" data-password="${s.password
        }">••••••••</span><i class="bi bi-eye-slash" style="cursor: pointer;" onclick="toggleTablePasswordVisibility(this)"></i></td><td><div class="btn-group"><button class="btn btn-sm btn-warning btn-action" onclick='openEditModal("supplier", ${s.id
        })'><i class="bi bi-pencil-fill"></i></button><button class="btn btn-sm btn-danger btn-action" onclick='handleDelete("supplier", ${s.id
        })'><i class="bi bi-trash-fill"></i></button></div></td></tr>`
    )
    .join("");
}
async function showReportDetails(reportId) {
  const container = document.getElementById("invoice-content");
  container.innerHTML = `<div class="text-center p-5"><div class="spinner-border"></div></div>`;
  modals.reportDetail.show();
  try {
    const resp = await fetch(`/api/get_report_details/${reportId}`);
    const result = await resp.json();
    if (!result.success) throw new Error(result.message);

    const data = result.data;

    let rincianHtml = '';
    const suppliers = Object.keys(data.rincian_per_supplier);

    if (suppliers.length === 0) {
      rincianHtml = '<p class="text-center text-muted">Tidak ada rincian produk untuk laporan ini.</p>';
    } else {
      suppliers.forEach(supplierName => {
        const products = data.rincian_per_supplier[supplierName];
        let supplierSubtotal = 0;

        // Membuat tabel untuk setiap supplier
        rincianHtml += `
                      <h5 class="mt-4">${supplierName}</h5>
                      <table class="table table-sm table-bordered">
                          <thead class="table-light">
                              <tr class="heading">
                                  <td>No.</td>
                                  <td>Produk</td>
                                  <td class="text-center">Stok Awal</td>
                                  <td class="text-center">Stok Akhir</td>
                                  <td class="text-center">Terjual</td>
                                  <td class="text-end">Subtotal</td>
                              </tr>
                          </thead>
                          <tbody>
                  `;

        // Mengisi baris produk untuk supplier ini
        products.forEach((p, index) => {
          supplierSubtotal += p.total_pendapatan;
          rincianHtml += `
                          <tr class="item">
                              <td>${index + 1}</td>
                              <td>${p.nama_produk}</td>
                              <td class="text-center">${p.stok_awal}</td>
                              <td class="text-center">${p.stok_akhir}</td>
                              <td class="text-center">${p.terjual}</td>
                              <td class="text-end">${formatCurrency(p.total_pendapatan)}</td>
                          </tr>
                      `;
        });

        // Menambahkan baris subtotal untuk supplier ini
        rincianHtml += `
                          <tr class="total">
                              <td colspan="5" class="text-end fw-bold">Subtotal ${supplierName}</td>
                              <td class="text-end fw-bold">${formatCurrency(supplierSubtotal)}</td>
                          </tr>
                          </tbody>
                      </table>
                  `;
      });
    }
    const compareHtml = `
              <tr><td>Terjual (Cash)</td><td class="text-end">${formatCurrency(data.rekap_otomatis.terjual_cash)}</td><td class="text-end">${formatCurrency(data.rekap_manual.terjual_cash)}</td></tr>
              <tr><td>Terjual (QRIS)</td><td class="text-end">${formatCurrency(data.rekap_otomatis.terjual_qris)}</td><td class="text-end">${formatCurrency(data.rekap_manual.terjual_qris)}</td></tr>
              <tr><td>Terjual (BCA)</td><td class="text-end">${formatCurrency(data.rekap_otomatis.terjual_bca)}</td><td class="text-end">${formatCurrency(data.rekap_manual.terjual_bca)}</td></tr>
              <tr class="fw-bold"><td>Total Produk Terjual</td><td class="text-end">${data.rekap_otomatis.total_produk_terjual} Pcs</td><td class="text-end">${data.rekap_manual.total_produk_terjual} Pcs</td></tr>
              <tr class="fw-bold table-group-divider"><td>Total Pendapatan</td><td class="text-end">${formatCurrency(data.rekap_otomatis.total_pendapatan)}</td><td class="text-end">${formatCurrency(data.rekap_manual.total_pendapatan)}</td></tr>
            `;

    container.innerHTML = `
              <table>
                <tr class="top"><td colspan="2"><table><tr><td class="title"><h4>Laporan Penjualan</h4></td><td style="text-align: right;">ID Laporan: #${data.id}<br>Tanggal: ${data.tanggal}<br>Status: ${data.status}</td></tr></table></td></tr>
                <tr class="information"><td colspan="2"><table><tr><td>Lapak: <strong>${data.lokasi}</strong><br>Penanggung Jawab:<br>${data.penanggung_jawab}</td></tr></table></td></tr>
              </table>
              
              ${rincianHtml}
              
              <table class="mt-4">
                 <tr class="total"><td class="text-end fw-bold">Total Pendapatan (Sistem)</td><td class="text-end fw-bold" style="width:25%">${formatCurrency(data.rekap_otomatis.total_pendapatan)}</td></tr>
                 <tr class="total"><td class="text-end fw-bold">Total Biaya Supplier</td><td class="text-end fw-bold" style="width:25%">${formatCurrency(data.rekap_otomatis.total_biaya_supplier)}</td></tr>
              </table>
              <h5 class="mt-5 mb-3">Perbandingan Rekapitulasi</h5>
              <table class="table table-bordered"><thead class="table-light"><tr><th>Deskripsi</th><th class="text-end">Otomatis (Sistem)</th><th class="text-end">Manual (Karyawan)</th></tr></thead><tbody>${compareHtml}</tbody></table>
            `;
  } catch (e) {
    container.innerHTML = `<div class="alert alert-danger">${e.message}</div>`;
  }
}
async function downloadReportAsPDF() {
  const invoiceElement = document.getElementById("invoice-content");
  const reportId = invoiceElement
    .querySelector('td[style="text-align: right;"]')
    .innerText.split("\n")[0]
    .split("#")[1];
  const modalBody = document.querySelector(
    "#report-detail-modal .modal-body"
  );
  const originalOverflow = modalBody.style.overflow;
  modalBody.style.overflow = "visible";

  await html2canvas(invoiceElement, { scale: 2 }).then((canvas) => {
    const imgData = canvas.toDataURL("image/png");
    const pdf = new jsPDF({ orientation: "p", unit: "mm", format: "a4" });
    const imgProps = pdf.getImageProperties(imgData);
    const pdfWidth = pdf.internal.pageSize.getWidth();
    const pdfHeight = (imgProps.height * pdfWidth) / imgProps.width;
    pdf.addImage(imgData, "PNG", 0, 0, pdfWidth, pdfHeight);
    pdf.save(`laporan-harian-${reportId}.pdf`);
  });

  modalBody.style.overflow = originalOverflow;
  showToast("PDF berhasil diunduh.");
}
async function populateLaporanPendapatan() {
  const date = document.getElementById(
    "laporan-pendapatan-datepicker"
  ).value;
  const accordionEl = document.getElementById(
    "laporan-pendapatan-accordion"
  );
  accordionEl.innerHTML = `<div class="text-center p-5"><div class="spinner-border text-primary"></div></div>`;
  try {
    const resp = await fetch(
      `/api/get_laporan_pendapatan_harian?date=${date}`
    );
    if (!resp.ok) throw new Error("Gagal mengambil data");
    const data = await resp.json();
    document.getElementById("total-pendapatan-harian").textContent =
      formatCurrency(data.total_harian);
    accordionEl.innerHTML = "";
    if (data.laporan_per_lapak.length === 0) {
      accordionEl.innerHTML =
        '<div class="alert alert-warning text-center">Tidak ada laporan untuk tanggal ini.</div>';
    } else {
      data.laporan_per_lapak.forEach((lapak, index) => {
        const productList = lapak.rincian_pendapatan
          .map(
            (p) =>
              `<li class="list-group-item d-flex justify-content-between"><div>${p.produk} <small class="text-muted">(${p.supplier})</small></div><div><span class="badge text-bg-light me-2">Awal: ${p.stok_awal}</span><span class="badge text-bg-light me-2">Akhir: ${p.stok_akhir}</span><span class="badge bg-primary rounded-pill">${p.jumlah} Pcs</span></div></li>`
          )
          .join("");
        accordionEl.innerHTML += `<div class="accordion-item"><h2 class="accordion-header"><button class="accordion-button ${index !== 0 ? "collapsed" : ""
          }" type="button" data-bs-toggle="collapse" data-bs-target="#collapse-lp-${index}"><strong>${lapak.lokasi
          }</strong> <span class="ms-auto me-3">${formatCurrency(
            lapak.total_pendapatan
          )}</span></button></h2><div id="collapse-lp-${index}" class="accordion-collapse collapse ${index === 0 ? "show" : ""
          }"><div class="accordion-body"><p>PJ: <strong>${lapak.penanggung_jawab
          }</strong></p><ul class="list-group list-group-flush">${productList}</ul></div></div></div>`;
      });
    }
  } catch (error) {
    accordionEl.innerHTML =
      '<div class="alert alert-danger text-center">Gagal memuat.</div>';
  }
}
async function populateLaporanBiaya() {
  const date = document.getElementById("laporan-biaya-datepicker").value;
  const accordionEl = document.getElementById("laporan-biaya-accordion");
  accordionEl.innerHTML = `<div class="text-center p-5"><div class="spinner-border text-warning"></div></div>`;
  try {
    const resp = await fetch(
      `/api/get_laporan_biaya_harian?date=${date}`
    );
    if (!resp.ok) throw new Error("Gagal mengambil data");
    const data = await resp.json();
    document.getElementById("total-biaya-harian").textContent =
      formatCurrency(data.total_harian);
    accordionEl.innerHTML = "";
    if (data.laporan_per_lapak.length === 0) {
      accordionEl.innerHTML =
        '<div class="alert alert-warning text-center">Tidak ada laporan untuk tanggal ini.</div>';
    } else {
      data.laporan_per_lapak.forEach((lapak, index) => {
        const productList = lapak.rincian_biaya
          .map(
            (p) =>
              `<li class="list-group-item d-flex justify-content-between"><div>${p.produk
              } <small class="text-muted">(${p.supplier
              })</small></div><div><span class="badge bg-primary rounded-pill me-2">${p.jumlah
              } Pcs</span><span class="fw-bold">${formatCurrency(
                p.biaya
              )}</span></div></li>`
          )
          .join("");
        accordionEl.innerHTML += `<div class="accordion-item"><h2 class="accordion-header"><button class="accordion-button ${index !== 0 ? "collapsed" : ""
          }" type="button" data-bs-toggle="collapse" data-bs-target="#collapse-lb-${index}"><strong>${lapak.lokasi
          }</strong> <span class="ms-auto me-3">${formatCurrency(
            lapak.total_biaya
          )}</span></button></h2><div id="collapse-lb-${index}" class="accordion-collapse collapse ${index === 0 ? "show" : ""
          }"><div class="accordion-body"><p>PJ: <strong>${lapak.penanggung_jawab
          }</strong></p><ul class="list-group list-group-flush">${productList}</ul></div></div></div>`;
      });
    }
  } catch (error) {
    accordionEl.innerHTML =
      '<div class="alert alert-danger text-center">Gagal memuat.</div>';
  }
}
// (Ganti fungsi lama di baris 2017 dengan ini)
async function populateManageReportsPage() {
  const loadingEl = document.getElementById("manage-reports-loading"),
    contentEl = document.getElementById("manage-reports-content"),
    tableBody = document.getElementById("unconfirmed-reports-table-body"),
    supplierSelect = document.getElementById('manage-reports-supplier-filter');

  // (Logika pengisian dropdown supplier tetap sama)
  if (supplierSelect.options.length <= 1) {
    if (AppState.ownerData && AppState.ownerData.supplier_data) {
      AppState.ownerData.supplier_data.forEach(s => {
        supplierSelect.innerHTML += `<option value="${s.id}">${s.nama_supplier}</option>`;
      });
    }
  }
  loadingEl.style.display = "block";
  contentEl.style.display = "none";

  // === LOGIKA FILTER BARU DIMULAI DI SINI ===
  // (Sekitar baris 2035 di index.html)
  // === LOGIKA FILTER BARU DIMULAI DI SINI ===
  const params = new URLSearchParams();
  const ownerId = AppState.currentUser.user_info.id;
  params.append('owner_id', ownerId);
  const supplierId = supplierSelect.value;
  const status = document.getElementById('manage-reports-status-filter').value; // <-- BACA FILTER STATUS

  if (supplierId) params.append('supplier_id', supplierId);
  if (status) params.append('status', status); // <-- KIRIM FILTER STATUS

  const advancedFilterEl = document.getElementById('advanced-reports-filter');
  const isAdvanced = advancedFilterEl.classList.contains('show');
  let startDate, endDate;

  if (isAdvanced) {
    // 1. Gunakan filter canggih (rentang tanggal)
    startDate = document.getElementById('manage-reports-start-date').value;
    endDate = document.getElementById('manage-reports-end-date').value;
  } else {
    // 2. Gunakan filter harian
    const dailyDate = document.getElementById('manage-reports-daily-date').value;
    startDate = dailyDate;
    endDate = dailyDate;
  }

  if (startDate) params.append('start_date', startDate);
  if (endDate) params.append('end_date', endDate);
  // === LOGIKA FILTER BARU SELESAI ===

  try {
    const resp = await fetch(`/api/get_manage_reports?${params.toString()}`);
    const result = await resp.json();
    // (Sisa dari fungsi ini (try...catch...finally) tetap sama seperti file Anda)
    if (result.success) {
      tableBody.innerHTML = result.reports.length === 0 ? '<tr><td colspan="9" class="text-center text-muted">Tidak ada laporan yang cocok.</td></tr>' :
        result.reports.map((r) => {
          const statusBadge = r.status === 'Terkonfirmasi' ? `<span class="badge bg-success">${r.status}</span>` : `<span class="badge bg-warning text-dark">${r.status}</span>`;
          // (Sekitar baris 2056 di index.html)
          // Logika Tombol Aksi Baru:
          // Jika Menunggu: Tampilkan tombol "Konfirmasi"
          // Jika Terkonfirmasi: Nonaktifkan tombol
          const confirmButton = r.status === 'Menunggu Konfirmasi'
            ? `<button class="btn btn-sm btn-success" onclick="confirmReport(${r.id})"><i class="bi bi-check-circle-fill"></i> Konfirmasi</button>`
            : `<button class="btn btn-sm btn-secondary" disabled><i class="bi bi-check-circle-fill"></i></button>`;
          const profitOwnerHtml = r.status === 'Terkonfirmasi' ? formatCurrency(r.keuntungan_owner) : '-';
          const profitSuperownerHtml = r.status === 'Terkonfirmasi' ? formatCurrency(r.keuntungan_superowner) : '-';
          return `<tr>
              <td>${r.id}</td><td>${r.lokasi}</td><td>${r.penanggung_jawab}</td>
              <td>${new Date(r.tanggal).toLocaleDateString("id-ID")}</td>
              <td>${formatCurrency(r.total_pendapatan)}</td>
              <td class="text-success fw-bold">${profitOwnerHtml}</td>
              <td class="text-secondary">${profitSuperownerHtml}</td>
              <td>${statusBadge}</td>
              <td><div class="btn-group">
                  <button class="btn btn-sm btn-info" onclick="showReportDetails(${r.id})"><i class="bi bi-eye-fill"></i></button>
                  ${confirmButton}
              </div></td>
          </tr>`;
        }).join("");
      contentEl.style.display = "block";
    } else { throw new Error(result.message); }
  } catch (error) {
    loadingEl.innerHTML = `<div class="alert alert-danger">${error.message || "Gagal memuat"}</div>`;
  } finally {
    loadingEl.style.display = "none";
  }
}
// (Ganti fungsi lama di baris 2088)
async function confirmReport(reportId) {
  if (
    !confirm(
      "Apakah Anda yakin ingin mengkonfirmasi laporan ini? Tindakan ini akan menghitung profit dan memperbarui saldo tagihan supplier."
    )
  )
    return;
  try {
    // === PERBAIKAN DI SINI: Kirim ID Owner ===
    const ownerId = AppState.currentUser.user_info.id;
    const resp = await fetch(`/api/confirm_report/${reportId}`, {
      method: "POST",
      // Tambahkan body yang mengirim owner_id
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ owner_id: ownerId })
    });
    // === AKHIR PERBAIKAN ===

    const result = await resp.json();
    showToast(result.message, result.success);
    if (result.success) {
      await populateManageReportsPage();
      await populateOwnerDashboard(); // Refresh KPI card juga
    }
  } catch (e) {
    showToast("Gagal terhubung ke server.", false);
  }
}

async function openEditModal(type, id = null) {
  const isEdit = id !== null;
  let data = {};
  if (isEdit) {
    const dataArray = AppState.ownerData[`${type}_data`];
    data = dataArray.find((item) => item.id === id);
    if (!data) return showToast("Data tidak ditemukan.", false);
  }
  if (type === "admin") {
    const form = document.getElementById("edit-admin-form");
    form.reset();
    document.getElementById("admin-modal-title").textContent = isEdit
      ? "Edit Admin"
      : "Tambah Admin Baru";
    document.getElementById("edit-admin-id").value = id || "";
    if (isEdit) {
      document.getElementById("edit-admin-nama").value =
        data.nama_lengkap;
      document.getElementById("edit-admin-nik").value = data.nik;
      document.getElementById("edit-admin-username").value =
        data.username;
      document.getElementById("edit-admin-email").value = data.email;
      document.getElementById("edit-admin-kontak").value =
        data.nomor_kontak;
    }
    modals.admin.show();
  } else if (type === "lapak") {
    const form = document.getElementById("edit-lapak-form");
    form.reset();
    document.getElementById("lapak-modal-title").textContent = isEdit
      ? "Edit Lapak"
      : "Tambah Lapak Baru";
    document.getElementById("edit-lapak-id").value = id || "";

    const pjSelect = document.getElementById("lapak-pj-select");
    const anggotaContainer = document.getElementById(
      "lapak-anggota-selection"
    );
    pjSelect.innerHTML =
      '<option value="" selected disabled>-- Pilih PJ --</option>' +
      AppState.ownerData.admin_data
        .map((a) => `<option value="${a.id}">${a.nama_lengkap}</option>`)
        .join("");
    anggotaContainer.innerHTML = AppState.ownerData.admin_data
      .map(
        (a) =>
          `<div class="form-check"><input class="form-check-input" type="checkbox" value="${a.id}" id="anggota-${a.id}"><label class="form-check-label" for="anggota-${a.id}">${a.nama_lengkap}</label></div>`
      )
      .join("");

    if (isEdit) {
      document.getElementById("edit-lapak-lokasi").value = data.lokasi;
      pjSelect.value = data.user_id;
      data.anggota_ids.forEach((anggotaId) => {
        const checkbox = document.getElementById(`anggota-${anggotaId}`);
        if (checkbox) checkbox.checked = true;
      });
    }
    modals.lapak.show();
  } else if (type === "supplier") {
    const form = document.getElementById("edit-supplier-form");
    form.reset();
    document.getElementById("supplier-modal-title").textContent = isEdit ? "Edit Supplier" : "Tambah Supplier Baru";
    document.getElementById("edit-supplier-id").value = id || "";

    // BARIS PENTING: Tidak ada lagi yang disembunyikan. Semua field selalu terlihat.

    // Isi data dasar supplier
    if (isEdit) {
      document.getElementById("edit-supplier-nama").value = data.nama_supplier;
      document.getElementById("edit-supplier-username").value = data.username;
      document.getElementById("edit-supplier-kontak").value = data.kontak;
      document.getElementById("edit-supplier-register").value = data.nomor_register;
      document.getElementById("edit-supplier-alamat").value = data.alamat;
      document.getElementById("edit-supplier-metode").value = data.metode_pembayaran;
      document.getElementById("edit-supplier-rekening").value = data.nomor_rekening;
    } else {
      // Dapatkan nomor register baru untuk supplier baru
      // REVISI: Kirim ID Owner yang sedang login
      const ownerId = AppState.currentUser.user_info.id;
      const resp = await fetch(`/api/get_next_supplier_reg_number/${ownerId}`);

      const result = await resp.json();
      document.getElementById("edit-supplier-register").value = result.reg_number;
    }

    modals.supplier.show();
  }
}
// GANTI FUNGSI LAMA DENGAN VERSI BARU INI
async function handleFormSubmit(type, e) {
  e.preventDefault();
  const form = e.target;
  const id = form.querySelector(`input[type=hidden]`).value;
  const isEdit = id !== "";
  let url = isEdit ? `/api/update_${type}/${id}` : `/api/add_${type}`;
  let method = isEdit ? "PUT" : "POST";
  let payload = {};
  if (type === "admin") {
    const password = form.elements["edit-admin-password"].value;
    if (password && password !== form.elements["edit-admin-password-confirm"].value) {
      return showToast("Password dan konfirmasi tidak cocok.", false);
    }
    payload = {
      nama_lengkap: form.elements["edit-admin-nama"].value,
      username: form.elements["edit-admin-username"].value,
      email: form.elements["edit-admin-email"].value,
      nomor_kontak: form.elements["edit-admin-kontak"].value,
      password: password,
      password_confirm: form.elements["edit-admin-password-confirm"].value,
      // ==========================================================
      // ===           INILAH PERBAIKAN UTAMANYA              ===
      // ==========================================================
      // Pastikan kita selalu mengirim ID Owner yang sedang membuat admin
      created_by_owner_id: AppState.currentUser.user_info.id
      // ==========================================================
    };
  } else if (type === "lapak") {
    const anggota_ids = Array.from(
      form.querySelectorAll("#lapak-anggota-selection input:checked")
    ).map((cb) => cb.value);
    payload = {
      lokasi: form.elements["edit-lapak-lokasi"].value,
      user_id: form.elements["lapak-pj-select"].value,
      anggota_ids,
      owner_id: AppState.currentUser.user_info.id,
    };
  } else if (type === "supplier") {
    const password = form.elements["edit-supplier-password"].value;
    if (password && password !== form.elements["edit-supplier-password-confirm"].value)
      return showToast("Password dan konfirmasi tidak cocok.", false);

    payload = {
      nama_supplier: form.elements["edit-supplier-nama"].value,
      username: form.elements["edit-supplier-username"].value,
      kontak: form.elements["edit-supplier-kontak"].value,
      nomor_register: form.elements["edit-supplier-register"].value,
      alamat: form.elements["edit-supplier-alamat"].value,
      password,
      password_confirm: form.elements["edit-supplier-password-confirm"].value,
      metode_pembayaran: form.elements["edit-supplier-metode"].value,
      nomor_rekening: form.elements["edit-supplier-rekening"].value,
      owner_id: AppState.currentUser.user_info.id,
    };
  }
  const resp = await fetch(url, {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const result = await resp.json();
  showToast(result.message, resp.ok);
  if (resp.ok) {
    modals[type].hide();
    await populateOwnerDashboard();
  }
}
async function handleDelete(type, id) {
  if (
    !confirm(
      `Apakah Anda yakin ingin menghapus data ini? Tindakan ini tidak dapat dibatalkan.`
    )
  )
    return;
  const resp = await fetch(`/api/delete_${type}/${id}`, {
    method: "DELETE",
  });
  const result = await resp.json();
  showToast(result.message, resp.ok);
  if (resp.ok) await populateOwnerDashboard();
}
// GANTI FUNGSI LAMA DENGAN VERSI BARU INI
async function populateVerificationCenter() {
  const loadingEl = document.getElementById('verification-center-loading');
  const contentEl = document.getElementById('verification-center-content');
  const listEl = document.getElementById('verification-report-list');

  loadingEl.style.display = 'block';
  contentEl.style.display = 'none';

  try {
    const ownerId = AppState.currentUser.user_info.id;
    const resp = await fetch(`/api/get_owner_verification_reports/${ownerId}`);
    const result = await resp.json();
    if (!result.success) throw new Error(result.message);

    if (result.reports.length === 0) {
      listEl.innerHTML = `<div class="list-group-item text-center text-muted p-4">Tidak ada laporan baru yang perlu diverifikasi.</div>`;
      contentEl.querySelector('button').disabled = true;
    } else {
      // PERUBAHAN DI SINI: Tambahkan 'data-report-id'
      listEl.innerHTML = result.reports.map(r => `
              <div class="list-group-item d-flex justify-content-between align-items-center" data-report-id="${r.id}">
                <div>
                  <strong>Laporan dari ${r.lokasi}</strong>
                  <small class="d-block text-muted">Tanggal: ${r.tanggal} | Total: ${formatCurrency(r.total_pendapatan)}</small>
                </div>
                <button class="btn btn-sm btn-outline-info" onclick="showReportDetails(${r.id})">
                    <i class="bi bi-eye-fill"></i> Lihat Detail
                </button>
              </div>
            `).join('');
      contentEl.querySelector('button').disabled = false;
    }
    contentEl.style.display = 'block';
  } catch (e) {
    loadingEl.innerHTML = `<div class="alert alert-danger">${e.message}</div>`;
  } finally {
    loadingEl.style.display = 'none';
  }
}

// GANTI FUNGSI LAMA DENGAN VERSI BARU INI
async function handleFinalizeReports() {
  const reportItems = document.querySelectorAll('#verification-report-list .list-group-item');
  const reportIds = Array.from(reportItems).map(item => item.dataset.reportId).filter(id => id);

  if (reportIds.length === 0) {
    return showToast("Tidak ada laporan untuk difinalisasi.", false);
  }

  if (!confirm(`Anda akan memfinalisasi ${reportIds.length} laporan. Setelah difinalisasi, laporan akan dikonfirmasi dan profit akan dibagikan. Lanjutkan?`)) return;

  const button = document.querySelector('#verification-center-content button');
  const originalBtnHTML = button.innerHTML;
  button.disabled = true;
  button.innerHTML = `<span class="spinner-border spinner-border-sm"></span> Memproses...`;

  try {
    const ownerId = AppState.currentUser.user_info.id;
    const resp = await fetch('/api/finalize_reports', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ report_ids: reportIds, owner_id: ownerId })
    });
    const result = await resp.json();
    showToast(result.message, result.success);

    if (result.success) {
      // Kembali ke dashboard utama setelah berhasil
      showPage('owner-dashboard');
    }
  } catch (e) {
    showToast('Gagal terhubung ke server.', false);
  } finally {
    button.disabled = false;
    button.innerHTML = originalBtnHTML;
  }
}

// (Ganti fungsi lama di baris 2088 dengan ini)
async function populatePembayaranPage() {
  const loadingEl = document.getElementById("pembayaran-content-loading"),
    mainEl = document.getElementById("pembayaran-content-main");
  const tableBody = document.getElementById("pembayaran-table-body");
  const filterMetode = document.getElementById('tagihan-metode-filter').value; // <-- BACA FILTER

  loadingEl.style.display = "block";
  mainEl.style.display = "none";

  try {
    // === PERBAIKAN: Kirim owner_id ===
    const ownerId = AppState.currentUser.user_info.id;
    const resp = await fetch(`/api/get_pembayaran_data?owner_id=${ownerId}`);
    const result = await resp.json();
    if (!result.success) throw new Error(result.message);

    tableBody.innerHTML = "";

    // Terapkan filter metode pembayaran
    const filteredBalances = result.supplier_balances.filter(item =>
      filterMetode === 'semua' || item.metode_pembayaran === filterMetode
    );

    if (filteredBalances.length === 0) {
      tableBody.innerHTML = '<tr><td colspan="4" class="text-center text-muted">Tidak ada tagihan yang cocok.</td></tr>';
    } else {
      filteredBalances.forEach((item) => {
        let isPayable;
        if (item.metode_pembayaran === 'BCA') {
          isPayable = item.total_tagihan > 0.01;
        } else {
          isPayable = item.total_tagihan >= 20000;
        }
        const isPaid = item.total_tagihan < 0.01;
        let statusBadge, actionBtn;

        if (isPaid) {
          statusBadge = `<span class="badge bg-light text-dark">Lunas</span>`;
          actionBtn = `<button class="btn btn-sm btn-secondary" disabled>Lunas</button>`;
        } else if (isPayable) {
          statusBadge = `<span class="badge bg-success">Siap Bayar</span>`;
          actionBtn = `<button class="btn btn-sm btn-primary" onclick='openPaymentModal(${item.supplier_id}, "${item.nama_supplier}", ${item.total_tagihan})'>Bayar Tagihan</button>`;
        } else {
          statusBadge = `<span class="badge bg-warning text-dark">Akumulasi</span>`;
          actionBtn = `<button class="btn btn-sm btn-secondary" disabled>Dibawah Minimum</button>`;
        }

        // Tampilkan tanggal tagihan masuk (data baru dari API)
        const tanggalMasukHtml = item.tanggal_masuk
          ? `<small class="d-block text-danger" style="font-size: 0.8em;">Tagihan sejak: ${new Date(item.tanggal_masuk + 'T00:00:00').toLocaleDateString('id-ID')}</small>`
          : '';

        tableBody.innerHTML += `<tr>
            <td>
              ${item.nama_supplier}
              <small class="d-block text-muted">${item.metode_pembayaran} - ${item.nomor_rekening}</small>
              ${tanggalMasukHtml}
            </td>
            <td class="fw-bold">${formatCurrency(item.total_tagihan)}</td>
            <td>${statusBadge}</td>
            <td>${actionBtn}</td></tr>`;
      });
    }

    loadingEl.style.display = "none";
    mainEl.style.display = "block";

    await populatePaymentHistory();
  } catch (e) {
    showToast(e.message, false);
    loadingEl.innerHTML = `<div class="alert alert-danger">${e.message}</div>`;
  }
}

// (Ganti fungsi lama di baris 2147 dengan ini)
// (Ganti fungsi lama di baris 2147 dengan ini)
async function populatePaymentHistory() {
  const loadingEl = document.getElementById('payment-history-loading');
  const tableBody = document.getElementById('payment-history-table-body');
  loadingEl.style.display = 'block';
  tableBody.innerHTML = '';

  // (Sekitar baris 2154 di index.html)
  // === LOGIKA FILTER BARU DIMULAI DI SINI ===
  const params = new URLSearchParams();

  // === PERBAIKAN: Tambahkan owner_id ===
  const ownerId = AppState.currentUser.user_info.id;
  params.append('owner_id', ownerId);

  const metode = document.getElementById('payment-history-method').value;
  if (metode && metode !== 'semua') params.append('metode', metode);

  const advancedFilterEl = document.getElementById('advanced-payment-filter');
  const isAdvanced = advancedFilterEl.classList.contains('show');
  let startDate, endDate;

  if (isAdvanced) {
    startDate = document.getElementById('payment-history-start-date').value;
    endDate = document.getElementById('payment-history-end-date').value;
  } else {
    const dailyDate = document.getElementById('payment-history-daily-date').value;
    startDate = dailyDate;
    endDate = dailyDate;
  }

  if (startDate) params.append('start_date', startDate);
  if (endDate) params.append('end_date', endDate);

  try {
    const resp = await fetch(`/api/get_all_payment_history?${params.toString()}`);
    const result = await resp.json();
    if (!result.success) throw new Error(result.message);

    if (result.history.length === 0) {
      // Ganti colspan menjadi 5
      tableBody.innerHTML = `<tr><td colspan="5" class="text-center text-muted">Tidak ada riwayat pembayaran.</td></tr>`;
    } else {
      tableBody.innerHTML = result.history.map(p => {
        // Logika baru untuk styling berdasarkan 'tipe'
        const keteranganBadge = p.tipe === 'tagihan'
          ? `<span class="badge bg-warning text-dark">${p.keterangan}</span>`
          : `<span class="badge bg-success">${p.keterangan}</span>`;

        const jumlahClass = p.tipe === 'tagihan' ? 'text-danger' : 'text-success';
        const jumlahPrefix = p.tipe === 'tagihan' ? '-' : '+';

        return `
          <tr>
            <td>${new Date(p.tanggal + 'T00:00:00').toLocaleDateString('id-ID')}</td>
            <td>${p.nama_supplier}</td>
            <td class="${jumlahClass} fw-bold">${jumlahPrefix}${formatCurrency(p.jumlah)}</td>
            <td><span class="badge bg-info">${p.metode}</span></td>
            <td>${keteranganBadge}</td>
          </tr>
        `;
      }).join('');
    }
  } catch (e) {
    tableBody.innerHTML = `<tr><td colspan="5" class="text-center text-danger">Gagal memuat: ${e.message}</td></tr>`;
  } finally {
    loadingEl.style.display = 'none';
  }
}

function openPaymentModal(supplierId, supplierName, amount) {
  const supplierData = AppState.ownerData.supplier_data.find(
    (s) => s.id === supplierId
  );
  if (!supplierData || !supplierData.metode_pembayaran) {
    return showToast("Info pembayaran supplier belum diatur.", false);
  }
  document.getElementById("payment-supplier-id").value = supplierId;
  document.getElementById("payment-supplier-amount").value = amount;
  document.getElementById("payment-supplier-name-confirm").textContent =
    supplierName;
  document.getElementById("payment-amount-confirm").textContent =
    formatCurrency(amount);
  document.getElementById(
    "payment-method-info"
  ).textContent = `${supplierData.metode_pembayaran}: ${supplierData.nomor_rekening}`;
  modals.payment.show();
}

async function handlePaymentSubmit(e) {
  e.preventDefault();
  const payload = {
    supplier_id: document.getElementById("payment-supplier-id").value,
    jumlah_pembayaran: document.getElementById("payment-supplier-amount")
      .value,
  };
  const resp = await fetch("/api/submit_pembayaran", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const result = await resp.json();
  showToast(result.message, resp.ok);
  if (resp.ok) {
    modals.payment.hide();
    await populatePembayaranPage();
    await populateOwnerDashboard();
  }
}

document.addEventListener("DOMContentLoaded", () => {
  document
    .getElementById("edit-admin-form")
    ?.addEventListener("submit", (e) => handleFormSubmit("admin", e));
  document
    .getElementById("edit-lapak-form")
    ?.addEventListener("submit", (e) => handleFormSubmit("lapak", e));
  document
    .getElementById("edit-supplier-form")
    ?.addEventListener("submit", (e) => handleFormSubmit("supplier", e));
  document
    .getElementById("payment-confirmation-form")
    ?.addEventListener("submit", handlePaymentSubmit);
  const lpd = document.getElementById("laporan-pendapatan-datepicker");
  if (lpd) lpd.addEventListener("change", populateLaporanPendapatan);
  const lbd = document.getElementById("laporan-biaya-datepicker");
  if (lbd) lbd.addEventListener("change", populateLaporanBiaya);

  const todayISO = new Date().toISOString().split("T")[0];
  ["laporan-pendapatan-datepicker", "laporan-biaya-datepicker"].forEach(
    (id) => {
      const el = document.getElementById(id);
      if (el) el.value = todayISO;
    }
  );

  const filterBtn = document.getElementById('supplier-history-filter-btn');
  if (filterBtn) {
    filterBtn.addEventListener('click', populateSupplierHistoryPage);
  }
  const manageReportsFilterBtn = document.getElementById('manage-reports-filter-btn');
  if (manageReportsFilterBtn) {
    manageReportsFilterBtn.addEventListener('click', populateManageReportsPage);
  }

  const paymentHistoryFilterBtn = document.getElementById('payment-history-filter-btn');
  if (paymentHistoryFilterBtn) {
    paymentHistoryFilterBtn.addEventListener('click', populatePaymentHistory);
  }

  document.getElementById('payment-history-daily-date').addEventListener('change', () => {
    bootstrap.Collapse.getOrCreateInstance('#advanced-payment-filter').hide();
    populatePaymentHistory();
  });
  document.getElementById('payment-history-prev-day').addEventListener('click', () => changePaymentDate(-1));
  document.getElementById('payment-history-next-day').addEventListener('click', () => changePaymentDate(1));
  // Listener untuk select metode (karena sekarang di luar)
  document.getElementById('payment-history-method').addEventListener('change', () => {
    // Jika filter harian aktif, refresh. Jika filter canggih, jangan lakukan apa-apa (tunggu tombol apply)
    const isAdvanced = document.getElementById('advanced-payment-filter').classList.contains('show');
    if (!isAdvanced) {
      populatePaymentHistory();
    }
  });

  document.getElementById('tagihan-metode-filter').addEventListener('change', populatePembayaranPage);
  const ownerSupplierSelect = document.getElementById('owner-supplier-select');
  if (ownerSupplierSelect) {
    // Listener ini memastikan data tampil saat supplier DIPILIH
    ownerSupplierSelect.addEventListener('change', fetchAndDisplayOwnerSupplierHistory);
  }
  const chartFilterBtn = document.getElementById('chart-filter-btn');
  if (chartFilterBtn) {
    chartFilterBtn.addEventListener('click', fetchAndDrawCharts);
  }
  const ownerHistoryFilterBtn = document.getElementById('owner-history-filter-btn');
  if (ownerHistoryFilterBtn) {
    // Listener ini memastikan data ter-filter saat tombol DIKLIK
    ownerHistoryFilterBtn.addEventListener('click', fetchAndDisplayOwnerSupplierHistory);
  }
});