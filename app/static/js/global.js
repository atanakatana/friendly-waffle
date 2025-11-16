let AppState = {
  currentUser: null,
  ownerData: {},
  // Ganti 'catatanData' dan 'lapakSuppliers' dengan 'masterData' yang lebih komprehensif
  masterData: {
    suppliers: [],
    products: []
  },
};
let pendapatanChartInstance = null;
let biayaChartInstance = null;
let modals = {};

// fungsi core dan helper

function formatCurrency(value) {
  return `Rp ${new Intl.NumberFormat("id-ID").format(value)}`;
}
function formatNumberInput(e) {
  let input = e.target;
  // 1. Ambil nilai input dan hapus semua karakter selain angka
  let value = input.value.replace(/\D/g, '');

  // 2. Jika nilainya kosong, biarkan kosong
  if (value === "") {
    input.value = "";
    return;
  }

  // 3. Ubah menjadi angka, lalu format dengan pemisah ribuan (titik)
  let formattedValue = new Intl.NumberFormat('id-ID').format(value);

  // 4. Setel kembali nilai input dengan yang sudah diformat
  input.value = formattedValue;
}
// --- HELPER & CORE FUNCTIONS ---

function manageFooterVisibility() {
  const footer = document.getElementById('rekap-footer');
  const handle = document.getElementById('footer-handle');
  const icon = document.getElementById('footer-toggle-icon');

  // --- BARIS DIAGNOSTIK ---
  // Kita cek dulu apakah elemennya ditemukan
  if (!handle) {
    console.error("DEBUG: Elemen #footer-handle TIDAK DITEMUKAN!");
    return;
  }
  console.log("DEBUG: Elemen #footer-handle ditemukan, event listener dipasang.");
  // --- AKHIR BARIS DIAGNOSTIK ---

  handle.onclick = function () {
    // --- BARIS DIAGNOSTIK ---
    console.log("DEBUG: Footer handle DIKLIK!");
    // --- AKHIR BARIS DIAGNOSTIK ---

    footer.classList.toggle('footer-hidden');

    if (footer.classList.contains('footer-hidden')) {
      icon.classList.remove('bi-chevron-down');
      icon.classList.add('bi-chevron-up');
    } else {
      icon.classList.remove('bi-chevron-up');
      icon.classList.add('bi-chevron-down');
    }
  };
}

function updateDate() {
  const today = new Date().toLocaleDateString("id-ID", {
    weekday: "long",
    year: "numeric",
    month: "long",
    day: "numeric",
  });
  [
    "current-date-lapak",
    "current-date-owner",
    "current-date-supplier",
  ].forEach((id) => {
    if (document.getElementById(id))
      document.getElementById(id).textContent = today;
  });
}
function showToast(message, isSuccess = true) {
  const toastEl = document.getElementById("liveToast");
  if (!toastEl) return;
  const toast = bootstrap.Toast.getOrCreateInstance(toastEl);
  document.getElementById("toast-body").textContent = message;
  toastEl.className = `toast ${isSuccess ? "bg-success" : "bg-danger"
    } text-white`;
  document.getElementById("toast-icon").className = `bi ${isSuccess ? "bi-check-circle-fill" : "bi-exclamation-triangle-fill"
    } me-2`;
  document.getElementById("toast-title").textContent = isSuccess
    ? "Sukses"
    : "Gagal";
  toast.show();
}
function togglePasswordVisibility(button, fieldId) {
  const field = document.getElementById(fieldId);
  const icon = button.querySelector("i");
  if (field.type === "password") {
    field.type = "text";
    icon.classList.replace("bi-eye-slash", "bi-eye");
  } else {
    field.type = "password";
    icon.classList.replace("bi-eye", "bi-eye-slash");
  }
}
function toggleTablePasswordVisibility(icon) {
  const passSpan = icon.closest("td").querySelector(".password-text");
  if (passSpan.textContent.includes("•")) {
    passSpan.textContent = passSpan.dataset.password;
    icon.classList.replace("bi-eye-slash", "bi-eye");
  } else {
    passSpan.textContent = "••••••••";
    icon.classList.replace("bi-eye", "bi-eye-slash");
  }
}

// logika otentikasi dan routing
async function handleLogin(e) {
  e.preventDefault();
  const username = document.getElementById("username").value.trim(),
    password = document.getElementById("password").value;
  try {
    const response = await fetch("/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    const result = await response.json();
    if (response.ok && result.success) {
      localStorage.setItem("userSession", JSON.stringify(result));
      AppState.currentUser = result;
      await routeUser(result.role);
    } else {
      showToast(result.message || "Login Gagal", false);
    }
  } catch (e) {
    showToast("Terjadi kesalahan koneksi.", false);
  }
}
async function handleAuthRouting() {
  const session = localStorage.getItem("userSession");
  if (session) {
    AppState.currentUser = JSON.parse(session);
    await routeUser(AppState.currentUser.role);
  } else {
    showLoginPage();
  }
}
function showLoginPage() {
  document
    .querySelectorAll("main")
    .forEach((main) => (main.style.display = "none"));
  showPage("login-page");
}
async function routeUser(role) {
  document
    .querySelectorAll("main")
    .forEach((main) => (main.style.display = "none"));
  if (role === "owner") {
    document.getElementById("owner-pages").style.display = "block";
    showPage("owner-dashboard");
    document.getElementById("owner-name").textContent =
      AppState.currentUser.user_info.nama_lengkap;
  } else if (role === "lapak") {
    document.getElementById("lapak-pages").style.display = "block";
    document.getElementById("lapak-name").textContent =
      AppState.currentUser.user_info.nama_lengkap;
    showPage("lapak-dashboard");
  } else if (role === "supplier") {
    document.getElementById("supplier-pages").style.display = "block";
    showPage("supplier-dashboard");
    document.getElementById("supplier-name").textContent =
      AppState.currentUser.user_info.nama_supplier;
  } else if (role === "superowner") {
    document.getElementById("superowner-pages").style.display = "block";
    showPage("superowner-dashboard");
    // Update tanggal untuk dashboard baru
    if (document.getElementById("current-date-superowner")) {
      document.getElementById("current-date-superowner").textContent = new Date().toLocaleDateString("id-ID", {
        weekday: "long", year: "numeric", month: "long", day: "numeric",
      });
    }

  } else {
    showLoginPage();
  }
}
function handleLogout() {
  // Bersihkan juga saat logout
  if (AppState.currentUser && AppState.currentUser.role === 'lapak') {
    const storageKey = `reportState_${AppState.currentUser.user_info.lapak_id}`;
    localStorage.removeItem(storageKey);
  }
  localStorage.removeItem("userSession");
  AppState.currentUser = null;
  window.location.reload();
}

// Inisialisasi modals setelah DOM siap (listener global)
document.addEventListener("DOMContentLoaded", () => {
  modals.admin = new bootstrap.Modal(
    document.getElementById("edit-admin-modal")
  );
  modals.lapak = new bootstrap.Modal(
    document.getElementById("edit-lapak-modal")
  );
  modals.supplier = new bootstrap.Modal(
    document.getElementById("edit-supplier-modal")
  );
  modals.payment = new bootstrap.Modal(
    document.getElementById("payment-confirmation-modal")
  );
  modals.reportDetail = new bootstrap.Modal(
    document.getElementById("report-detail-modal")
  );
  modals.aturProduk = new bootstrap.Modal(
    document.getElementById("atur-produk-modal")
  );
  modals.withdraw = new bootstrap.Modal(document.getElementById("superowner-withdraw-modal")
  );
  modals.superownerEditOwner = new bootstrap.Modal(document.getElementById("superowner-edit-owner-modal")
  );

  // listener untuk form login
  document.getElementById("login-form")?.addEventListener("submit", handleLogin);

  // fungsi global yang berjalan saat load
  manageFooterVisibility();
  handleAuthRouting();
  updateDate();
});