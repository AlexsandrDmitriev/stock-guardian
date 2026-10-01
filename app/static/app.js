const API_BASE = window.location.origin;
const DEFAULT_USER_ID = "12345678-1234-5678-1234-567812345678";
const USER_ID_KEY = "stockGuardianUserId";
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

const wsIndicator = document.getElementById("wsIndicator");
const wsStatus = document.getElementById("wsStatus");
const alertForm = document.getElementById("alertForm");
const formMessage = document.getElementById("formMessage");
const tableBody = document.querySelector("#alertsTable tbody");
const notifications = document.getElementById("notifications");
const userIdInput = document.getElementById("userId");
const checkNowBtn = document.getElementById("checkNow");
const checkNowStatus = document.getElementById("checkNowStatus");

let ws = null;
let reconnectTimer = null;
let reconnectDelay = 1000;

function getUserId() {
  return (localStorage.getItem(USER_ID_KEY) || DEFAULT_USER_ID).trim();
}

function setUserId(value) {
  const id = value.trim();
  localStorage.setItem(USER_ID_KEY, id);
  return id;
}

function formatId(id) {
  return id ? id.slice(0, 8) + "..." : "";
}

function setStatus(text, state) {
  wsStatus.textContent = text;
  wsIndicator.classList.toggle("online", state === "online");
  wsIndicator.classList.toggle("offline", state !== "online");
}

function addNotification(text, isError) {
  const li = document.createElement("li");
  if (isError) li.classList.add("error");
  li.textContent = text;
  notifications.prepend(li);
}

async function loadAlerts() {
  try {
    const res = await fetch(`${API_BASE}/alerts`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const alerts = await res.json();
    tableBody.innerHTML = alerts
      .map(
        (a) => `<tr>
          <td>${formatId(a.id)}</td>
          <td>${a.symbol}</td>
          <td>${a.target_price}</td>
          <td>${a.direction}</td>
          <td>${formatId(a.user_id)}</td>
          <td><button class="danger" data-id="${a.id}">Delete</button></td>
        </tr>`
      )
      .join("");
    tableBody.querySelectorAll("button.danger").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const res = await fetch(`${API_BASE}/alerts/${btn.dataset.id}`, { method: "DELETE" });
        if (!res.ok) addNotification(`Delete failed: HTTP ${res.status}`, true);
        loadAlerts();
      });
    });
  } catch (err) {
    addNotification(`Failed to load alerts: ${err.message}`, true);
  }
}

function renderAlert(data) {
  const arrow = data.direction === "below" ? "<=" : ">=";
  return `${data.symbol} ${data.price} (${arrow} target ${data.target_price})`;
}

function connectWebSocket(userId) {
  if (reconnectTimer) {
    clearTimeout(reconnectTimer);
    reconnectTimer = null;
  }
  if (ws) {
    ws.onclose = null;
    ws.close();
    ws = null;
  }

  const scheme = window.location.protocol === "https:" ? "wss" : "ws";
  const url = `${scheme}://${window.location.host}/ws/${userId}`;
  setStatus("WebSocket: connecting…", "connecting");
  ws = new WebSocket(url);

  ws.onopen = () => {
    reconnectDelay = 1000;
    setStatus("WebSocket: connected", "online");
  };
  ws.onerror = () => {
    setStatus("WebSocket: error", "offline");
  };
  ws.onclose = (event) => {
    setStatus(`WebSocket: offline (${event.code}) — retry in ${Math.round(reconnectDelay / 1000)}s`, "offline");
    reconnectTimer = setTimeout(() => connectWebSocket(userId), reconnectDelay);
    reconnectDelay = Math.min(reconnectDelay * 2, 30000);
  };
  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      if (data.symbol === undefined) {
        addNotification(JSON.stringify(data));
      } else {
        addNotification(renderAlert(data));
      }
    } catch {
      addNotification(event.data);
    }
  };
}

async function refreshPrices() {
  const el = document.getElementById("currentPrices");
  if (!el) return;
  try {
    const res = await fetch(`${API_BASE}/debug/prices`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    if (data.error) {
      el.textContent = `prices: error — ${data.error}`;
      return;
    }
    const prices = Object.entries(data.prices || {})
      .map(([k, v]) => `${k}=${v}`)
      .join(", ");
    const age = data.last_check_age_seconds;
    el.textContent = prices
      ? `prices: ${prices || "none yet"} — last check ${age === null ? "never" : age + "s ago"}`
      : "prices: none yet — checker has never run";
  } catch (err) {
    el.textContent = `prices: error — ${err.message}`;
  }
}

alertForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  formMessage.textContent = "";
  const userId = userIdInput.value.trim();
  if (!UUID_RE.test(userId)) {
    formMessage.textContent = "Error: User ID must be a UUID.";
    return;
  }
  const payload = {
    symbol: document.getElementById("symbol").value.toUpperCase(),
    target_price: parseFloat(document.getElementById("targetPrice").value),
    direction: document.getElementById("direction").value,
    user_id: userId,
  };
  try {
    const res = await fetch(`${API_BASE}/alerts`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (res.ok) {
      setUserId(userId);
      formMessage.textContent = `Alert created for ${userId}.`;
      loadAlerts();
    } else {
      formMessage.textContent = "Error: " + (await res.text());
    }
  } catch (err) {
    formMessage.textContent = "Error: " + err.message;
  }
});

userIdInput.addEventListener("change", () => {
  const id = userIdInput.value.trim();
  if (!UUID_RE.test(id)) {
    addNotification("User ID must be a UUID — WebSocket not switched.", true);
    return;
  }
  setUserId(id);
  addNotification(`Listening as ${id}`);
  connectWebSocket(id);
  loadAlerts();
});

checkNowBtn.addEventListener("click", async () => {
  checkNowBtn.disabled = true;
  checkNowBtn.textContent = "Checking…";
  checkNowStatus.textContent = "";
  checkNowStatus.classList.remove("error");
  try {
    const res = await fetch(`${API_BASE}/debug/trigger`, { method: "POST" });
    const data = await res.json();
    if (!res.ok || data.status !== "triggered") {
      checkNowStatus.textContent = `Check failed: ${data.detail || "HTTP " + res.status}`;
      checkNowStatus.classList.add("error");
    } else {
      checkNowStatus.textContent = "Check finished — matching alerts are in the table below.";
    }
  } catch (err) {
    checkNowStatus.textContent = `Check failed: ${err.message}`;
    checkNowStatus.classList.add("error");
  }
  checkNowBtn.textContent = "Check Now";
  checkNowBtn.disabled = false;
  refreshPrices();
  loadAlerts();
});

userIdInput.value = getUserId();
loadAlerts();
connectWebSocket(getUserId());
refreshPrices();
setInterval(refreshPrices, 10000);
