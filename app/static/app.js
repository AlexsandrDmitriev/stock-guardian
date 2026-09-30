const API_BASE = window.location.origin;

const wsIndicator = document.getElementById("wsIndicator");
const wsStatus = document.getElementById("wsStatus");
const alertForm = document.getElementById("alertForm");
const formMessage = document.getElementById("formMessage");
const tableBody = document.querySelector("#alertsTable tbody");
const notifications = document.getElementById("notifications");

let ws = null;

function formatId(id) {
  return id ? id.slice(0, 8) + "..." : "";
}

function addNotification(text) {
  const li = document.createElement("li");
  li.textContent = text;
  notifications.prepend(li);
}

async function loadAlerts() {
  try {
    const res = await fetch(`${API_BASE}/alerts`);
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
        await fetch(`${API_BASE}/alerts/${btn.dataset.id}`, { method: "DELETE" });
        loadAlerts();
      });
    });
  } catch (err) {
    console.error(err);
  }
}

function connectWebSocket(userId) {
  const scheme = window.location.protocol === "https:" ? "wss" : "ws";
  const url = `${scheme}://${window.location.host}/ws/${userId}`;
  ws = new WebSocket(url);
  ws.onopen = () => {
    wsIndicator.classList.add("online");
    wsStatus.textContent = "WebSocket: connected";
  };
  ws.onclose = () => {
    wsIndicator.classList.remove("online");
    wsStatus.textContent = "WebSocket: offline";
    setTimeout(() => connectWebSocket(userId), 3000);
  };
  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      addNotification(`${data.symbol} hit ${data.price}`);
    } catch {
      addNotification(event.data);
    }
  };
}

alertForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  formMessage.textContent = "";
  const payload = {
    symbol: document.getElementById("symbol").value,
    target_price: parseFloat(document.getElementById("targetPrice").value),
    direction: document.getElementById("direction").value,
    user_id: document.getElementById("userId").value,
  };
  try {
    const res = await fetch(`${API_BASE}/alerts`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (res.ok) {
      formMessage.textContent = "Alert created.";
      alertForm.reset();
      loadAlerts();
    } else {
      formMessage.textContent = "Error: " + (await res.text());
    }
  } catch (err) {
    formMessage.textContent = "Error: " + err.message;
  }
});

loadAlerts();
connectWebSocket("12345678-1234-5678-1234-567812345678");