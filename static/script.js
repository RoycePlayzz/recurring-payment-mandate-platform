let revenueChart;
let statusChart;

const $ = (id) => document.getElementById(id);

function escapeHtml(value) {
    return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

function formatAmount(value) {
    return Number(value || 0).toLocaleString("en-IN");
}

function formatDate(value) {
    return value ? new Date(value).toLocaleString() : "—";
}

async function api(url, options = {}) {
    const response = await fetch(url, options);
    let payload = null;
    try {
        payload = await response.json();
    } catch (_) {
        payload = null;
    }

    if (!response.ok) {
        throw new Error(payload?.detail || `Request failed (${response.status})`);
    }
    return payload;
}

function showMessage(message, type = "success") {
    const box = $("message");
    box.textContent = message;
    box.className = `message ${type}`;
    clearTimeout(showMessage.timer);
    showMessage.timer = setTimeout(() => {
        box.className = "message hidden";
    }, 3500);
}

async function loadDashboard() {
    const data = await api("/dashboard");
    $("active").textContent = data.active;
    $("paused").textContent = data.paused;
    $("cancelled").textContent = data.cancelled;
    $("revenue").textContent = formatAmount(data.revenue);
    $("transactions").textContent = data.transactions;
    $("success").textContent = data.success;
    $("failed").textContent = data.failed;
    $("successRate").textContent = `${data.success_rate}%`;
    drawStatusChart(data.success, data.failed);
}

async function loadMerchantAnalytics() {
    const data = await api("/merchant-analytics");
    const table = $("merchantTable");
    table.innerHTML = data.length
        ? data.map((m) => `
            <tr>
                <td>${escapeHtml(m.merchant)}</td>
                <td>${formatAmount(m.revenue)}</td>
                <td>${m.success}</td>
                <td>${m.failed}</td>
                <td>${m.total}</td>
                <td><span class="rate-badge">${m.success_rate}%</span></td>
            </tr>
        `).join("")
        : `<tr><td colspan="6" class="empty">No merchant activity yet.</td></tr>`;

    drawRevenueChart(data);
}

function drawRevenueChart(data) {
    const ctx = $("revenueChart").getContext("2d");
    if (revenueChart) revenueChart.destroy();

    revenueChart = new Chart(ctx, {
        type: "bar",
        data: {
            labels: data.map((m) => m.merchant),
            datasets: [{
                label: "Successful revenue",
                data: data.map((m) => m.revenue),
                backgroundColor: "rgba(79, 70, 229, 0.78)",
                borderRadius: 8,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                y: { beginAtZero: true },
                x: { ticks: { maxRotation: 0 } },
            },
        },
    });
}

function drawStatusChart(success, failed) {
    const ctx = $("statusChart").getContext("2d");
    if (statusChart) statusChart.destroy();

    statusChart = new Chart(ctx, {
        type: "doughnut",
        data: {
            labels: ["Successful", "Failed"],
            datasets: [{
                data: [success, failed],
                backgroundColor: ["#16a34a", "#dc2626"],
                borderColor: "#ffffff",
                borderWidth: 3,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: "68%",
            plugins: { legend: { position: "bottom" } },
        },
    });
}

async function loadMandates() {
    const data = await api("/mandates");
    const table = $("mandateTable");

    table.innerHTML = data.length
        ? data.map((m) => {
            const statusClass = m.status.toLowerCase();
            const actions = m.status === "ACTIVE"
                ? `
                    <button class="ghost" onclick="pauseMandate(${m.id})">Pause</button>
                    <button class="danger-ghost" onclick="cancelMandate(${m.id})">Cancel</button>
                    <button onclick="executeMandate(${m.id})">Execute</button>
                  `
                : m.status === "PAUSED"
                    ? `
                        <button onclick="resumeMandate(${m.id})">Resume</button>
                        <button class="danger-ghost" onclick="cancelMandate(${m.id})">Cancel</button>
                      `
                    : `<span class="muted">No actions</span>`;

            return `
                <tr>
                    <td>#${m.id}</td>
                    <td>${escapeHtml(m.customer_name)}</td>
                    <td>${escapeHtml(m.merchant_name)}</td>
                    <td>${formatAmount(m.amount)}</td>
                    <td>${escapeHtml(m.frequency)}</td>
                    <td><span class="status ${statusClass}">${escapeHtml(m.status)}</span></td>
                    <td>${formatDate(m.next_execution)}</td>
                    <td class="actions">${actions}</td>
                </tr>
            `;
        }).join("")
        : `<tr><td colspan="8" class="empty">No mandates created yet.</td></tr>`;
}

async function loadTransactions() {
    const data = await api("/transactions");
    const table = $("transactionTable");

    table.innerHTML = data.length
        ? data.slice(0, 20).map((tx) => {
            const badgeClass = tx.status === "SUCCESS" ? "success" : "failed";
            const retry = tx.status === "FAILED"
                ? `<button onclick="retryTransaction(${tx.id})">Retry (${tx.retry_count}/3)</button>`
                : `<span class="muted">—</span>`;

            return `
                <tr>
                    <td title="${escapeHtml(tx.transaction_id)}">${escapeHtml(tx.transaction_id.slice(0, 8))}…</td>
                    <td>#${tx.mandate_id}</td>
                    <td>${formatAmount(tx.amount)}</td>
                    <td><span class="${badgeClass}">${escapeHtml(tx.status)}</span></td>
                    <td>${escapeHtml(tx.failure_reason || "—")}</td>
                    <td>${tx.retry_count}</td>
                    <td>${formatDate(tx.created_at)}</td>
                    <td>${retry}</td>
                </tr>
            `;
        }).join("")
        : `<tr><td colspan="8" class="empty">No transactions yet.</td></tr>`;
}

async function loadAuditLogs() {
    const data = await api("/audit-logs");
    const table = $("auditTable");
    table.innerHTML = data.length
        ? data.slice(0, 20).map((log) => `
            <tr>
                <td>${formatDate(log.created_at)}</td>
                <td>${escapeHtml(log.entity_type)}</td>
                <td>${escapeHtml(log.entity_id)}</td>
                <td>${escapeHtml(log.action)}</td>
                <td>${escapeHtml(log.details || "—")}</td>
            </tr>
        `).join("")
        : `<tr><td colspan="5" class="empty">No audit events yet.</td></tr>`;
}

async function createMandate(event) {
    event.preventDefault();
    const form = event.target;
    const payload = {
        customer_name: form.customer_name.value.trim(),
        merchant_name: form.merchant_name.value.trim(),
        amount: Number(form.amount.value),
        frequency: form.frequency.value,
    };

    try {
        await api("/mandates", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });
        form.reset();
        showMessage("Mandate created successfully.");
        await refreshDashboard();
    } catch (error) {
        showMessage(error.message, "error");
    }
}

async function updateMandate(id, action, successMessage) {
    try {
        await api(`/mandates/${id}/${action}`, { method: "POST" });
        showMessage(successMessage);
        await refreshDashboard();
    } catch (error) {
        showMessage(error.message, "error");
    }
}

function pauseMandate(id) { return updateMandate(id, "pause", "Mandate paused."); }
function resumeMandate(id) { return updateMandate(id, "resume", "Mandate resumed."); }
function cancelMandate(id) { return updateMandate(id, "cancel", "Mandate cancelled."); }

async function executeMandate(id) {
    try {
        await api(`/payments/execute/${id}`, {
            method: "POST",
            headers: { "Idempotency-Key": crypto.randomUUID() },
        });
        showMessage("Payment execution recorded.");
        await refreshDashboard();
    } catch (error) {
        showMessage(error.message, "error");
    }
}

async function retryTransaction(id) {
    try {
        await api(`/transactions/${id}/retry`, { method: "POST" });
        showMessage("Transaction retry completed.");
        await refreshDashboard();
    } catch (error) {
        showMessage(error.message, "error");
    }
}

async function refreshDashboard() {
    const results = await Promise.allSettled([
        loadDashboard(),
        loadMandates(),
        loadTransactions(),
        loadMerchantAnalytics(),
        loadAuditLogs(),
    ]);

    const firstError = results.find((result) => result.status === "rejected");
    if (firstError && document.readyState === "complete") {
        console.error(firstError.reason);
    }
}

$("createMandateForm").addEventListener("submit", createMandate);
refreshDashboard();
setInterval(refreshDashboard, 5000);
