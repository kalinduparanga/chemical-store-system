/**
 * Chemical Store Management System - Frontend Application Logic
 * Communicates with FastAPI backend REST endpoints and SQLite database.
 */

let currentUser = {
  username: "storekeeper",
  full_name: "Samitha K. (Storekeeper)",
  role: "Storekeeper"
};

let authToken = localStorage.getItem("chemstore_token") || "";

// Cache for dropdowns
let cachedChemicals = [];
let cachedLocations = [];
let cachedSuppliers = [];
let cachedBatches = [];
let cachedBarrels = [];

// Initialize on window load
window.addEventListener("DOMContentLoaded", async () => {
  startLiveClock();
  setupDefaultDates();
  await checkAuthStatus();
  await loadGlobalMasterData();
  await refreshDashboard();
  switchTab("dashboard");
});

function startLiveClock() {
  const updateClock = () => {
    const now = new Date();
    const timeEl = document.getElementById("live-clock-time");
    const dateEl = document.getElementById("live-clock-date");
    if (timeEl) timeEl.textContent = now.toLocaleTimeString('en-US', { hour12: true });
    if (dateEl) dateEl.textContent = now.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  };
  updateClock();
  setInterval(updateClock, 1000);
}

function setupDefaultDates() {
  const today = new Date().toISOString().split("T")[0];
  const nowTime = new Date().toTimeString().split(" ")[0].substring(0, 5);

  const setVal = (id, val) => {
    const el = document.getElementById(id);
    if (el) el.value = val;
  };

  setVal("daily-date", today);
  setVal("daily-time", nowTime);
  setVal("usage-date", today);
  setVal("rcv-date", today);
  setVal("rcv-mfg-date", today);

  const exp6m = new Date();
  exp6m.setMonth(exp6m.getMonth() + 6);
  const exp6mStr = exp6m.toISOString().split("T")[0];

  const exp1y = new Date();
  exp1y.setFullYear(exp1y.getFullYear() + 1);
  const exp1yStr = exp1y.toISOString().split("T")[0];

  setVal("rcv-exp-date", exp1yStr);
  setVal("prep-date", today);
  setVal("prep-exp-date", exp6mStr);
  setVal("modal-prep-date", today);
  setVal("modal-prep-exp", exp6mStr);
}

// --- AUTHENTICATION & HEADERS ---
function getAuthHeaders() {
  const headers = { "Content-Type": "application/json" };
  if (authToken) {
    headers["Authorization"] = `Bearer ${authToken}`;
  }
  return headers;
}

async function checkAuthStatus() {
  try {
    const res = await fetch("/api/auth/me", { headers: getAuthHeaders() });
    if (res.ok) {
      currentUser = await res.json();
      updateUserUI();
    }
  } catch (err) {
    console.warn("Auth check fallback:", err);
  }
}

async function loginAs(username, password) {
  try {
    const res = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password })
    });
    if (!res.ok) {
      showToast("Authentication failed", "error");
      return;
    }
    const data = await res.json();
    authToken = data.access_token;
    localStorage.setItem("chemstore_token", authToken);
    currentUser = data.user;
    updateUserUI();
    closeModal("modal-role-switch");
    showToast(`Logged in as ${currentUser.full_name} (${currentUser.role})`, "success");
    await refreshDashboard();
  } catch (err) {
    showToast("Login error: " + err.message, "error");
  }
}

function updateUserUI() {
  const nameEl = document.getElementById("current-user-name");
  const roleEl = document.getElementById("current-user-role");
  const badgeEl = document.getElementById("user-avatar-badge");

  if (nameEl) nameEl.textContent = currentUser.full_name;
  if (roleEl) roleEl.textContent = currentUser.role;
  if (badgeEl) {
    const initials = currentUser.full_name.split(" ").map(w => w[0]).join("").substring(0, 2).toUpperCase();
    badgeEl.textContent = initials || "SK";
  }

  // Set default inspector/operator fields
  const dailyOp = document.getElementById("daily-operator");
  if (dailyOp) dailyOp.value = currentUser.full_name;
  const prepOp = document.getElementById("prep-operator");
  if (prepOp) prepOp.value = currentUser.full_name;
}

// --- MASTER DATA CACHING ---
async function loadGlobalMasterData() {
  try {
    const [chemRes, locRes, suppRes] = await Promise.all([
      fetch("/api/inventory/chemicals"),
      fetch("/api/inventory/locations"),
      fetch("/api/inventory/suppliers")
    ]);

    if (chemRes.ok) cachedChemicals = await chemRes.json();
    if (locRes.ok) cachedLocations = await locRes.json();
    if (suppRes.ok) cachedSuppliers = await suppRes.json();

    populateStaticDropdowns();
  } catch (err) {
    console.error("Error loading master data:", err);
  }
}

function populateStaticDropdowns() {
  // Usage Chemical Select
  const usageChem = document.getElementById("usage-chem-select");
  if (usageChem) {
    usageChem.innerHTML = `<option value="">-- Choose Chemical --</option>` +
      cachedChemicals.map(c => `<option value="${c.id}">${c.name}</option>`).join("");
  }

  // Receiving Chemical & Location & Supplier
  const rcvChem = document.getElementById("rcv-chem");
  if (rcvChem) {
    rcvChem.innerHTML = cachedChemicals.map(c => `<option value="${c.id}">${c.name}</option>`).join("");
  }
  const rcvLoc = document.getElementById("rcv-location");
  if (rcvLoc) {
    rcvLoc.innerHTML = cachedLocations.map(l => `<option value="${l.id}">${l.name}</option>`).join("");
  }
  const rcvSupp = document.getElementById("rcv-supplier");
  if (rcvSupp) {
    rcvSupp.innerHTML = cachedSuppliers.map(s => `<option value="${s.id}">${s.name}</option>`).join("");
  }

  // Transfer Chemical & Locations
  const trfChem = document.getElementById("trf-chem");
  if (trfChem) {
    trfChem.innerHTML = `<option value="">-- Choose Chemical --</option>` +
      cachedChemicals.map(c => `<option value="${c.id}">${c.name}</option>`).join("");
  }
  const trfSrc = document.getElementById("trf-source");
  const trfDest = document.getElementById("trf-dest");
  if (trfSrc && trfDest) {
    const locOpts = cachedLocations.map(l => `<option value="${l.id}">${l.name}</option>`).join("");
    trfSrc.innerHTML = locOpts;
    trfDest.innerHTML = locOpts;
  }

  // History Filter Chemical
  const histChem = document.getElementById("hist-chem-filter");
  if (histChem) {
    histChem.innerHTML = `<option value="">All Chemicals</option>` +
      cachedChemicals.map(c => `<option value="${c.id}">${c.name}</option>`).join("");
  }
}

// --- TAB ROUTING ---
function switchTab(tabId) {
  document.querySelectorAll(".view-panel").forEach(p => p.classList.add("hidden"));
  document.querySelectorAll(".nav-btn").forEach(b => {
    b.classList.remove("bg-slate-100", "text-cyan-700", "font-bold");
  });

  const targetView = document.getElementById(`view-${tabId}`);
  if (targetView) targetView.classList.remove("hidden");

  const activeNav = document.getElementById(`nav-${tabId}`);
  if (activeNav) activeNav.classList.add("bg-slate-100", "text-cyan-700", "font-bold");

  const titleMap = {
    "dashboard": "Dashboard Overview",
    "daily-entry": "Daily Morning Physical Verification (Ammonia Only)",
    "usage": "Chemical Usage Ledger",
    "receiving": "Chemical Receiving & GRN",
    "transfers": "Location Stock Transfers",
    "ammonia-barrels": "25% Ammonia Barrel Stock Tracking",
    "ammonia-ready": "Ready-to-Use 25% Ammonia Store",
    "ammonia-10-stock": "10% Ammonia Diluted Stock",
    "ammonia-prep": "10% Ammonia Preparation (Fixed Ratio)",
    "chemicals": "Chemicals Master Inventory",
    "batches": "Batch & Expiry Management",
    "reports": "Store Reports & Analytics",
    "history": "Historical Transaction Traceability Log",
    "alerts": "Stock & Expiry Alert Center",
    "settings": "System Settings & Configuration"
  };

  const titleEl = document.getElementById("current-page-title");
  if (titleEl) titleEl.textContent = titleMap[tabId] || "Chemical Store Management System";

  // Tab-specific loaders
  if (tabId === "dashboard") refreshDashboard();
  else if (tabId === "daily-entry") loadDailyMorningData();
  else if (tabId === "usage") loadUsageTable();
  else if (tabId === "receiving") loadReceivingTable();
  else if (tabId === "transfers") loadTransfersTable();
  else if (tabId === "ammonia-barrels") loadAmmoniaBarrels();
  else if (tabId === "ammonia-ready") loadReady25Ammonia();
  else if (tabId === "ammonia-10-stock") loadAmmonia10Stock();
  else if (tabId === "ammonia-prep") populatePrepBarrelSelect();
  else if (tabId === "chemicals") loadChemicalsMaster();
  else if (tabId === "batches") loadBatchesTable();
  else if (tabId === "reports") selectReportTab("daily");
  else if (tabId === "history") loadHistoricalTransactions();
  else if (tabId === "alerts") loadAlertsCenter();
  else if (tabId === "settings") loadSettingsPage();

  if (window.lucide) lucide.createIcons();
}

// --- DASHBOARD LOADER ---
async function refreshDashboard() {
  try {
    const res = await fetch("/api/inventory/dashboard");
    if (!res.ok) return;
    const d = await res.json();

    document.getElementById("dash-kpi-chem-count").textContent = `${d.total_chemicals} Chemicals`;
    document.getElementById("dash-kpi-barrels").textContent = `${d.barrel_stock.full_barrels} Barrels`;
    document.getElementById("dash-kpi-barrel-kg").textContent = `${d.barrel_stock.total_kg.toLocaleString()} kg`;
    document.getElementById("dash-kpi-10-stock").textContent = `${d.ammonia_10_kg.toLocaleString()} kg`;
    document.getElementById("dash-kpi-alerts").textContent = `${d.expiring_batches_count + d.low_stock_count} Items`;

    document.getElementById("snap-barrel-count").textContent = `${d.barrel_stock.full_barrels} Full Barrels`;
    document.getElementById("snap-barrel-weight").textContent = `${d.barrel_stock.total_kg.toLocaleString()} kg`;
    document.getElementById("snap-ready-qty").textContent = `${d.ready_25_kg.toFixed(2)} kg`;
    document.getElementById("snap-10-qty").textContent = `${d.ammonia_10_kg.toFixed(2)} kg`;

    document.getElementById("badge-barrel-count").textContent = `${d.barrel_stock.total_barrels} Barrels`;
    document.getElementById("badge-alert-count").textContent = d.expiring_batches_count + d.low_stock_count;

    // Morning check status badge
    const physStatusBadge = document.getElementById("dash-today-physical-status");
    if (physStatusBadge) {
      if (d.has_today_physical_stock) {
        physStatusBadge.textContent = "Verified Today";
        physStatusBadge.className = "px-2 py-0.5 text-[10px] font-bold rounded bg-emerald-100 text-emerald-800 border border-emerald-200";
      } else {
        physStatusBadge.textContent = "Pending Morning Check";
        physStatusBadge.className = "px-2 py-0.5 text-[10px] font-bold rounded bg-amber-100 text-amber-800 border border-amber-200 animate-pulse";
      }
    }

    // Morning check summary cards
    const morningSummary = document.getElementById("dash-morning-summary");
    if (morningSummary) {
      morningSummary.innerHTML = `
        <div class="p-2.5 bg-slate-50 rounded-lg border border-slate-200 flex justify-between items-center text-xs">
          <div>
            <span class="text-slate-800 font-bold block">25% Barrel Store</span>
            <span class="text-[10px] text-slate-500 font-mono">${d.barrel_stock.full_barrels} Barrels (${d.barrel_stock.total_kg} kg)</span>
          </div>
          <span class="px-2 py-0.5 text-[10px] font-bold rounded ${d.has_today_physical_stock ? 'bg-emerald-100 text-emerald-800' : 'bg-slate-200 text-slate-700'}">
            ${d.has_today_physical_stock ? 'Logged' : 'Pending'}
          </span>
        </div>
        <div class="p-2.5 bg-slate-50 rounded-lg border border-slate-200 flex justify-between items-center text-xs">
          <div>
            <span class="text-slate-800 font-bold block">Ready-to-Use 25% Store</span>
            <span class="text-[10px] text-slate-500 font-mono">${d.ready_25_kg.toFixed(2)} kg</span>
          </div>
          <span class="px-2 py-0.5 text-[10px] font-bold rounded ${d.has_today_physical_stock ? 'bg-emerald-100 text-emerald-800' : 'bg-slate-200 text-slate-700'}">
            ${d.has_today_physical_stock ? 'Logged' : 'Pending'}
          </span>
        </div>
        <div class="p-2.5 bg-slate-50 rounded-lg border border-slate-200 flex justify-between items-center text-xs">
          <div>
            <span class="text-slate-800 font-bold block">10% Ammonia Store</span>
            <span class="text-[10px] text-slate-500 font-mono">${d.ammonia_10_kg.toFixed(2)} kg</span>
          </div>
          <span class="px-2 py-0.5 text-[10px] font-bold rounded ${d.has_today_physical_stock ? 'bg-emerald-100 text-emerald-800' : 'bg-slate-200 text-slate-700'}">
            ${d.has_today_physical_stock ? 'Logged' : 'Pending'}
          </span>
        </div>
      `;
    }

    // Recent 25% Barrel History Table
    const barrelHistTbody = document.getElementById("dash-table-barrel-history");
    if (barrelHistTbody) {
      if (!d.recent_barrel_activity || d.recent_barrel_activity.length === 0) {
        barrelHistTbody.innerHTML = `<tr><td colspan="7" class="p-3 text-center text-slate-400">No barrel transactions recorded yet</td></tr>`;
      } else {
        barrelHistTbody.innerHTML = d.recent_barrel_activity.map(b => `
          <tr class="hover:bg-slate-50">
            <td class="p-2.5 font-mono text-[11px] text-slate-500">${b.action_date}</td>
            <td class="p-2.5 font-mono font-bold text-amber-700">${b.barrel_id}</td>
            <td class="p-2.5 font-mono text-slate-700">${b.batch_number}</td>
            <td class="p-2.5 text-right font-mono font-bold text-rose-600">-${b.used_or_transferred_quantity.toFixed(1)} kg</td>
            <td class="p-2.5 text-slate-800">${b.usage_purpose}</td>
            <td class="p-2.5 text-slate-500">${b.supplier_customer_name || '—'}</td>
            <td class="p-2.5 text-right font-mono font-bold text-emerald-700">${b.remaining_quantity.toFixed(1)} kg</td>
          </tr>
        `).join("");
      }
    }

    // Recent Usage Table
    const usageTbody = document.getElementById("dash-table-usage");
    if (usageTbody) {
      if (!d.recent_usage || d.recent_usage.length === 0) {
        usageTbody.innerHTML = `<tr><td colspan="5" class="p-3 text-center text-slate-400">No usage records yet</td></tr>`;
      } else {
        usageTbody.innerHTML = d.recent_usage.map(u => `
          <tr class="hover:bg-slate-50">
            <td class="p-2.5 font-mono text-[11px] text-slate-500">${u.date} <span class="text-slate-400 text-[10px]">${u.time}</span></td>
            <td class="p-2.5 font-bold text-slate-900">${u.chemical_name}</td>
            <td class="p-2.5 font-mono text-cyan-700 font-bold">${u.batch_number}</td>
            <td class="p-2.5 text-right font-mono font-bold text-rose-600">-${u.quantity_used.toFixed(2)} ${u.unit}</td>
            <td class="p-2.5 text-slate-700">${u.purpose}</td>
          </tr>
        `).join("");
      }
    }

    // Alerts Snapshot List
    const alertsList = document.getElementById("dash-alerts-list");
    if (alertsList) {
      const alertRes = await fetch("/api/inventory/alerts");
      if (alertRes.ok) {
        const al = await alertRes.json();
        const items = [];
        al.expiry_alerts.slice(0, 2).forEach(a => {
          items.push(`
            <div class="p-2.5 bg-amber-50 rounded-lg border border-amber-200 text-xs">
              <span class="font-bold text-amber-900 block">${a.chemical_name} (${a.batch_number})</span>
              <p class="text-[11px] text-amber-800 mt-0.5">Expiring in ${a.days_remaining} days (${a.expiry_date}). Available: ${a.current_quantity} ${a.unit}</p>
            </div>
          `);
        });
        al.low_stock_alerts.slice(0, 2).forEach(l => {
          items.push(`
            <div class="p-2.5 bg-rose-50 rounded-lg border border-rose-200 text-xs">
              <span class="font-bold text-rose-900 block">${l.chemical_name} - Low Stock</span>
              <p class="text-[11px] text-rose-800 mt-0.5">Current: ${l.current_stock.toFixed(1)} ${l.default_unit} (Minimum: ${l.min_stock_level} ${l.default_unit})</p>
            </div>
          `);
        });
        alertsList.innerHTML = items.length > 0 ? items.join("") : `<p class="text-xs text-slate-400">No active stock or expiry alerts</p>`;
      }
    }

    if (window.lucide) lucide.createIcons();
  } catch (err) {
    console.error("Dashboard refresh error:", err);
  }
}

// --- DAILY MORNING PHYSICAL STOCK ---
async function loadDailyMorningData() {
  try {
    const res = await fetch("/api/physical-stock/current-system");
    if (!res.ok) return;
    const items = await res.json();

    const tbody = document.getElementById("daily-entry-table-body");
    tbody.innerHTML = items.map((item, idx) => `
      <tr class="hover:bg-slate-50">
        <td class="p-3 font-bold text-slate-900">
          ${item.storage_location_name}
          <span class="block text-[10px] text-slate-500 font-normal">${item.chemical_name} ${item.extra_info ? '&bull; ' + item.extra_info : ''}</span>
          <input type="hidden" name="loc_id_${idx}" value="${item.storage_location_id}">
          <input type="hidden" name="chem_id_${idx}" value="${item.chemical_id}">
          <input type="hidden" id="sys_val_${idx}" value="${item.system_quantity}">
        </td>
        <td class="p-3 font-mono text-slate-500">${item.unit}</td>
        <td class="p-3 text-right font-mono text-slate-800 font-semibold">${item.system_quantity.toFixed(2)} ${item.unit}</td>
        <td class="p-3 text-right">
          <input type="number" step="0.01" id="phys_val_${idx}" value="${item.system_quantity.toFixed(2)}" oninput="calcMorningVariance(${idx})" class="w-32 text-right bg-white border border-slate-300 rounded px-2.5 py-1.5 font-mono text-xs text-slate-900 focus:border-cyan-600 font-bold" required>
        </td>
        <td class="p-3 text-right font-mono font-bold" id="var_display_${idx}">
          <span class="text-emerald-700">0.00 ${item.unit}</span>
        </td>
        <td class="p-3">
          <input type="text" id="rem_val_${idx}" placeholder="e.g. Tank level confirmed" class="w-full bg-white border border-slate-200 rounded px-2.5 py-1 text-xs text-slate-800">
        </td>
      </tr>
    `).join("");

    loadDailyHistoryTable();
  } catch (err) {
    console.error("Error loading daily morning stock data:", err);
  }
}

function calcMorningVariance(idx) {
  const sysVal = parseFloat(document.getElementById(`sys_val_${idx}`).value) || 0;
  const physVal = parseFloat(document.getElementById(`phys_val_${idx}`).value) || 0;
  const variance = physVal - sysVal;
  const dispEl = document.getElementById(`var_display_${idx}`);

  if (variance === 0) {
    dispEl.innerHTML = `<span class="text-emerald-700 font-bold">0.00 kg</span>`;
  } else if (variance > 0) {
    dispEl.innerHTML = `<span class="text-cyan-700 font-bold">+${variance.toFixed(2)} kg</span>`;
  } else {
    dispEl.innerHTML = `<span class="text-rose-600 font-bold">${variance.toFixed(2)} kg</span>`;
  }
}

async function handleDailyStockSubmit(e) {
  e.preventDefault();
  const dateVal = document.getElementById("daily-date").value;
  const timeVal = document.getElementById("daily-time").value;
  const opVal = document.getElementById("daily-operator").value;

  const rows = document.querySelectorAll("#daily-entry-table-body tr");
  const entries = [];

  rows.forEach((row, idx) => {
    const locId = parseInt(row.querySelector(`input[name="loc_id_${idx}"]`).value);
    const chemId = parseInt(row.querySelector(`input[name="chem_id_${idx}"]`).value);
    const physQty = parseFloat(document.getElementById(`phys_val_${idx}`).value);
    const remarks = document.getElementById(`rem_val_${idx}`).value;

    entries.push({
      storage_location_id: locId,
      chemical_id: chemId,
      physical_quantity: physQty,
      remarks: remarks
    });
  });

  try {
    const res = await fetch("/api/physical-stock", {
      method: "POST",
      headers: getAuthHeaders(),
      body: JSON.stringify({
        date: dateVal,
        time: timeVal ? timeVal + ":00" : undefined,
        operator_name: opVal,
        entries: entries
      })
    });

    if (!res.ok) {
      const err = await res.json();
      showToast(err.detail || "Error saving physical stock check", "error");
      return;
    }

    showToast("Morning Physical Stock Verification logged successfully!", "success");
    loadDailyHistoryTable();
    refreshDashboard();
  } catch (err) {
    showToast("Submission failed: " + err.message, "error");
  }
}

async function loadDailyHistoryTable() {
  try {
    const res = await fetch("/api/physical-stock/history");
    if (!res.ok) return;
    const history = await res.json();

    const tbody = document.getElementById("daily-history-tbody");
    if (history.length === 0) {
      tbody.innerHTML = `<tr><td colspan="7" class="p-3 text-center text-slate-400">No daily morning records found</td></tr>`;
      return;
    }

    tbody.innerHTML = history.map(d => `
      <tr class="hover:bg-slate-50">
        <td class="p-2.5 font-mono text-[11px] text-slate-500">${d.date} <span class="text-slate-400">${d.time}</span></td>
        <td class="p-2.5 font-bold text-slate-900">${d.storage_location_name} <span class="text-slate-500 font-normal">(${d.chemical_name})</span></td>
        <td class="p-2.5 text-right font-mono text-slate-700">${d.system_quantity.toFixed(2)} ${d.unit}</td>
        <td class="p-2.5 text-right font-mono font-bold text-cyan-700">${d.physical_quantity.toFixed(2)} ${d.unit}</td>
        <td class="p-2.5 text-right font-mono font-bold ${d.variance < 0 ? 'text-rose-600' : d.variance > 0 ? 'text-cyan-700' : 'text-emerald-700'}">
          ${d.variance > 0 ? '+' : ''}${d.variance.toFixed(2)} ${d.unit}
        </td>
        <td class="p-2.5 text-slate-700">${d.remarks || '—'}</td>
        <td class="p-2.5 text-slate-500">${d.operator_name}</td>
      </tr>
    `).join("");
  } catch (err) {
    console.error("Error loading daily history:", err);
  }
}

// --- CHEMICAL USAGE ---
async function loadUsageTable() {
  try {
    const res = await fetch("/api/usage");
    if (!res.ok) return;
    const records = await res.json();

    const tbody = document.getElementById("usage-table-tbody");
    if (records.length === 0) {
      tbody.innerHTML = `<tr><td colspan="10" class="p-3 text-center text-slate-400">No chemical usage recorded yet</td></tr>`;
      return;
    }

    tbody.innerHTML = records.map(u => `
      <tr class="hover:bg-slate-50">
        <td class="p-3 font-mono text-slate-500">${u.date} <span class="text-slate-400 text-[10px]">${u.time}</span></td>
        <td class="p-3 font-bold text-slate-900">${u.chemical_name}</td>
        <td class="p-3 font-mono text-cyan-700 font-bold">${u.batch_number}</td>
        <td class="p-3 text-slate-600">${u.storage_location_name}</td>
        <td class="p-3 text-right font-mono font-bold text-rose-600">-${u.quantity_used.toFixed(2)} ${u.unit}</td>
        <td class="p-3 text-slate-800">${u.purpose}</td>
        <td class="p-3 text-slate-500">${u.supplier_customer_name || '—'}</td>
        <td class="p-3 font-mono text-slate-500">${u.reference_number}</td>
        <td class="p-3 text-slate-500">${u.remarks || '—'}</td>
        <td class="p-3 text-slate-500">${u.operator_name}</td>
      </tr>
    `).join("");
  } catch (err) {
    console.error("Error loading usage table:", err);
  }
}

function filterUsageTable() {
  const query = document.getElementById("usage-search-input").value.toLowerCase();
  const chemFilter = document.getElementById("usage-filter-chemical").value;
  const rows = document.querySelectorAll("#usage-table-tbody tr");

  rows.forEach(row => {
    const text = row.innerText.toLowerCase();
    const chemCell = row.children[1].innerText;
    const matchesQuery = text.includes(query);
    const matchesChem = chemFilter === "" || chemCell.includes(chemFilter);

    if (matchesQuery && matchesChem) row.style.display = "";
    else row.style.display = "none";
  });
}

async function populateUsageBatches() {
  const chemId = document.getElementById("usage-chem-select").value;
  const batchSel = document.getElementById("usage-batch-select");
  if (!chemId) {
    batchSel.innerHTML = `<option value="">Select chemical first</option>`;
    document.getElementById("usage-available-meta").value = "";
    return;
  }

  const res = await fetch(`/api/inventory/batches?chemical_id=${chemId}`);
  if (!res.ok) return;
  const batches = await res.json();
  const activeBatches = batches.filter(b => b.current_quantity > 0);

  cachedBatches = batches;

  if (activeBatches.length === 0) {
    batchSel.innerHTML = `<option value="">No available stock for this chemical</option>`;
    document.getElementById("usage-available-meta").value = "0.00 kg";
  } else {
    batchSel.innerHTML = activeBatches.map(b => 
      `<option value="${b.id}">${b.batch_number} (${b.current_quantity.toFixed(1)} ${b.unit} available &bull; ${b.storage_location_name})</option>`
    ).join("");
    updateUsageBatchMeta();
  }
}

function updateUsageBatchMeta() {
  const batchId = parseInt(document.getElementById("usage-batch-select").value);
  const batch = cachedBatches.find(b => b.id === batchId);
  const availEl = document.getElementById("usage-available-meta");
  if (batch && availEl) {
    availEl.value = `${batch.current_quantity.toFixed(2)} ${batch.unit} (${batch.storage_location_name})`;
  }
}

async function handleUsageSubmit(e) {
  e.preventDefault();
  const chemId = parseInt(document.getElementById("usage-chem-select").value);
  const batchId = parseInt(document.getElementById("usage-batch-select").value);
  const qtyUsed = parseFloat(document.getElementById("usage-qty").value);
  const purpose = document.getElementById("usage-purpose").value;
  const refNo = document.getElementById("usage-ref").value;
  const dateVal = document.getElementById("usage-date").value;
  const customer = document.getElementById("usage-customer").value;
  const remarks = document.getElementById("usage-remarks").value;

  const batch = cachedBatches.find(b => b.id === batchId);
  if (!batch) {
    showToast("Please select a valid active batch", "error");
    return;
  }

  if (qtyUsed > batch.current_quantity) {
    showToast(`Usage quantity (${qtyUsed} kg) exceeds available stock (${batch.current_quantity} kg)`, "error");
    return;
  }

  try {
    const res = await fetch("/api/usage", {
      method: "POST",
      headers: getAuthHeaders(),
      body: JSON.stringify({
        date: dateVal,
        chemical_id: chemId,
        batch_id: batchId,
        storage_location_id: batch.storage_location_id,
        quantity_used: qtyUsed,
        purpose: purpose,
        supplier_customer_name: customer,
        reference_number: refNo,
        remarks: remarks
      })
    });

    if (!res.ok) {
      const err = await res.json();
      showToast(err.detail || "Error recording usage", "error");
      return;
    }

    closeModal("modal-usage");
    showToast(`Successfully logged usage of ${qtyUsed} kg from Batch ${batch.batch_number}`, "success");
    loadUsageTable();
    refreshDashboard();
  } catch (err) {
    showToast("Submission failed: " + err.message, "error");
  }
}

// --- RECEIVING (GRN) ---
async function loadReceivingTable() {
  try {
    const res = await fetch("/api/receiving");
    if (!res.ok) return;
    const receipts = await res.json();

    const tbody = document.getElementById("receiving-table-tbody");
    if (receipts.length === 0) {
      tbody.innerHTML = `<tr><td colspan="10" class="p-3 text-center text-slate-400">No shipments received yet</td></tr>`;
      return;
    }

    tbody.innerHTML = receipts.map(r => `
      <tr class="hover:bg-slate-50">
        <td class="p-3 font-mono text-slate-500">${r.received_date}</td>
        <td class="p-3 font-mono font-bold text-blue-700">${r.grn_number}</td>
        <td class="p-3 font-bold text-slate-900">${r.chemical_name}</td>
        <td class="p-3 font-mono text-cyan-700 font-bold">${r.batch_number}</td>
        <td class="p-3 font-mono text-slate-500">${r.manufacturing_date || '—'}</td>
        <td class="p-3 font-mono text-slate-500">${r.expiry_date}</td>
        <td class="p-3 text-slate-800">${r.supplier_name}</td>
        <td class="p-3 text-right font-mono font-bold text-emerald-700">+${r.quantity.toFixed(1)} ${r.unit}</td>
        <td class="p-3 text-slate-600">${r.storage_location_name}</td>
        <td class="p-3 text-slate-500">${r.created_by}</td>
      </tr>
    `).join("");
  } catch (err) {
    console.error("Error loading receiving table:", err);
  }
}

function toggleReceivingBarrelNotice() {
  const chemSel = document.getElementById("rcv-chem");
  const selectedText = chemSel.options[chemSel.selectedIndex].text;
  const notice = document.getElementById("rcv-barrel-notice");
  if (selectedText.includes("25%") || selectedText.includes("Ammonia 25%")) {
    notice.classList.remove("hidden");
  } else {
    notice.classList.add("hidden");
  }
}

async function handleReceivingSubmit(e) {
  e.preventDefault();
  const chemId = parseInt(document.getElementById("rcv-chem").value);
  const batchNo = document.getElementById("rcv-batch").value;
  const grn = document.getElementById("rcv-grn").value;
  const qty = parseFloat(document.getElementById("rcv-qty").value);
  const rcvDate = document.getElementById("rcv-date").value;
  const mfgDate = document.getElementById("rcv-mfg-date").value || null;
  const expDate = document.getElementById("rcv-exp-date").value;
  const suppId = parseInt(document.getElementById("rcv-supplier").value);
  const locId = parseInt(document.getElementById("rcv-location").value);
  const remarks = document.getElementById("rcv-remarks").value;

  try {
    const res = await fetch("/api/receiving", {
      method: "POST",
      headers: getAuthHeaders(),
      body: JSON.stringify({
        chemical_id: chemId,
        batch_number: batchNo,
        grn_number: grn,
        quantity: qty,
        unit: "kg",
        received_date: rcvDate,
        manufacturing_date: mfgDate,
        expiry_date: expDate,
        supplier_id: suppId,
        storage_location_id: locId,
        remarks: remarks
      })
    });

    if (!res.ok) {
      const err = await res.json();
      showToast(err.detail || "Error saving shipment", "error");
      return;
    }

    const resp = await res.json();
    closeModal("modal-receiving");
    showToast(resp.message || "Shipment saved successfully!", "success");
    loadReceivingTable();
    refreshDashboard();
  } catch (err) {
    showToast("Submission failed: " + err.message, "error");
  }
}

// --- 25% AMMONIA BARRELS ---
async function loadAmmoniaBarrels() {
  try {
    const res = await fetch("/api/ammonia/barrels");
    if (!res.ok) return;
    const barrels = await res.json();
    cachedBarrels = barrels;

    const grid = document.getElementById("barrel-cards-grid");
    if (barrels.length === 0) {
      grid.innerHTML = `<div class="col-span-3 text-center p-6 text-slate-400">No 25% Ammonia barrels registered</div>`;
    } else {
      grid.innerHTML = barrels.map(b => {
        const percent = Math.round((b.current_quantity / b.original_quantity) * 100);
        let badgeColor = "bg-emerald-100 text-emerald-800 border-emerald-200";
        if (b.status === "Partial") badgeColor = "bg-amber-100 text-amber-800 border-amber-200";
        if (b.status.includes("Empty")) badgeColor = "bg-slate-100 text-slate-500 border-slate-200";

        return `
          <div class="glass-card p-4 rounded-xl border border-slate-200 space-y-3 relative overflow-hidden">
            <div class="flex justify-between items-start">
              <div>
                <span class="text-[10px] font-mono text-amber-700 font-bold uppercase tracking-wider block">${b.barrel_id}</span>
                <h4 class="font-bold text-sm text-slate-900 font-mono mt-0.5">${b.batch_number}</h4>
              </div>
              <span class="px-2 py-0.5 text-[10px] rounded font-bold border ${badgeColor}">
                ${b.status}
              </span>
            </div>

            <div class="space-y-1">
              <div class="flex justify-between text-xs font-mono">
                <span class="text-slate-500">Current Quantity:</span>
                <span class="text-slate-900 font-bold">${b.current_quantity.toFixed(1)} / ${b.original_quantity.toFixed(1)} kg</span>
              </div>
              <div class="w-full bg-slate-100 h-2 rounded-full overflow-hidden border border-slate-200">
                <div class="bg-amber-500 h-full transition-all duration-500" style="width: ${percent}%"></div>
              </div>
            </div>

            <div class="grid grid-cols-2 gap-2 text-[10px] text-slate-500 border-t border-slate-200 pt-2 font-mono">
              <div>Supplier: <span class="text-slate-800 block truncate font-sans font-medium">${b.supplier_name || '—'}</span></div>
              <div>Expiry: <span class="text-slate-800 block font-sans font-medium">${b.expiry_date}</span></div>
            </div>

            <div class="pt-1 flex justify-end">
              <button onclick="openBarrelModalWithId('${b.barrel_id}')" class="px-3 py-1 bg-amber-50 hover:bg-amber-100 text-amber-800 border border-amber-300 rounded text-xs font-bold flex items-center gap-1 transition">
                <i data-lucide="edit-2" class="w-3 h-3"></i> Use / Transfer
              </button>
            </div>
          </div>
        `;
      }).join("");
    }

    loadBarrelHistoryLedger();
    if (window.lucide) lucide.createIcons();
  } catch (err) {
    console.error("Error loading ammonia barrels:", err);
  }
}

async function loadBarrelHistoryLedger() {
  try {
    const res = await fetch("/api/ammonia/barrel-history");
    if (!res.ok) return;
    const history = await res.json();

    const tbody = document.getElementById("barrel-history-tbody");
    if (history.length === 0) {
      tbody.innerHTML = `<tr><td colspan="11" class="p-3 text-center text-slate-400">No barrel transactions recorded</td></tr>`;
      return;
    }

    tbody.innerHTML = history.map(h => `
      <tr class="hover:bg-slate-50">
        <td class="p-2.5 font-mono text-[11px] text-slate-500">${h.action_date} <span class="text-slate-400">${h.action_time}</span></td>
        <td class="p-2.5 font-mono font-bold text-amber-700">${h.barrel_id}</td>
        <td class="p-2.5 font-mono text-slate-800 font-semibold">${h.batch_number}</td>
        <td class="p-2.5 text-right font-mono text-slate-600">${h.original_quantity.toFixed(1)} kg</td>
        <td class="p-2.5 text-right font-mono font-bold text-rose-600">-${h.used_or_transferred_quantity.toFixed(1)} kg</td>
        <td class="p-2.5 text-right font-mono font-bold text-emerald-700">${h.remaining_quantity.toFixed(1)} kg</td>
        <td class="p-2.5 text-slate-800">${h.usage_purpose}</td>
        <td class="p-2.5 text-slate-500">${h.supplier_customer_name || '—'}</td>
        <td class="p-2.5 text-slate-500">${h.destination || '—'}</td>
        <td class="p-2.5 font-mono text-slate-500">${h.reference_number || '—'}</td>
        <td class="p-2.5 text-slate-500">${h.operator_name}</td>
      </tr>
    `).join("");
  } catch (err) {
    console.error("Error loading barrel history ledger:", err);
  }
}

function openBarrelModalWithId(barrelId) {
  const sel = document.getElementById("bu-select-barrel");
  sel.innerHTML = cachedBarrels
    .filter(b => b.current_quantity > 0)
    .map(b => `<option value="${b.barrel_id}">${b.barrel_id} | Batch: ${b.batch_number} (${b.current_quantity.toFixed(1)} kg available)</option>`)
    .join("");

  sel.value = barrelId;
  updateBarrelModalMeta();
  openModal("modal-barrel-usage");
}

function updateBarrelModalMeta() {
  const barrelId = document.getElementById("bu-select-barrel").value;
  const barrel = cachedBarrels.find(b => b.barrel_id === barrelId);
  if (barrel) {
    document.getElementById("bu-orig-qty").value = `${barrel.original_quantity.toFixed(2)} kg`;
    document.getElementById("bu-curr-qty").value = `${barrel.current_quantity.toFixed(2)} kg`;
    document.getElementById("bu-used-qty").value = barrel.current_quantity;
    calcBarrelRemaining();
  }
}

function calcBarrelRemaining() {
  const barrelId = document.getElementById("bu-select-barrel").value;
  const barrel = cachedBarrels.find(b => b.barrel_id === barrelId);
  const used = parseFloat(document.getElementById("bu-used-qty").value) || 0;
  if (barrel) {
    const rem = Math.max(0, barrel.current_quantity - used);
    document.getElementById("bu-rem-qty").value = `${rem.toFixed(2)} kg`;
  }
}

function toggleCustomerSupplierField() {
  const purpose = document.getElementById("bu-purpose").value;
  const wrapper = document.getElementById("bu-customer-wrapper");
  if (purpose === "Latex Supplier / Customer Supply" || purpose === "25% Ammonia Usage") {
    wrapper.classList.remove("hidden");
  } else {
    wrapper.classList.add("hidden");
  }
}

async function handleBarrelUsageSubmit(e) {
  e.preventDefault();
  const barrelId = document.getElementById("bu-select-barrel").value;
  const usedQty = parseFloat(document.getElementById("bu-used-qty").value);
  const purpose = document.getElementById("bu-purpose").value;
  const customer = document.getElementById("bu-customer").value;
  const refNo = document.getElementById("bu-ref").value;
  const dest = document.getElementById("bu-dest").value;
  const remarks = document.getElementById("bu-remarks").value;

  try {
    const res = await fetch("/api/ammonia/barrel-usage", {
      method: "POST",
      headers: getAuthHeaders(),
      body: JSON.stringify({
        barrel_id: barrelId,
        quantity_used: usedQty,
        usage_purpose: purpose,
        supplier_customer_name: customer,
        destination: dest,
        reference_number: refNo,
        remarks: remarks
      })
    });

    if (!res.ok) {
      const err = await res.json();
      showToast(err.detail || "Error updating barrel", "error");
      return;
    }

    const resp = await res.json();
    closeModal("modal-barrel-usage");
    showToast(resp.message || "Barrel updated successfully!", "success");
    loadAmmoniaBarrels();
    refreshDashboard();
  } catch (err) {
    showToast("Submission failed: " + err.message, "error");
  }
}

// --- READY TO USE 25% AMMONIA ---
async function loadReady25Ammonia() {
  try {
    const res = await fetch("/api/ammonia/ready-stock");
    if (!res.ok) return;
    const data = await res.json();

    document.getElementById("ready-store-total").textContent = `${data.total_quantity.toFixed(2)} kg`;
    const tbody = document.getElementById("ready-batches-tbody");

    if (data.batches.length === 0) {
      tbody.innerHTML = `<tr><td colspan="6" class="p-3 text-center text-slate-400">No active stock in Ready-to-Use 25% Ammonia Store</td></tr>`;
      return;
    }

    tbody.innerHTML = data.batches.map(b => `
      <tr class="hover:bg-slate-50">
        <td class="p-2.5 font-bold text-slate-900 font-mono">${b.batch_number}</td>
        <td class="p-2.5 text-slate-600">${b.expiry_date}</td>
        <td class="p-2.5 text-right font-mono">${b.received_quantity.toFixed(2)} kg</td>
        <td class="p-2.5 text-right font-mono font-bold text-blue-600">${b.current_quantity.toFixed(2)} kg</td>
        <td class="p-2.5"><span class="px-2 py-0.5 rounded text-[10px] bg-emerald-100 text-emerald-800 font-bold border border-emerald-200">${b.status}</span></td>
        <td class="p-2.5 text-slate-500 font-sans text-xs">${b.remarks || '—'}</td>
      </tr>
    `).join("");
  } catch (err) {
    console.error("Error loading Ready 25% Ammonia:", err);
  }
}

// --- 10% AMMONIA STOCK & PREPARATION (STRICT FIXED RULE) ---
async function loadAmmonia10Stock() {
  try {
    const res = await fetch("/api/ammonia/stock-10");
    if (!res.ok) return;
    const data = await res.json();

    const tbody = document.getElementById("ammonia-10-tbody");
    if (data.batches.length === 0) {
      tbody.innerHTML = `<tr><td colspan="7" class="p-3 text-center text-slate-400">No prepared 10% Ammonia batches found</td></tr>`;
      return;
    }

    tbody.innerHTML = data.batches.map(b => `
      <tr class="hover:bg-slate-50">
        <td class="p-3 font-mono font-bold text-cyan-700">${b.batch_number}</td>
        <td class="p-3 font-mono text-slate-500">${b.manufacturing_date || '—'}</td>
        <td class="p-3 font-mono text-slate-700">${b.expiry_date}</td>
        <td class="p-3 text-right font-mono text-emerald-700 font-bold">${b.received_quantity.toFixed(1)} kg</td>
        <td class="p-3 text-right font-mono font-bold text-slate-900">${b.current_quantity.toFixed(1)} kg</td>
        <td class="p-3 text-slate-600 font-mono text-[11px]">${b.remarks || 'In-House Preparation'}</td>
        <td class="p-3"><span class="px-2 py-0.5 rounded text-[10px] bg-emerald-100 text-emerald-800 font-bold border border-emerald-200">${b.status}</span></td>
      </tr>
    `).join("");
  } catch (err) {
    console.error("Error loading 10% Ammonia stock:", err);
  }
}

async function populatePrepBarrelSelect() {
  try {
    const res = await fetch("/api/ammonia/barrels");
    if (!res.ok) return;
    const barrels = await res.json();
    cachedBarrels = barrels;

    const availableBarrels = barrels.filter(b => b.current_quantity >= 220.0);

    const sel1 = document.getElementById("prep-select-barrel");
    const sel2 = document.getElementById("modal-prep-select-barrel");

    const renderOpts = (sel) => {
      if (!sel) return;
      if (availableBarrels.length === 0) {
        sel.innerHTML = `<option value="">⚠️ Insufficient Stock: No complete 220 kg barrel available!</option>`;
      } else {
        sel.innerHTML = availableBarrels.map(b => 
          `<option value="${b.barrel_id}">${b.barrel_id} | Batch: ${b.batch_number} (${b.current_quantity.toFixed(1)} kg available) [Complete 220kg Ready]</option>`
        ).join("");
      }
    };

    renderOpts(sel1);
    renderOpts(sel2);
  } catch (err) {
    console.error("Error populating prep barrels:", err);
  }
}

async function handlePrepSubmit(e) {
  e.preventDefault();
  const barrelId = document.getElementById("prep-select-barrel").value;
  const prodDate = document.getElementById("prep-date").value;
  const expDate = document.getElementById("prep-exp-date").value;
  const refNo = document.getElementById("prep-ref").value;
  const remarks = document.getElementById("prep-remarks").value;

  await execute10Preparation(barrelId, prodDate, expDate, refNo, remarks);
}

async function handleModalPrepSubmit(e) {
  e.preventDefault();
  const barrelId = document.getElementById("modal-prep-select-barrel").value;
  const prodDate = document.getElementById("modal-prep-date").value;
  const expDate = document.getElementById("modal-prep-exp").value;
  const refNo = document.getElementById("modal-prep-ref").value;
  const remarks = document.getElementById("modal-prep-remarks").value;

  await execute10Preparation(barrelId, prodDate, expDate, refNo, remarks);
  closeModal("modal-prep");
}

async function execute10Preparation(barrelId, prodDate, expDate, refNo, remarks) {
  const barrel = cachedBarrels.find(b => b.barrel_id === barrelId);
  if (!barrel || barrel.current_quantity < 220.0) {
    alert("Insufficient 25% Ammonia stock. A complete 220 kg barrel is required for 10% Ammonia preparation.");
    return;
  }

  try {
    const res = await fetch("/api/ammonia/prepare-10", {
      method: "POST",
      headers: getAuthHeaders(),
      body: JSON.stringify({
        source_barrel_id: barrelId,
        production_date: prodDate,
        expiry_date: expDate,
        reference_number: refNo,
        remarks: remarks
      })
    });

    if (!res.ok) {
      const err = await res.json();
      alert(err.detail || "Dilution preparation rejected");
      return;
    }

    const data = await res.json();
    showToast(data.message || `Successfully produced 605 kg of 10% Ammonia!`, "success");
    switchTab("ammonia-10-stock");
    refreshDashboard();
  } catch (err) {
    alert("Preparation failed: " + err.message);
  }
}

// --- TRANSFERS ---
async function loadTransfersTable() {
  try {
    const res = await fetch("/api/reports/historical-transactions?transaction_type=Transfer");
    if (!res.ok) return;
    const transfers = await res.json();

    const tbody = document.getElementById("transfers-tbody");
    if (transfers.length === 0) {
      tbody.innerHTML = `<tr><td colspan="10" class="p-3 text-center text-slate-400">No stock transfers recorded</td></tr>`;
      return;
    }

    tbody.innerHTML = transfers.map(t => `
      <tr class="hover:bg-slate-50">
        <td class="p-3 font-mono text-slate-500">${t.trans_date} <span class="text-slate-400 text-[10px]">${t.trans_time}</span></td>
        <td class="p-3 font-bold text-slate-900">${t.chemical_name}</td>
        <td class="p-3 font-mono text-cyan-700 font-bold">${t.batch_number}</td>
        <td class="p-3 font-mono text-amber-700 font-semibold">${t.barrel_id || '—'}</td>
        <td class="p-3 text-slate-600" colspan="2">${t.location_name}</td>
        <td class="p-3 text-right font-mono font-bold text-purple-700">${t.quantity.toFixed(1)} ${t.unit}</td>
        <td class="p-3 font-mono text-slate-500">${t.reference_number}</td>
        <td class="p-3 text-slate-700">${t.purpose}</td>
        <td class="p-3 text-slate-500">${t.operator_name}</td>
      </tr>
    `).join("");
  } catch (err) {
    console.error("Error loading transfers:", err);
  }
}

async function populateTransferBatches() {
  const chemId = document.getElementById("trf-chem").value;
  const batchSel = document.getElementById("trf-batch");
  if (!chemId) {
    batchSel.innerHTML = `<option value="">Select chemical first</option>`;
    return;
  }

  const res = await fetch(`/api/inventory/batches?chemical_id=${chemId}`);
  if (!res.ok) return;
  const batches = await res.json();
  const activeBatches = batches.filter(b => b.current_quantity > 0);

  if (activeBatches.length === 0) {
    batchSel.innerHTML = `<option value="">No active batches available</option>`;
  } else {
    batchSel.innerHTML = activeBatches.map(b => 
      `<option value="${b.id}">${b.batch_number} (${b.current_quantity.toFixed(1)} ${b.unit} in ${b.storage_location_name})</option>`
    ).join("");
  }
}

async function handleTransferSubmit(e) {
  e.preventDefault();
  const chemId = parseInt(document.getElementById("trf-chem").value);
  const batchId = parseInt(document.getElementById("trf-batch").value);
  const qty = parseFloat(document.getElementById("trf-qty").value);
  const srcLoc = parseInt(document.getElementById("trf-source").value);
  const destLoc = parseInt(document.getElementById("trf-dest").value);
  const remarks = document.getElementById("trf-remarks").value;

  if (srcLoc === destLoc) {
    showToast("Source and destination locations cannot be the same", "error");
    return;
  }

  try {
    const res = await fetch("/api/inventory/transfers", {
      method: "POST",
      headers: getAuthHeaders(),
      body: JSON.stringify({
        date: new Date().toISOString().split("T")[0],
        chemical_id: chemId,
        batch_id: batchId,
        from_location_id: srcLoc,
        to_location_id: destLoc,
        quantity: qty,
        purpose: remarks || "Internal Store Transfer",
        reference_number: `TRF-${Date.now().toString().slice(-6)}`,
        remarks: remarks
      })
    });

    if (!res.ok) {
      const err = await res.json();
      showToast(err.detail || "Error transferring stock", "error");
      return;
    }

    closeModal("modal-transfer");
    showToast(`Transferred ${qty} kg successfully!`, "success");
    loadTransfersTable();
    refreshDashboard();
  } catch (err) {
    showToast("Transfer failed: " + err.message, "error");
  }
}

// --- CHEMICALS MASTER & BATCHES ---
async function loadChemicalsMaster() {
  try {
    const res = await fetch("/api/inventory/chemicals");
    if (!res.ok) return;
    const chemicals = await res.json();

    const grid = document.getElementById("chemicals-master-grid");
    grid.innerHTML = chemicals.map(c => `
      <div class="glass-card p-5 rounded-xl border border-slate-200 space-y-3">
        <div class="flex justify-between items-start">
          <div>
            <span class="text-[10px] font-mono text-slate-400 uppercase font-bold tracking-wider block">${c.code}</span>
            <h4 class="text-base font-bold text-slate-900">${c.name}</h4>
          </div>
          <span class="px-2 py-0.5 text-[10px] font-bold bg-slate-100 text-slate-700 rounded border border-slate-200">
            ${c.default_unit}
          </span>
        </div>

        <p class="text-xs text-slate-500 leading-relaxed">${c.description || 'Industrial Compounding Chemical'}</p>

        <div class="p-3 bg-slate-50 rounded-lg border border-slate-200 flex justify-between items-center text-xs font-mono">
          <span class="text-slate-600 font-sans font-medium">Available Total Stock:</span>
          <span class="text-cyan-700 font-bold text-sm">${c.total_stock.toLocaleString('en-US', {minimumFractionDigits: 1})} ${c.default_unit}</span>
        </div>

        <div class="grid grid-cols-2 gap-2 text-[10px] text-slate-500 pt-1">
          <div>Storage Store: <span class="text-slate-800 block truncate font-medium">${c.storage_location_name || 'Main Chemical Store'}</span></div>
          <div>Morning Check Req: <span class="${c.requires_daily_physical_check ? 'text-amber-700 font-bold' : 'text-slate-400'} block">${c.requires_daily_physical_check ? 'Yes (Ammonia)' : 'No (Usage Only)'}</span></div>
        </div>
      </div>
    `).join("");
  } catch (err) {
    console.error("Error loading chemicals master:", err);
  }
}

async function loadBatchesTable() {
  const statusFilter = document.getElementById("batch-filter-status").value;
  try {
    let url = "/api/inventory/batches";
    if (statusFilter) url += `?status_filter=${statusFilter}`;
    const res = await fetch(url);
    if (!res.ok) return;
    const batches = await res.json();

    const tbody = document.getElementById("batches-tbody");
    if (batches.length === 0) {
      tbody.innerHTML = `<tr><td colspan="9" class="p-3 text-center text-slate-400">No batches found</td></tr>`;
      return;
    }

    tbody.innerHTML = batches.map(b => {
      let badgeClass = "badge-valid";
      if (b.status === "Expiring Soon") badgeClass = "badge-expiring";
      if (b.status === "Expired") badgeClass = "badge-expired";

      return `
        <tr class="hover:bg-slate-50">
          <td class="p-3 font-bold text-slate-900">${b.chemical_name}</td>
          <td class="p-3 font-mono text-cyan-700 font-bold">${b.batch_number}</td>
          <td class="p-3 font-mono text-slate-500">${b.manufacturing_date || '—'}</td>
          <td class="p-3 font-mono font-bold ${b.status === 'Expiring Soon' ? 'text-amber-700' : b.status === 'Expired' ? 'text-rose-600' : 'text-slate-700'}">${b.expiry_date}</td>
          <td class="p-3 text-slate-800">${b.supplier_name || '—'}</td>
          <td class="p-3 text-slate-600">${b.storage_location_name}</td>
          <td class="p-3 text-right font-mono text-slate-500">${b.received_quantity.toFixed(1)} ${b.unit}</td>
          <td class="p-3 text-right font-mono font-bold text-cyan-800">${b.current_quantity.toFixed(1)} ${b.unit}</td>
          <td class="p-3"><span class="px-2 py-0.5 text-[10px] font-bold rounded ${badgeClass}">${b.status}</span></td>
        </tr>
      `;
    }).join("");
  } catch (err) {
    console.error("Error loading batches table:", err);
  }
}

// --- REPORTS CONTROLLER & EXPORTS ---
let currentReportType = "daily";

function selectReportTab(tabKey) {
  currentReportType = tabKey;
  document.querySelectorAll("#rtab-daily, #rtab-usage, #rtab-stock, #rtab-ammonia, #rtab-physical-vs-sys").forEach(b => {
    b.classList.remove("text-cyan-700", "border-b-2", "border-cyan-700", "font-bold");
    b.classList.add("text-slate-500");
  });
  const activeTabBtn = document.getElementById(`rtab-${tabKey}`);
  if (activeTabBtn) activeTabBtn.classList.add("text-cyan-700", "border-b-2", "border-cyan-700", "font-bold");

  renderActiveReport(tabKey);
}

async function renderActiveReport(type) {
  const container = document.getElementById("report-content-area");
  container.innerHTML = `<div class="p-8 text-center text-slate-400">Loading report data...</div>`;

  try {
    if (type === "daily") {
      const today = new Date().toISOString().split("T")[0];
      const res = await fetch(`/api/reports/daily?report_date=${today}`);
      const data = await res.json();
      container.innerHTML = `
        <div class="space-y-4">
          <div class="flex justify-between items-center">
            <h4 class="font-bold text-slate-900 text-sm">Daily Store Movement Report (${today})</h4>
            <span class="text-xs text-slate-500 font-mono">Formula: Closing = Opening + Rcvd + TrfIn + ProdIn - Used - TrfOut - ProdCons +/- Adj</span>
          </div>
          <div class="overflow-x-auto">
            <table class="w-full text-left text-xs">
              <thead class="bg-slate-50 text-slate-600 border-b border-slate-200 uppercase text-[10px] font-bold">
                <tr>
                  <th class="p-2.5">Chemical</th>
                  <th class="p-2.5">Batch</th>
                  <th class="p-2.5">Expiry</th>
                  <th class="p-2.5">Store Location</th>
                  <th class="p-2.5 text-right">Opening</th>
                  <th class="p-2.5 text-right">Rcvd</th>
                  <th class="p-2.5 text-right">Used</th>
                  <th class="p-2.5 text-right">Trf In</th>
                  <th class="p-2.5 text-right">Trf Out</th>
                  <th class="p-2.5 text-right">Prod In</th>
                  <th class="p-2.5 text-right">Prod Cons</th>
                  <th class="p-2.5 text-right">Closing</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-slate-200 text-slate-700 font-mono">
                ${data.map(r => `
                  <tr>
                    <td class="p-2.5 font-sans font-bold text-slate-900">${r.chemical_name}</td>
                    <td class="p-2.5 text-cyan-700 font-bold">${r.batch_number}</td>
                    <td class="p-2.5 text-slate-500">${r.expiry_date}</td>
                    <td class="p-2.5 font-sans text-slate-600">${r.storage_location}</td>
                    <td class="p-2.5 text-right">${r.opening_stock.toFixed(1)}</td>
                    <td class="p-2.5 text-right text-emerald-700">${r.received > 0 ? '+' + r.received.toFixed(1) : '0.0'}</td>
                    <td class="p-2.5 text-right text-rose-600">${r.used > 0 ? '-' + r.used.toFixed(1) : '0.0'}</td>
                    <td class="p-2.5 text-right text-purple-700">${r.transfer_in > 0 ? '+' + r.transfer_in.toFixed(1) : '0.0'}</td>
                    <td class="p-2.5 text-right text-purple-700">${r.transfer_out > 0 ? '-' + r.transfer_out.toFixed(1) : '0.0'}</td>
                    <td class="p-2.5 text-right text-cyan-700">${r.production_in > 0 ? '+' + r.production_in.toFixed(1) : '0.0'}</td>
                    <td class="p-2.5 text-right text-amber-700">${r.production_consumption > 0 ? '-' + r.production_consumption.toFixed(1) : '0.0'}</td>
                    <td class="p-2.5 text-right font-bold text-slate-900">${r.closing_stock.toFixed(1)} ${r.unit}</td>
                  </tr>
                `).join("")}
              </tbody>
            </table>
          </div>
        </div>
      `;
    } else if (type === "usage") {
      const curYM = new Date().toISOString().substring(0, 7);
      const res = await fetch(`/api/reports/monthly-usage?year_month=${curYM}`);
      const data = await res.json();
      container.innerHTML = `
        <div class="space-y-4">
          <h4 class="font-bold text-slate-900 text-sm">Monthly Chemical Usage Report (${curYM})</h4>
          <div class="overflow-x-auto">
            <table class="w-full text-left text-xs">
              <thead class="bg-slate-50 text-slate-600 border-b border-slate-200 uppercase text-[10px] font-bold">
                <tr>
                  <th class="p-2.5">Chemical</th>
                  <th class="p-2.5">Batch</th>
                  <th class="p-2.5">Expiry Date</th>
                  <th class="p-2.5">Storage Location</th>
                  <th class="p-2.5 text-right">Transactions</th>
                  <th class="p-2.5 text-right">Total Qty Used</th>
                  <th class="p-2.5">Purposes</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-slate-200 text-slate-700">
                ${data.map(r => `
                  <tr>
                    <td class="p-2.5 font-bold text-slate-900">${r.chemical_name}</td>
                    <td class="p-2.5 font-mono text-cyan-700 font-bold">${r.batch_number}</td>
                    <td class="p-2.5 font-mono text-slate-500">${r.expiry_date}</td>
                    <td class="p-2.5 text-slate-600">${r.storage_location}</td>
                    <td class="p-2.5 text-right font-mono">${r.transaction_count}</td>
                    <td class="p-2.5 text-right font-mono font-bold text-rose-600">-${r.total_quantity_used.toFixed(2)} ${r.unit}</td>
                    <td class="p-2.5 text-slate-700">${r.purposes || '—'}</td>
                  </tr>
                `).join("")}
              </tbody>
            </table>
          </div>
        </div>
      `;
    } else if (type === "stock") {
      const res = await fetch(`/api/reports/stock-balance`);
      const data = await res.json();
      container.innerHTML = `
        <div class="space-y-4">
          <h4 class="font-bold text-slate-900 text-sm">Current Stock Balance by Batch</h4>
          <div class="overflow-x-auto">
            <table class="w-full text-left text-xs">
              <thead class="bg-slate-50 text-slate-600 border-b border-slate-200 uppercase text-[10px] font-bold">
                <tr>
                  <th class="p-2.5">Chemical</th>
                  <th class="p-2.5">Batch</th>
                  <th class="p-2.5">Expiry Date</th>
                  <th class="p-2.5">Location</th>
                  <th class="p-2.5 text-right">Received Qty</th>
                  <th class="p-2.5 text-right">Current Available</th>
                  <th class="p-2.5">Status</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-slate-200 text-slate-700 font-mono">
                ${data.map(r => `
                  <tr>
                    <td class="p-2.5 font-sans font-bold text-slate-900">${r.chemical_name}</td>
                    <td class="p-2.5 text-cyan-700 font-bold">${r.batch_number}</td>
                    <td class="p-2.5 text-slate-500">${r.expiry_date}</td>
                    <td class="p-2.5 font-sans text-slate-600">${r.storage_location_name}</td>
                    <td class="p-2.5 text-right">${r.received_quantity.toFixed(1)} ${r.unit}</td>
                    <td class="p-2.5 text-right font-bold text-cyan-800">${r.current_quantity.toFixed(1)} ${r.unit}</td>
                    <td class="p-2.5 font-sans"><span class="px-2 py-0.5 rounded text-[10px] font-bold ${r.status === 'Valid' ? 'badge-valid' : r.status === 'Expiring Soon' ? 'badge-expiring' : 'badge-expired'}">${r.status}</span></td>
                  </tr>
                `).join("")}
              </tbody>
            </table>
          </div>
        </div>
      `;
    } else if (type === "ammonia") {
      const res = await fetch(`/api/reports/ammonia-audit`);
      const data = await res.json();
      container.innerHTML = `
        <div class="space-y-6">
          <div>
            <h4 class="font-bold text-slate-900 text-sm mb-3">10% Ammonia Dilution Production History</h4>
            <div class="overflow-x-auto">
              <table class="w-full text-left text-xs">
                <thead class="bg-slate-50 text-slate-600 border-b border-slate-200 uppercase text-[10px] font-bold">
                  <tr>
                    <th class="p-2.5">Prep Date</th>
                    <th class="p-2.5">Ref No</th>
                    <th class="p-2.5">Source 25% Barrel</th>
                    <th class="p-2.5">Source 25% Batch</th>
                    <th class="p-2.5 text-right">25% Used</th>
                    <th class="p-2.5 text-right">Water Added</th>
                    <th class="p-2.5 text-right">10% Produced</th>
                    <th class="p-2.5">New 10% Batch</th>
                    <th class="p-2.5">Expiry</th>
                    <th class="p-2.5">Operator</th>
                  </tr>
                </thead>
                <tbody class="divide-y divide-slate-200 text-slate-700 font-mono">
                  ${data.dilutions.map(d => `
                    <tr>
                      <td class="p-2.5 text-slate-500">${d.production_date}</td>
                      <td class="p-2.5 text-slate-700">${d.reference_number}</td>
                      <td class="p-2.5 font-bold text-amber-700">${d.source_barrel_id}</td>
                      <td class="p-2.5 text-slate-700">${d.source_25_batch}</td>
                      <td class="p-2.5 text-right text-amber-800 font-bold">${d.source_quantity.toFixed(1)} kg</td>
                      <td class="p-2.5 text-right text-blue-700">${d.water_quantity.toFixed(1)} kg</td>
                      <td class="p-2.5 text-right font-bold text-cyan-700">${d.produced_quantity.toFixed(1)} kg</td>
                      <td class="p-2.5 font-bold text-cyan-800">${d.new_10_batch}</td>
                      <td class="p-2.5 text-slate-500">${d.expiry_date}</td>
                      <td class="p-2.5 font-sans text-slate-600">${d.operator_name}</td>
                    </tr>
                  `).join("")}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      `;
    } else if (type === "physical-vs-sys") {
      const res = await fetch(`/api/reports/physical-vs-system`);
      const data = await res.json();
      container.innerHTML = `
        <div class="space-y-4">
          <h4 class="font-bold text-slate-900 text-sm">Physical vs System Stock Reconciliation</h4>
          <div class="overflow-x-auto">
            <table class="w-full text-left text-xs">
              <thead class="bg-slate-50 text-slate-600 border-b border-slate-200 uppercase text-[10px] font-bold">
                <tr>
                  <th class="p-2.5">Date & Time</th>
                  <th class="p-2.5">Location</th>
                  <th class="p-2.5">Chemical</th>
                  <th class="p-2.5 text-right">Physical Measured</th>
                  <th class="p-2.5 text-right">System Recorded</th>
                  <th class="p-2.5 text-right">Variance (Diff)</th>
                  <th class="p-2.5">Inspector Remarks</th>
                  <th class="p-2.5">Inspector</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-slate-200 text-slate-700 font-mono">
                ${data.map(r => `
                  <tr>
                    <td class="p-2.5 text-slate-500">${r.date} ${r.time}</td>
                    <td class="p-2.5 font-sans font-bold text-slate-900">${r.storage_location_name}</td>
                    <td class="p-2.5 font-sans text-slate-700">${r.chemical_name}</td>
                    <td class="p-2.5 text-right font-bold text-cyan-700">${r.physical_quantity.toFixed(2)} ${r.unit}</td>
                    <td class="p-2.5 text-right text-slate-600">${r.system_quantity.toFixed(2)} ${r.unit}</td>
                    <td class="p-2.5 text-right font-bold ${r.variance < 0 ? 'text-rose-600' : r.variance > 0 ? 'text-cyan-700' : 'text-emerald-700'}">
                      ${r.variance > 0 ? '+' : ''}${r.variance.toFixed(2)} ${r.unit}
                    </td>
                    <td class="p-2.5 font-sans text-slate-600">${r.remarks || '—'}</td>
                    <td class="p-2.5 font-sans text-slate-500">${r.operator_name}</td>
                  </tr>
                `).join("")}
              </tbody>
            </table>
          </div>
        </div>
      `;
    }
  } catch (err) {
    container.innerHTML = `<div class="p-6 text-center text-rose-500">Error loading report: ${err.message}</div>`;
  }
}

function downloadActiveReportExcel() {
  const dateStr = new Date().toISOString().split("T")[0];
  const curYM = dateStr.substring(0, 7);

  if (currentReportType === "daily") {
    window.location.href = `/api/export/daily/excel?report_date=${dateStr}`;
  } else if (currentReportType === "usage") {
    window.location.href = `/api/export/monthly-usage/excel?year_month=${curYM}`;
  } else if (currentReportType === "stock") {
    window.location.href = `/api/export/stock-balance/excel`;
  } else if (currentReportType === "ammonia") {
    window.location.href = `/api/export/ammonia-audit/excel`;
  } else if (currentReportType === "physical-vs-sys") {
    window.location.href = `/api/export/physical-vs-system/excel`;
  }
  showToast("Downloading Excel spreadsheet...", "success");
}

function downloadActiveReportPDF() {
  const dateStr = new Date().toISOString().split("T")[0];
  const curYM = dateStr.substring(0, 7);

  let url = "";
  if (currentReportType === "daily") {
    url = `/api/export/daily/pdf?report_date=${dateStr}`;
  } else if (currentReportType === "usage") {
    url = `/api/export/monthly-usage/pdf?year_month=${curYM}`;
  } else if (currentReportType === "stock") {
    url = `/api/export/stock-balance/pdf`;
  } else if (currentReportType === "ammonia") {
    url = `/api/export/ammonia-audit/pdf`;
  } else if (currentReportType === "physical-vs-sys") {
    url = `/api/export/physical-vs-system/pdf`;
  }

  if (url) window.open(url, "_blank");
}

function downloadHistoricalExcel() {
  const search = document.getElementById("hist-search").value;
  const type = document.getElementById("hist-type-filter").value;
  const chem = document.getElementById("hist-chem-filter").value;
  const dateVal = document.getElementById("hist-date-filter").value;

  let url = `/api/export/historical-records/excel?`;
  if (search) url += `search=${encodeURIComponent(search)}&`;
  if (type) url += `transaction_type=${encodeURIComponent(type)}&`;
  if (chem) url += `chemical_id=${chem}&`;
  if (dateVal) url += `start_date=${dateVal}&`;

  window.location.href = url;
  showToast("Downloading Historical Ledger Excel...", "success");
}

// --- HISTORICAL TRANSACTIONS TRACEABILITY ---
async function loadHistoricalTransactions() {
  const search = document.getElementById("hist-search").value;
  const type = document.getElementById("hist-type-filter").value;
  const chem = document.getElementById("hist-chem-filter").value;
  const dateVal = document.getElementById("hist-date-filter").value;

  let url = `/api/reports/historical-transactions?`;
  if (search) url += `search=${encodeURIComponent(search)}&`;
  if (type) url += `transaction_type=${encodeURIComponent(type)}&`;
  if (chem) url += `chemical_id=${chem}&`;
  if (dateVal) url += `start_date=${dateVal}&`;

  try {
    const res = await fetch(url);
    if (!res.ok) return;
    const records = await res.json();

    const tbody = document.getElementById("history-tbody");
    if (records.length === 0) {
      tbody.innerHTML = `<tr><td colspan="10" class="p-3 text-center text-slate-400">No matching historical records found</td></tr>`;
      return;
    }

    tbody.innerHTML = records.map(r => `
      <tr class="hover:bg-slate-50">
        <td class="p-2.5 font-mono text-[11px] text-slate-500">${r.trans_date} <span class="text-slate-400 text-[10px]">${r.trans_time}</span></td>
        <td class="p-2.5 font-bold ${r.trans_type === 'Usage' ? 'text-rose-600' : r.trans_type === 'Receiving' ? 'text-blue-600' : r.trans_type === 'Preparation' ? 'text-cyan-700' : 'text-purple-600'}">${r.trans_type}</td>
        <td class="p-2.5 font-bold text-slate-900">${r.chemical_name}</td>
        <td class="p-2.5 font-mono text-slate-700">${r.batch_number || ''} ${r.barrel_id ? `<span class="text-amber-700 font-bold block">(${r.barrel_id})</span>` : ''}</td>
        <td class="p-2.5 text-right font-mono font-bold text-slate-900">${r.quantity.toFixed(1)} ${r.unit}</td>
        <td class="p-2.5 text-slate-700">${r.purpose}</td>
        <td class="p-2.5 text-slate-500">${r.supplier_customer_name || '—'}</td>
        <td class="p-2.5 text-slate-600">${r.location_name || '—'}</td>
        <td class="p-2.5 font-mono text-slate-500">${r.reference_number || '—'}</td>
        <td class="p-2.5 text-slate-500">${r.operator_name || '—'}</td>
      </tr>
    `).join("");
  } catch (err) {
    console.error("Error loading historical transactions:", err);
  }
}

// --- ALERTS CENTER ---
async function loadAlertsCenter() {
  try {
    const res = await fetch("/api/inventory/alerts");
    if (!res.ok) return;
    const data = await res.json();

    const container = document.getElementById("alerts-full-list");
    const items = [];

    data.expiry_alerts.forEach(a => {
      const isExp = a.alert_status === "Expired";
      items.push(`
        <div class="p-4 rounded-xl border ${isExp ? 'bg-rose-50 border-rose-200' : 'bg-amber-50 border-amber-200'} flex items-start justify-between">
          <div class="flex items-start gap-3">
            <i data-lucide="${isExp ? 'x-circle' : 'alert-triangle'}" class="w-5 h-5 ${isExp ? 'text-rose-600' : 'text-amber-600'} mt-0.5"></i>
            <div>
              <h4 class="font-bold text-sm ${isExp ? 'text-rose-900' : 'text-amber-900'}">${a.chemical_name} &bull; Batch: ${a.batch_number}</h4>
              <p class="text-xs text-slate-700 mt-1">Expiry Date: <span class="font-mono font-bold">${a.expiry_date}</span> (${a.days_remaining} days remaining)</p>
              <p class="text-xs text-slate-600 mt-0.5">Current Stock in Location: <span class="font-bold font-mono">${a.current_quantity} ${a.unit}</span> (${a.storage_location_name})</p>
            </div>
          </div>
          <span class="px-2.5 py-1 text-xs font-bold rounded ${isExp ? 'bg-rose-200 text-rose-800' : 'bg-amber-200 text-amber-800'}">
            ${a.alert_status}
          </span>
        </div>
      `);
    });

    data.low_stock_alerts.forEach(l => {
      items.push(`
        <div class="p-4 rounded-xl border bg-orange-50 border-orange-200 flex items-start justify-between">
          <div class="flex items-start gap-3">
            <i data-lucide="arrow-down-circle" class="w-5 h-5 text-orange-600 mt-0.5"></i>
            <div>
              <h4 class="font-bold text-sm text-orange-900">${l.chemical_name} &bull; Low Stock Warning</h4>
              <p class="text-xs text-slate-700 mt-1">Current Stock: <span class="font-mono font-bold">${l.current_stock.toFixed(1)} ${l.default_unit}</span> &bull; Minimum Configured: <span class="font-mono font-bold">${l.min_stock_level} ${l.default_unit}</span></p>
              <p class="text-xs text-rose-700 font-semibold mt-0.5">Deficit: -${l.deficit.toFixed(1)} ${l.default_unit}</p>
            </div>
          </div>
          <span class="px-2.5 py-1 text-xs font-bold rounded bg-orange-200 text-orange-800">
            Low Stock
          </span>
        </div>
      `);
    });

    container.innerHTML = items.length > 0 ? items.join("") : `<div class="p-8 text-center text-slate-400">All chemicals within safe stock thresholds and validity periods.</div>`;
    if (window.lucide) lucide.createIcons();
  } catch (err) {
    console.error("Error loading alerts:", err);
  }
}

// --- SETTINGS & ADJUSTMENTS ---
async function loadSettingsPage() {
  try {
    const res = await fetch("/api/inventory/batches");
    if (!res.ok) return;
    const batches = await res.json();
    cachedBatches = batches;

    const adjSel = document.getElementById("adj-select-batch");
    if (adjSel) {
      adjSel.innerHTML = batches.map(b => 
        `<option value="${b.id}">${b.chemical_name} &bull; ${b.batch_number} (${b.current_quantity.toFixed(1)} ${b.unit} in ${b.storage_location_name})</option>`
      ).join("");
      updateAdjustmentBatchMeta();
    }
  } catch (err) {
    console.error("Error loading settings page data:", err);
  }
}

function updateAdjustmentBatchMeta() {
  const batchId = parseInt(document.getElementById("adj-select-batch").value);
  const batch = cachedBatches.find(b => b.id === batchId);
  const currEl = document.getElementById("adj-curr-qty");
  if (batch && currEl) {
    currEl.value = `${batch.current_quantity.toFixed(2)} ${batch.unit}`;
  }
}

async function handleAdjustmentSubmit(e) {
  e.preventDefault();
  const batchId = parseInt(document.getElementById("adj-select-batch").value);
  const newQty = parseFloat(document.getElementById("adj-new-qty").value);
  const reason = document.getElementById("adj-reason").value;

  const batch = cachedBatches.find(b => b.id === batchId);
  if (!batch) return;

  try {
    const res = await fetch("/api/inventory/adjustments", {
      method: "POST",
      headers: getAuthHeaders(),
      body: JSON.stringify({
        chemical_id: batch.chemical_id,
        batch_id: batch.id,
        storage_location_id: batch.storage_location_id,
        new_quantity: newQty,
        reason: reason
      })
    });

    if (!res.ok) {
      const err = await res.json();
      showToast(err.detail || "Error adjusting stock", "error");
      return;
    }

    const data = await res.json();
    showToast(data.message, "success");
    loadSettingsPage();
    refreshDashboard();
  } catch (err) {
    showToast("Adjustment failed: " + err.message, "error");
  }
}

async function saveSystemSettings() {
  const days = document.getElementById("setting-expiry-days").value;
  try {
    const res = await fetch("/api/settings", {
      method: "POST",
      headers: getAuthHeaders(),
      body: JSON.stringify({
        key: "expiry_warning_days",
        value: days
      })
    });
    if (!res.ok) {
      showToast("Error updating configuration", "error");
      return;
    }
    showToast("System configuration saved successfully", "success");
    refreshDashboard();
  } catch (err) {
    showToast("Failed to save: " + err.message, "error");
  }
}

// --- MODALS & NOTIFICATIONS ---
function openModal(id) {
  const el = document.getElementById(id);
  if (el) el.classList.remove("hidden");
  if (id === "modal-prep") populatePrepBarrelSelect();
  if (id === "modal-receiving") toggleReceivingBarrelNotice();
}

function closeModal(id) {
  const el = document.getElementById(id);
  if (el) el.classList.add("hidden");
}

function showToast(message, type = "success") {
  const container = document.getElementById("toast-container");
  const toast = document.createElement("div");

  let colorClass = "bg-white border-cyan-600 text-slate-800";
  let iconName = "check-circle-2";
  if (type === "error") {
    colorClass = "bg-rose-50 border-rose-500 text-rose-900";
    iconName = "alert-circle";
  }

  toast.className = `p-3 rounded-xl border shadow-xl text-xs font-bold flex items-center gap-2.5 transition-all duration-300 ${colorClass}`;
  toast.innerHTML = `<i data-lucide="${iconName}" class="w-4 h-4"></i> <span>${message}</span>`;

  container.appendChild(toast);
  if (window.lucide) lucide.createIcons();

  setTimeout(() => {
    toast.classList.add("opacity-0");
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}
