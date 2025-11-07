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