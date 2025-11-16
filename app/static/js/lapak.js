// --- LAPAK FUNCTIONS ---

async function openAturProdukModal() {
  const supplierContainer = document.getElementById("supplier-selection-container");
  const productContainer = document.getElementById("product-selection-container");
  const productAreaTitle = document.getElementById("product-area-title");
  const addProductForm = document.getElementById("add-product-form-container");
  const productSelectionArea = document.getElementById("product-selection-area");

  // Reset tampilan modal ke kondisi awal
  supplierContainer.innerHTML = '<div class="spinner-border spinner-border-sm"></div>';
  productContainer.innerHTML = '';
  productAreaTitle.innerHTML = '<p class="text-muted pt-3">Pilih satu supplier untuk melihat & menambah produk.</p>';
  addProductForm.style.display = 'none';
  productSelectionArea.style.display = 'none'; // Sembunyikan juga area produk

  modals.aturProduk.show();

  try {
    const resp = await fetch(`/api/lapak/get_data_buat_catatan/${AppState.currentUser.user_info.lapak_id}`);
    const result = await resp.json();
    if (!result.success) {
      if (result.already_exists) {
        modals.aturProduk.hide();
        showToast(result.message, false);
        document.getElementById("laporan-exists").style.display = "block";
        document.getElementById("laporan-content").style.display = "none";
      }
      throw new Error(result.message);
    }

    // Simpan daftar supplier
    AppState.masterData.suppliers = result.data;
    AppState.masterData.products = result.data.flatMap(supplier =>
      supplier.products.map(product => ({
        ...product,
        supplier_id: supplier.id
      }))
    );
    // ==========================================================

    // Tampilkan daftar supplier sebagai radio button
    supplierContainer.innerHTML = AppState.masterData.suppliers.map(s => `
              <label class="list-group-item">
                <input class="form-check-input me-2 supplier-radio" type="radio" name="supplierSelection" value="${s.id}">
                ${s.name}
              </label>
            `).join('');

    // Tambahkan event listener ke setiap radio button supplier
    document.querySelectorAll('.supplier-radio').forEach(radio => {
      radio.addEventListener('change', updateProductSelection);
    });

  } catch (e) {
    supplierContainer.innerHTML = `<div class="alert alert-danger p-2 small">${e.message}</div>`;
  }
}

function updateProductSelection(event) {
  const supplierId = parseInt(event.target.value);
  const productContainer = document.getElementById("product-selection-container");
  const productAreaTitle = document.getElementById("product-area-title");
  const addProductForm = document.getElementById("add-product-form-container");
  const productSelectionArea = document.getElementById("product-selection-area");
  const searchInput = document.getElementById("modal-product-search-input");

  const selectedSupplier = AppState.masterData.suppliers.find(s => s.id === supplierId);
  productAreaTitle.innerHTML = `<h6>Produk dari: <strong>${selectedSupplier.name}</strong></h6>`;
  addProductForm.style.display = 'block';
  productSelectionArea.style.display = 'block';
  searchInput.value = '';

  const renderProducts = (searchTerm = "") => {
    const productsOfSupplier = AppState.masterData.products.filter(p =>
      p.supplier_id === supplierId && p.name.toLowerCase().includes(searchTerm.toLowerCase())
    );
    if (productsOfSupplier.length === 0) {
      productContainer.innerHTML = '<p class="text-muted small p-2">Belum ada produk atau tidak ada hasil yang cocok.</p>';
    } else {
      productContainer.innerHTML = productsOfSupplier.map(p => `
                      <div class="input-group input-group-sm mb-2">
                          <div class="input-group-text">
                              <input class="form-check-input mt-0 product-checkbox" type="checkbox" value="${p.id}" id="modal-product-${p.id}">
                          </div>
                          <label for="modal-product-${p.id}" class="form-control">${p.name}</label>
                          <input type="number" class="form-control form-control-sm text-center modal-stok-awal" placeholder="Stok Awal" style="max-width: 100px;" disabled>
                      </div>
                  `).join('');
    }
  };

  renderProducts();
  searchInput.oninput = () => renderProducts(searchInput.value);

  productContainer.onclick = function (e) {
    if (e.target.classList.contains('product-checkbox')) {
      const stokInput = e.target.closest('.input-group').querySelector('.modal-stok-awal');
      stokInput.disabled = !e.target.checked;
      if (!e.target.checked) stokInput.value = '';
    }
  };
}

async function handleAddNewProduct(e) {
  e.preventDefault();
  const productName = document.getElementById("new-product-name-input").value.trim();
  const selectedSupplierRadio = document.querySelector('.supplier-radio:checked');

  if (!productName || !selectedSupplierRadio) {
    return showToast("Nama produk dan supplier harus dipilih.", false);
  }
  const supplierId = parseInt(selectedSupplierRadio.value);
  const lapakId = AppState.currentUser.user_info.lapak_id;

  const submitBtn = e.target.querySelector('button[type="submit"]');
  submitBtn.disabled = true;
  submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';

  try {
    const resp = await fetch('/api/lapak/add_manual_product_to_supplier', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        nama_produk: productName,
        supplier_id: supplierId,
        lapak_id: lapakId
      })
    });
    const result = await resp.json();
    showToast(result.message, result.success);

    if (result.success) {
      AppState.masterData.products.push(result.product);
      document.getElementById("new-product-name-input").value = '';
      updateProductSelection({ target: selectedSupplierRadio });

      setTimeout(() => {
        const newCheckbox = document.getElementById(`modal-product-${result.product.id}`);
        if (newCheckbox) {
          newCheckbox.checked = true;
          const stokInput = newCheckbox.closest('.input-group').querySelector('.modal-stok-awal');
          if (stokInput) stokInput.disabled = false;
        }
      }, 100); // Beri jeda sedikit agar DOM selesai update
      // ================================================================
    }
  } catch (error) {
    showToast('Gagal terhubung ke server.', false);
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = 'Simpan';
  }
}

function generateReportTables() {
  const container = document.getElementById("report-tables-container");
  const summaryContainer = document.getElementById("report-summary-container");
  const selectedCheckboxes = document.querySelectorAll('.product-checkbox:checked');

  if (selectedCheckboxes.length === 0) return showToast("Pilih setidaknya satu produk.", false);

  let productsToDisplay = [];
  let hasInvalidStok = false;
  selectedCheckboxes.forEach(cb => {
    const productId = parseInt(cb.value);
    const stokInput = cb.closest('.input-group').querySelector('.modal-stok-awal');
    const stokAwal = parseInt(stokInput.value) || 0;
    if (stokAwal <= 0) hasInvalidStok = true;
    const product = AppState.masterData.products.find(p => p.id === productId);
    if (product) productsToDisplay.push({ ...product, stokAwal });
  });

  if (hasInvalidStok) return showToast("Stok awal harus diisi dan lebih dari 0.", false);

  const initialPrompt = document.getElementById("initial-prompt");
  if (initialPrompt) initialPrompt.style.display = 'none';

  summaryContainer.style.display = 'block';
  document.getElementById("product-search-container").style.display = 'block';

  productsToDisplay.forEach(productData => {
    const supplier = AppState.masterData.suppliers.find(s => s.id === productData.supplier_id);
    const supplierGroupId = `supplier-group-${supplier.id}`;
    let supplierGroup = document.getElementById(supplierGroupId);

    if (!supplierGroup) {
      const newGroup = document.createElement('div');
      newGroup.id = supplierGroupId;
      newGroup.className = 'mb-4';
      const paymentMethod = supplier.metode_pembayaran ? `<span class="badge bg-info">${supplier.metode_pembayaran}</span>` : '';
      newGroup.innerHTML = `
                    <h5 class="d-flex justify-content-between align-items-center">${supplier.name} ${paymentMethod}</h5>
                    <div class="table-responsive">
                        <table class="table table-bordered table-hover align-middle">
                            <thead class="table-light">
                                <tr>
                                    <th>Produk</th><th style="width: 15%">Stok Awal</th>
                                    <th style="width: 15%">Stok Akhir</th><th class="text-center" style="width: 10%">Terjual</th>
                                    <th class="text-center" style="width: 15%">Notifikasi</th>
                                </tr>
                            </thead>
                            <tbody></tbody>
                            <tfoot class="table-group-divider">
                              <tr>
                                <td class="text-end fw-bold">Total (per Supplier):</td>
                                <td class="text-center fw-bold supplier-total-awal">0</td>
                                <td class="text-center fw-bold supplier-total-akhir">0</td>
                                <td class="text-center fw-bold supplier-total-terjual">0</td>
                                <td></td>
                              </tr>
                            </tfoot>
                            </table>
                    </div>
                `;
      container.appendChild(newGroup);
      supplierGroup = newGroup;
    }

    const tableBody = supplierGroup.querySelector('tbody');
    const isProductExist = tableBody.querySelector(`tr[data-product-id="${productData.id}"]`);

    if (!isProductExist) {
      let rowHtml = createProductRow(productData, supplier);
      const tempTbody = document.createElement('tbody');
      tempTbody.innerHTML = rowHtml;
      const newRow = tempTbody.querySelector('tr');

      if (newRow) {
        newRow.querySelector('.stok-awal').value = productData.stokAwal;
        attachEventListenersToRow(newRow);
        tableBody.appendChild(newRow);
      }
    }
  });

  updateSummarySection();
  saveReportStateToLocalStorage();
  modals.aturProduk.hide();
  showToast("Produk berhasil ditambahkan ke tabel.");
}
function createProductRow(product, supplier) {
  const stokAkhirInput = `<div class="d-inline-flex flex-column">
                  <button class="btn btn-outline-secondary btn-plus py-0" type="button"><i class="bi bi-caret-up-fill"></i></button>
                  <input type="number" class="form-control form-control-sm text-center input-stok stok-akhir" placeholder="0" min="0">
                  <button class="btn btn-outline-secondary btn-minus py-0" type="button"><i class="bi bi-caret-down-fill"></i></button>
              </div>`;
  return `
              <tr class="product-row" data-product-id="${product.id}" data-harga-jual="${product.harga_jual}" data-harga-beli="${product.harga_beli}">
                  <td class="product-supplier-info"><strong>${product.name}</strong></td>
                  <td><input type="number" class="form-control-plaintext form-control-sm text-center input-stok stok-awal" readonly></td>
                  <td>${stokAkhirInput}</td>
                  <td class="text-center fw-bold terjual-pcs">0</td>
                  <td class="text-center"><button class="btn btn-outline-warning btn-sm notify-btn"><i class="bi bi-bell-fill"></i> Stok Habis</button></td>
              </tr>`;
}

async function populateLapakDashboard() {
  const loadingEl = document.getElementById("laporan-loading"),
    contentEl = document.getElementById("laporan-content"),
    existsEl = document.getElementById("laporan-exists");

  loadingEl.style.display = "block";
  contentEl.style.display = "none";
  existsEl.style.display = "none";
  document.getElementById("report-tables-container").innerHTML = `
            <div id="initial-prompt" class="text-center text-muted p-5 border rounded">
                <i class="bi bi-ui-checks-grid" style="font-size: 3rem;"></i><h5 class="mt-3">Mulai Laporan Harian</h5>
                <p>Klik "Atur Produk" di atas untuk memilih produk yang akan dijual hari ini.</p>
            </div>`;
  document.getElementById("product-search-container").style.display = "none";

  try {
    // API dipanggil untuk mengecek apakah laporan hari ini sudah ada
    const resp = await fetch(
      `/api/lapak/get_data_buat_catatan/${AppState.currentUser.user_info.lapak_id}`
    );
    if (!resp.ok && resp.status === 409) {
      existsEl.style.display = "block";
      document.getElementById("rekap-footer").style.display = "none";
    } else {
      contentEl.style.display = "block";
    }
  } catch (error) {
    loadingEl.innerHTML = `<div class="alert alert-danger">${error.message}</div>`;
  } finally {
    loadingEl.style.display = "none";
  }
}

async function populateLapakDashboard() {
  const loadingEl = document.getElementById("laporan-loading"),
    contentEl = document.getElementById("laporan-content"),
    existsEl = document.getElementById("laporan-exists"),
    initialPrompt = document.getElementById("initial-prompt"),
    menuCards = contentEl.querySelectorAll('.menu-card');

  // Reset semua tampilan ke kondisi awal
  loadingEl.style.display = "block";
  contentEl.style.display = "none";
  existsEl.style.display = "none";
  const lapakId = AppState.currentUser.user_info.lapak_id;

  // Cek jika admin belum ditugaskan ke lapak manapun
  if (!lapakId) {
    loadingEl.style.display = 'none';
    contentEl.style.display = 'block';
    initialPrompt.innerHTML = `
                <i class="bi bi-person-workspace" style="font-size: 3rem;"></i>
                <h5 class="mt-3">Anda Belum Ditugaskan</h5>
                <p>Saat ini Anda belum ditugaskan ke lapak manapun. Silakan hubungi Owner Anda untuk mendapatkan penugasan.</p>
            `;
    // Nonaktifkan menu
    menuCards.forEach(card => card.style.pointerEvents = 'none');
    document.getElementById('rekap-footer').style.display = 'none';
    return; // Hentikan eksekusi lebih lanjut
  }

  // Jika admin punya lapak_id, lanjutkan seperti biasa
  initialPrompt.innerHTML = `
            <i class="bi bi-ui-checks-grid" style="font-size: 3rem;"></i>
            <h5 class="mt-3">Mulai Laporan Harian</h5>
            <p>Klik "Atur Produk" di atas untuk memilih produk yang akan dijual hari ini.</p>`;
  menuCards.forEach(card => card.style.pointerEvents = 'auto');
  document.getElementById("product-search-container").style.display = "none";

  try {
    const resp = await fetch(`/api/lapak/get_data_buat_catatan/${lapakId}`);
    if (!resp.ok) {
      const result = await resp.json();
      if (resp.status === 409 && result.already_exists) {
        existsEl.style.display = "block";
        document.getElementById("rekap-footer").style.display = "none";
      } else { throw new Error(result.message); }
    } else {
      contentEl.style.display = "block";
      const result = await resp.json();
      AppState.masterData.suppliers = result.data;
      AppState.masterData.products = result.data.flatMap(supplier => supplier.products.map(product => ({ ...product, supplier_id: supplier.id })));
      loadReportStateFromLocalStorage();
    }
  } catch (error) {
    loadingEl.innerHTML = `<div class="alert alert-danger">${error.message}</div>`;
  } finally {
    loadingEl.style.display = "none";
  }
}


function updateRowAndTotals(row) {
  const awal = parseInt(row.querySelector(".stok-awal").value) || 0;
  let akhirInput = row.querySelector(".stok-akhir");
  let akhir = parseInt(akhirInput.value) || 0;
  if (akhir > awal) { akhir = awal; akhirInput.value = awal; }
  const terjual = awal - akhir;
  row.querySelector(".terjual-pcs").textContent = terjual;
  updateSummarySection(); // Panggil update ringkasan
  saveReportStateToLocalStorage();
}

// (Ganti fungsi lama di baris 2487)
function updateSummarySection() {
  const summaryPlaceholder = document.getElementById("summary-placeholder");
  const summaryContent = document.getElementById("summary-content");
  summaryPlaceholder.style.display = 'block';
  summaryContent.style.display = 'none';

  let totalTerjual = 0, totalPendapatan = 0, totalBiaya = 0, totalKeuntungan = 0;

  // Objek untuk menyimpan total per supplier (awal, akhir, terjual)
  let supplierTotals = {};

  document.querySelectorAll(".product-row").forEach(row => {
    // Ambil nilai stok awal, akhir, dan terjual
    const stokAwal = parseInt(row.querySelector(".stok-awal").value) || 0;
    const stokAkhir = parseInt(row.querySelector(".stok-akhir").value) || 0;
    const terjual = parseInt(row.querySelector('.terjual-pcs').textContent) || 0;

    const hargaJual = parseFloat(row.dataset.hargaJual) || 0;
    const hargaBeli = parseFloat(row.dataset.hargaBeli) || 0;

    // Hitung total keseluruhan
    totalTerjual += terjual;
    totalPendapatan += terjual * hargaJual;
    totalBiaya += terjual * hargaBeli;

    // Hitung total per supplier
    const supplierGroup = row.closest("[id^='supplier-group-']");
    if (supplierGroup) {
      const supplierId = supplierGroup.id;
      // Inisialisasi jika belum ada
      if (!supplierTotals[supplierId]) {
        supplierTotals[supplierId] = { awal: 0, akhir: 0, terjual: 0 };
      }
      // Tambahkan nilai
      supplierTotals[supplierId].awal += stokAwal;
      supplierTotals[supplierId].akhir += stokAkhir;
      supplierTotals[supplierId].terjual += terjual;
    }
  });
  totalKeuntungan = totalPendapatan - totalBiaya;

  // Tampilkan total per supplier ke tfoot
  for (const supplierId in supplierTotals) {
    const groupElement = document.getElementById(supplierId);
    if (groupElement) {
      const totals = supplierTotals[supplierId];
      groupElement.querySelector('.supplier-total-awal').textContent = totals.awal;
      groupElement.querySelector('.supplier-total-akhir').textContent = totals.akhir;
      groupElement.querySelector('.supplier-total-terjual').textContent = totals.terjual;
    }
  }

  // Perbarui Tampilan (Global) - (Bagian ini tidak berubah)
  document.getElementById("summary-total-terjual").textContent = `${totalTerjual} Pcs`;
  document.getElementById("summary-total-pendapatan").textContent = formatCurrency(totalPendapatan);
  document.getElementById("summary-total-biaya").textContent = formatCurrency(totalBiaya);
  document.getElementById("summary-total-keuntungan").textContent = formatCurrency(totalKeuntungan);
  document.getElementById("total-sistem").textContent = formatCurrency(totalPendapatan);

  const qris = parseFloat(document.getElementById("rekap-qris").value.replace(/\D/g, '')) || 0;
  const bca = parseFloat(document.getElementById("rekap-bca").value.replace(/\D/g, '')) || 0;
  const cash = parseFloat(document.getElementById("rekap-cash").value.replace(/\D/g, '')) || 0;
  const totalManual = qris + bca + cash;
  document.getElementById("total-manual").textContent = formatCurrency(totalManual);

  // Rekonsiliasi (Bagian ini tidak berubah)
  checkReconciliation(totalPendapatan, totalManual);

  setTimeout(() => {
    summaryPlaceholder.style.display = 'none';
    summaryContent.style.display = 'block';
  }, 200);
}

function checkReconciliation(totalSistem, totalManual) {
  const warningEl = document.getElementById("reconciliation-warning");
  const submitBtn = document.getElementById("kirim-laporan-btn");
  const isMatched = Math.abs(totalSistem - totalManual) < 0.01;
  if (isMatched && totalSistem > 0) {
    warningEl.style.display = "none";
    submitBtn.disabled = false;
    submitBtn.classList.remove("btn-danger");
    submitBtn.classList.add("btn-primary");
  } else {
    warningEl.style.display =
      totalSistem > 0 && !isMatched ? "block" : "none";
    submitBtn.disabled = true;
    if (totalSistem > 0) {
      submitBtn.classList.add("btn-danger");
      submitBtn.classList.remove("btn-primary");
    }
  }
}


// GANTI Funghi LAMA DENGAN VERSI BARU INI
function attachAllEventListeners() {
  // Fungsi ini sekarang hanya bertanggung jawab untuk event listener di dalam tabel
  document.querySelectorAll(".product-row").forEach((row) => {
    attachEventListenersToRow(row);
  });

  // Listener untuk input pencarian tabel utama
  const mainSearchInput = document.getElementById('main-report-search-input');
  if (mainSearchInput) {
    mainSearchInput.addEventListener('input', filterMainReportTable);
  }
}

// (Letakkan ini setelah fungsi checkReconciliation)

// FUNGSI BARU 1: Untuk menyimpan keadaan tabel ke localStorage
function saveReportStateToLocalStorage() {
  if (!AppState.currentUser || AppState.currentUser.role !== 'lapak') return;

  const reportData = [];
  document.querySelectorAll(".product-row").forEach(row => {
    reportData.push({
      productId: parseInt(row.dataset.productId),
      stokAwal: parseInt(row.querySelector(".stok-awal").value) || 0,
      stokAkhir: parseInt(row.querySelector(".stok-akhir").value) || 0
    });
  });

  const storageKey = `reportState_${AppState.currentUser.user_info.lapak_id}`;
  localStorage.setItem(storageKey, JSON.stringify(reportData));
}

// FUNGSI BARU 2: Untuk memuat dan membangun kembali tabel dari localStorage

function loadReportStateFromLocalStorage() {
  if (!AppState.currentUser || AppState.currentUser.role !== 'lapak') return;

  const storageKey = `reportState_${AppState.currentUser.user_info.lapak_id}`;
  const savedData = JSON.parse(localStorage.getItem(storageKey) || '[]');

  if (savedData.length === 0) return;

  const container = document.getElementById("report-tables-container");
  const summaryContainer = document.getElementById("report-summary-container");

  // Hapus "initial-prompt" jika ada
  const initialPrompt = document.getElementById("initial-prompt");
  if (initialPrompt) initialPrompt.style.display = 'none';

  container.innerHTML = ''; // Kosongkan container sebelum membangun

  savedData.forEach(item => {
    const product = AppState.masterData.products.find(p => p.id === item.productId);
    const supplier = AppState.masterData.suppliers.find(s => s.id === product.supplier_id);

    if (product && supplier) {
      const supplierGroupId = `supplier-group-${supplier.id}`;
      let supplierGroup = document.getElementById(supplierGroupId);

      // Jika grup supplier belum ada, buat dulu
      if (!supplierGroup) {
        const newGroup = document.createElement('div');
        newGroup.id = supplierGroupId;
        newGroup.className = 'mb-4';
        const paymentMethod = supplier.metode_pembayaran ? `<span class="badge bg-info">${supplier.metode_pembayaran}</span>` : '';

        // ==========================================================
        // ===           INILAH PERBAIKAN UTAMANYA              ===
        // ==========================================================
        // Gunakan struktur header tabel yang benar (tanpa Biaya & Keuntungan)
        // (Sekitar baris 2595 di index.html)
        newGroup.innerHTML = `
                    <h5 class="d-flex justify-content-between align-items-center">${supplier.name} ${paymentMethod}</h5>
                    <div class="table-responsive">
                        <table class="table table-bordered table-hover align-middle">
                            <thead class="table-light">
                                <tr>
                                    <th>Produk</th>
                                    <th style="width: 15%">Stok Awal</th>
                                    <th style="width: 15%">Stok Akhir</th>
                                    <th class="text-center" style="width: 10%">Terjual</th>
                                    <th class="text-center" style="width: 15%">Notifikasi</th>
                                </tr>
                            </thead>
                            <tbody></tbody>
                            <tfoot class="table-group-divider">
                              <tr>
                                <td class="text-end fw-bold">Total (per Supplier):</td>
                                <td class="text-center fw-bold supplier-total-awal">0</td>
                                <td class="text-center fw-bold supplier-total-akhir">0</td>
                                <td class="text-center fw-bold supplier-total-terjual">0</td>
                                <td></td>
                              </tr>
                            </tfoot>
                            </table>
                    </div>
                `;
        // ==========================================================
        container.appendChild(newGroup);
        supplierGroup = newGroup;
      }

      const tableBody = supplierGroup.querySelector('tbody');
      let rowHtml = createProductRow(product, supplier);
      const tempTbody = document.createElement('tbody');
      tempTbody.innerHTML = rowHtml;
      const newRow = tempTbody.querySelector('tr');

      if (newRow) {
        newRow.querySelector('.stok-awal').value = item.stokAwal;
        newRow.querySelector('.stok-akhir').value = item.stokAkhir; // Isi juga stok akhir yang tersimpan
        tableBody.appendChild(newRow);
        attachEventListenersToRow(newRow);
      }
    }
  });

  summaryContainer.style.display = 'block';
  document.getElementById("product-search-container").style.display = 'block';
  updateSummarySection(); // Hitung ulang semua total
  showToast("Sesi laporan sebelumnya berhasil dipulihkan.", true);
}


async function handleNotifySupplier(button) {
  const row = button.closest('tr');
  const productId = row.dataset.productId;
  const lapakId = AppState.currentUser.user_info.lapak_id;

  if (!confirm("Kirim notifikasi stok habis ke supplier?")) return;

  button.disabled = true;
  button.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';

  try {
    const resp = await fetch('/api/lapak/notify_supplier', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ product_id: productId, lapak_id: lapakId })
    });
    const result = await resp.json();
    showToast(result.message, result.success);

    if (result.success) {
      button.classList.remove('btn-outline-warning');
      button.classList.add('btn-success');
      button.innerHTML = '<i class="bi bi-check-lg"></i> Terkirim';
    } else {
      // Jika gagal, kembalikan tombol ke keadaan semula
      button.disabled = false;
      button.innerHTML = '<i class="bi bi-bell-fill"></i> Stok Habis';
    }
  } catch (error) {
    showToast('Gagal terhubung ke server.', false);
    button.disabled = false;
    button.innerHTML = '<i class="bi bi-bell-fill"></i> Stok Habis';
  }
}




function attachEventListenersToRow(row) {
  // Event listener untuk input angka manual (ini sudah benar)
  row.querySelectorAll(".stok-akhir").forEach((input) => {
    input.addEventListener("input", () => updateRowAndTotals(row));
  });

  // Logika untuk tombol spinner (ini juga sudah benar)
  const parentDiv = row.querySelector('.stok-akhir')?.closest('div');
  if (parentDiv) {
    const plusBtn = parentDiv.querySelector('.btn-plus');
    const minusBtn = parentDiv.querySelector('.btn-minus');
    const input = parentDiv.querySelector(".stok-akhir");

    if (plusBtn) {
      plusBtn.addEventListener("click", () => {
        let currentValue = parseInt(input.value) || 0;
        currentValue++;
        input.value = currentValue;
        input.dispatchEvent(new Event("input")); // Picu kalkulasi ulang
      });
    }

    if (minusBtn) {
      minusBtn.addEventListener("click", () => {
        let currentValue = parseInt(input.value) || 0;
        currentValue = Math.max(0, currentValue - 1);
        input.value = currentValue;
        input.dispatchEvent(new Event("input")); // Picu kalkulasi ulang
      });
    }
  }

  // ==========================================================
  // ===           INILAH PERBAIKAN UTAMANYA              ===
  // ==========================================================
  // Event listener untuk tombol notifikasi kita nonaktifkan sementara
  // karena fungsinya (handleNotifySupplier) belum dibuat.
  // INILAH YANG MENYEBABKAN ERROR FATAL.

  const notifyBtn = row.querySelector('.notify-btn');
  if (notifyBtn) {
    notifyBtn.addEventListener('click', () => handleNotifySupplier(notifyBtn));
  }

  // ==========================================================
}

// (Letakkan ini setelah fungsi attachEventListenersToRow)


function filterMainReportTable(e) {
  const searchTerm = e.target.value.toLowerCase();

  // Loop melalui setiap grup supplier
  document.querySelectorAll("[id^='supplier-group-']").forEach(group => {
    const supplierName = group.querySelector('h5').textContent.toLowerCase();
    const productRows = group.querySelectorAll('.product-row');
    let groupHasVisibleRows = false;

    // Loop melalui setiap baris produk di dalam grup
    productRows.forEach(row => {
      const productName = row.querySelector('.product-supplier-info strong').textContent.toLowerCase();

      // Sebuah baris akan terlihat jika nama produk ATAU nama suppliernya cocok
      const isVisible = productName.includes(searchTerm) || supplierName.includes(searchTerm);

      row.style.display = isVisible ? "" : "none"; // Tampilkan atau sembunyikan baris ini

      if (isVisible) {
        groupHasVisibleRows = true; // Tandai bahwa grup ini punya setidaknya satu baris yang terlihat
      }
    });

    // Setelah semua baris diperiksa, tentukan apakah seluruh grup (termasuk judulnya) perlu ditampilkan
    group.style.display = groupHasVisibleRows ? 'block' : 'none';
  });
}

async function handleKirimLaporan() {
  if (!confirm("Kirim laporan ini? Laporan yang sudah dikirim tidak bisa diubah.")) return;

  const productData = [];
  document.querySelectorAll(".product-row").forEach((row) => {
    const stokAwal = row.querySelector(".stok-awal").value;
    const stokAkhir = row.querySelector(".stok-akhir").value;
    // Hanya kirim data yang diisi
    if (stokAwal > 0 || stokAkhir > 0) {
      productData.push({
        id: parseInt(row.dataset.productId),
        stok_awal: parseInt(stokAwal) || 0,
        stok_akhir: parseInt(stokAkhir) || 0,
      });
    }
  });

  if (productData.length === 0) return showToast("Tidak ada data penjualan.", false);

  const rekapData = {
    qris: document.getElementById("rekap-qris").value.replace(/\D/g, '') || '0',
    bca: document.getElementById("rekap-bca").value.replace(/\D/g, '') || '0',
    cash: document.getElementById("rekap-cash").value.replace(/\D/g, '') || '0',
    total: document.getElementById("total-manual").textContent.replace(/\D/g, "") || '0',
  };

  const payload = {
    lapak_id: AppState.currentUser.user_info.lapak_id,
    products: productData,
    rekap_pembayaran: rekapData,
  };

  const submitBtn = document.getElementById("kirim-laporan-btn");
  const originalBtnHTML = submitBtn.innerHTML;
  submitBtn.disabled = true;
  submitBtn.innerHTML = `<span class="spinner-border spinner-border-sm"></span> Mengirim...`;

  try {
    const response = await fetch("/api/lapak/submit_catatan_harian", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const result = await response.json();
    showToast(result.message, response.ok);
    if (response.ok) {
      // Bersihkan localStorage setelah pengiriman berhasil
      const storageKey = `reportState_${AppState.currentUser.user_info.lapak_id}`;
      localStorage.removeItem(storageKey);
      // Muat ulang dashboard untuk menampilkan status terbaru
      await populateLapakDashboard();
    }
  } catch (e) {
    showToast("Gagal terhubung ke server.", false);
  } finally {
    submitBtn.disabled = false;
    submitBtn.innerHTML = originalBtnHTML;
  }
}
async function populateHistoryLaporanPage() {
  const loadingEl = document.getElementById("history-loading"),
    listEl = document.getElementById("history-list");
  loadingEl.style.display = "block";
  listEl.innerHTML = "";
  const resp = await fetch(
    `/api/lapak/get_history_laporan/${AppState.currentUser.user_info.lapak_id}`
  );
  if (!resp.ok) {
    loadingEl.innerHTML =
      '<div class="alert alert-danger">Gagal memuat histori.</div>';
    return;
  }
  const result = await resp.json();
  loadingEl.style.display = "none";
  if (result.reports.length === 0) {
    listEl.innerHTML =
      '<div class="alert alert-info">Belum ada laporan yang dibuat.</div>';
    return;
  }
  result.reports.forEach((r) => {
    const statusBadge =
      r.status === "Terkonfirmasi"
        ? '<span class="badge bg-success">Terkonfirmasi</span>'
        : '<span class="badge bg-warning text-dark">Menunggu Konfirmasi</span>';
    listEl.innerHTML += `<div class="list-group-item"><div class="d-flex w-100 justify-content-between"><h5 class="mb-1">${new Date(
      r.tanggal
    ).toLocaleDateString("id-ID", {
      weekday: "long",
      year: "numeric",
      month: "long",
      day: "numeric",
    })}</h5>${statusBadge}</div><p class="mb-1">Total pendapatan: <strong>${formatCurrency(
      r.total_pendapatan
    )}</strong></p><small>Total produk terjual: ${r.total_produk_terjual
      } Pcs.</small></div>`;
  });
}

document.addEventListener("DOMContentLoaded", () => {
  const rekapCollapseEl = document.getElementById('rekap-manual-collapse');
  if (rekapCollapseEl) {
    const rekapText = document.getElementById('toggle-rekap-text');
    const rekapIcon = document.getElementById('toggle-rekap-icon');

    // Saat akan ditampilkan (show)
    rekapCollapseEl.addEventListener('show.bs.collapse', event => {
      rekapText.textContent = 'Sembunyikan Input';
      rekapIcon.classList.remove('bi-chevron-up');
      rekapIcon.classList.add('bi-chevron-down');
    });

    // Saat akan disembunyikan (hide)
    rekapCollapseEl.addEventListener('hide.bs.collapse', event => {
      rekapText.textContent = 'Input Hasil Penjualan';
      rekapIcon.classList.remove('bi-chevron-down');
      rekapIcon.classList.add('bi-chevron-up');
    });
  }
  document
    .getElementById("add-product-to-supplier-form")
    .addEventListener("submit", handleAddNewProduct);

  document
    .getElementById("kirim-laporan-btn")
    .addEventListener("click", handleKirimLaporan);
  // Pasang event listener untuk input footer DI SINI
  document.querySelectorAll(".rekap-input").forEach(input => {
    input.addEventListener("input", formatNumberInput); // Untuk format angka
    input.addEventListener("keyup", updateSummarySection); // Untuk kalkulasi ulang
  });

  const searchInput = document.getElementById('main-report-search-input');
  if (!searchInput) return;

  searchInput.addEventListener('input', function () {
    const filter = this.value.toLowerCase();
    const tables = document.querySelectorAll('#report-tables-container table tbody');

    tables.forEach(tbody => {
      const rows = tbody.querySelectorAll('tr');
      rows.forEach(row => {
        const text = row.textContent.toLowerCase();
        row.style.display = text.includes(filter) ? '' : 'none';
      });
    });
  });
});