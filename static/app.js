(() => {
  const state = {
    devices: [],
    locations: [],
    selectedDevice: null,
    hours: 24,
    start: null,
    end: null,
    markers: [],
    lines: [],
    bounds: [],
    pollerLabel: "Ready",
  };
  const $ = (id) => document.getElementById(id);

  const map = L.map('map', { zoomControl: false }).setView([51.1657, 10.4515], 6);
  L.control.zoom({ position: 'bottomright' }).addTo(map);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', 
              { attribution: '© OpenStreetMap contributors', 
               maxZoom: 19, 
               referrerPolicy:'origin'}
             ).addTo(map);


  const icons = {
    iphone: "📱",
    ipad: "▣",
    mac: "▰",
    watch: "⌚",
    airpods: "◉",
    default: "⌖",
  };
  const iconFor = (name = "") =>
    Object.entries(icons).find(([key]) =>
      name.toLowerCase().includes(key),
    )?.[1] || icons.default;
  const fmtNumber = (n) => Number(n || 0).toLocaleString();
  const fmtDate = (value) =>
    value
      ? new Date(value).toLocaleString([], {
          dateStyle: "medium",
          timeStyle: "short",
        })
      : "—";
  const fmtRelative = (value) => {
    if (!value) return "Never";
    const seconds = Math.max(
      0,
      (Date.now() - new Date(value).getTime()) / 1000,
    );
    if (seconds < 90) return "Just now";
    if (seconds < 3600) return `${Math.round(seconds / 60)} min ago`;
    if (seconds < 86400) return `${Math.round(seconds / 3600)} h ago`;
    return `${Math.round(seconds / 86400)} d ago`;
  };
  const batteryPercent = (level) =>
    level == null
      ? null
      : Math.max(0, Math.min(100, Math.round(Number(level) * 100)));

  function toast(message) {
    const el = $("toast");
    el.textContent = message;
    el.classList.add("visible");
    clearTimeout(toast.timer);
    toast.timer = setTimeout(() => el.classList.remove("visible"), 2600);
  }

  function setBusy(busy) {
    $("refresh-btn").disabled = busy;
    $("main-content").setAttribute("aria-busy", String(busy));
    $("live-status").lastChild.textContent = busy
      ? " Loading"
      : ` ${state.pollerLabel}`;
  }

  async function fetchJson(url) {
    const response = await fetch(url, {
      cache: "no-store",
      headers: { Accept: "application/json" },
    });
    if (!response.ok) {
      const payload = await response.json().catch(() => ({}));
      throw new Error(payload.error || `Request failed (${response.status})`);
    }
    return response.json();
  }

  function switchView(view) {
    document
      .querySelectorAll(".workspace")
      .forEach((el) => el.classList.toggle("active", el.id === `${view}-view`));
    document
      .querySelectorAll("[data-view]")
      .forEach((el) => el.classList.toggle("active", el.dataset.view === view));
    const titles = {
      map: "Overview",
      timeline: "Timeline",
      settings: "Settings",
    };
    $("page-title").textContent = titles[view] || "Overview";
    $("fit-map").hidden = view !== "map";
    document.querySelector(".metric-grid").hidden = view === "settings";
    $("filter-summary").hidden = view === "settings";
    document.body.classList.toggle("settings-active", view === "settings");
    document.querySelectorAll("[data-view]").forEach((el) => {
      el.setAttribute("aria-pressed", String(el.dataset.view === view));
    });
    if (view === "map") setTimeout(() => map.invalidateSize(), 80);
    closeSidebar();
  }

  function closeSidebar() {
    $("sidebar").classList.remove("open");
    $("sidebar-backdrop").classList.remove("visible");
  }

  function renderDevices() {
    $("device-count").textContent = state.devices.length;
    const container = $("devices-list");
    if (!state.devices.length) {
      container.innerHTML =
        '<div class="empty-inline">No devices recorded yet.</div>';
      $("active-device-label").textContent = "All devices";
      $("clear-device").hidden = true;
      return;
    }
    container.innerHTML = state.devices
      .map((device) => {
        const latest = device.latest_location || {};
        const battery = batteryPercent(latest.battery_level);
        return `<button class="device-card ${state.selectedDevice === device.id ? "active" : ""}" data-device="${escapeHtml(device.id)}" type="button" aria-pressed="${state.selectedDevice === device.id}">
        <span class="device-avatar">${iconFor(`${device.name} ${device.device_display_name || ""}`)}</span>
        <span><span class="device-name">${escapeHtml(device.name || "Unknown device")}</span><span class="device-meta">${escapeHtml(device.device_display_name || "Apple device")} · ${fmtRelative(device.last_seen)}</span></span>
        <span class="device-side"><i class="device-status"></i>${battery == null ? "" : `<span class="device-meta">${battery}%</span><span class="battery-bar"><i style="width:${battery}%"></i></span>`}</span>
      </button>`;
      })
      .join("");
    $("active-device-label").textContent = state.selectedDevice
      ? deviceName(state.selectedDevice)
      : "All devices";
    $("clear-device").hidden = !state.selectedDevice;
    container.querySelectorAll("[data-device]").forEach((button) =>
      button.addEventListener("click", () => {
        state.selectedDevice =
          state.selectedDevice === button.dataset.device
            ? null
            : button.dataset.device;
        renderDevices();
        loadLocations();
        closeSidebar();
      }),
    );
  }

  function clearMap() {
    state.markers.forEach((marker) => map.removeLayer(marker));
    state.lines.forEach((line) => map.removeLayer(line));
    state.markers = [];
    state.lines = [];
    state.bounds = [];
  }

  function renderMap() {
    clearMap();
    const grouped = {};
    state.locations.forEach((loc) => (grouped[loc.device_id] ||= []).push(loc));
    const palette = ["#38bdf8", "#5eead4", "#a78bfa", "#fbbf24", "#fb7185"];
    Object.values(grouped).forEach((items, groupIndex) => {
      items.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));
      const color = palette[groupIndex % palette.length];
      const path = items.map((loc) => [loc.latitude, loc.longitude]);
      if (path.length > 1)
        state.lines.push(
          L.polyline(path, {
            color,
            weight: 4,
            opacity: 0.72,
            lineJoin: "round",
          }).addTo(map),
        );
      items.forEach((loc, index) => {
        const latest = index === items.length - 1;
        const marker = L.circleMarker([loc.latitude, loc.longitude], {
          radius: latest ? 9 : 5,
          fillColor: latest ? "#5eead4" : color,
          color: latest ? "#ffffff" : "#dbeafe",
          weight: latest ? 3 : 1.5,
          fillOpacity: 0.9,
        }).addTo(map);
        marker.bindPopup(
          `<strong>${escapeHtml(deviceName(loc.device_id))}</strong><br>${fmtDate(loc.timestamp)}<br><span style="color:#8f9bb3">Accuracy ${loc.horizontal_accuracy ? `${Math.round(loc.horizontal_accuracy)} m` : "unknown"}</span>`,
        );
        marker.on("click", () => switchView("map"));
        state.markers.push(marker);
        state.bounds.push([loc.latitude, loc.longitude]);
      });
    });
    $("map-empty").classList.toggle("hidden", state.locations.length > 0);
    $("visible-points").textContent = fmtNumber(state.locations.length);
    if (state.bounds.length)
      map.fitBounds(state.bounds, { padding: [40, 40], maxZoom: 15 });
  }

  function renderTimeline() {
    const list = $("timeline-list");
    const rows = [...state.locations].sort(
      (a, b) => new Date(b.timestamp) - new Date(a.timestamp),
    );
    $("timeline-count").textContent = `${fmtNumber(rows.length)} points`;
    $("timeline-title").textContent = state.selectedDevice
      ? deviceName(state.selectedDevice)
      : "All devices";
    if (!rows.length) {
      list.innerHTML =
        '<div class="empty-inline">No recorded positions in this time range.</div>';
      return;
    }
    list.innerHTML = rows
      .map((loc, index) => {
        const date = new Date(loc.timestamp);
        const battery = batteryPercent(loc.battery_level);
        return `<button class="timeline-entry ${index === 0 ? "latest" : ""}" data-lat="${loc.latitude}" data-lng="${loc.longitude}">
        <span><span class="timeline-time">${date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span><span class="timeline-date">${date.toLocaleDateString([], { month: "short", day: "numeric" })}</span></span>
        <span class="timeline-rail"><i></i></span>
        <span><span class="timeline-position">${iconFor(deviceName(loc.device_id))} ${escapeHtml(deviceName(loc.device_id))}</span><span class="timeline-detail">${escapeHtml(loc.position_type || "Location")} · ${loc.horizontal_accuracy ? `${Math.round(loc.horizontal_accuracy)} m accuracy` : "accuracy unknown"}</span></span>
        <span class="timeline-battery">${battery == null ? "" : `${battery}%`}</span>
      </button>`;
      })
      .join("");
    list.querySelectorAll(".timeline-entry").forEach((entry) =>
      entry.addEventListener("click", () => {
        switchView("map");
        map.setView([Number(entry.dataset.lat), Number(entry.dataset.lng)], 16);
      }),
    );
  }

  function deviceName(id) {
    return (
      state.devices.find((device) => device.id === id)?.name ||
      id ||
      "Unknown device"
    );
  }

  function updateMetrics(stats) {
    $("metric-devices").textContent = fmtNumber(stats.total_devices);
    $("metric-locations").textContent = fmtNumber(stats.total_locations);
    const latest = stats.devices
      .map((d) => d.last_seen)
      .filter(Boolean)
      .sort()
      .at(-1);
    $("metric-latest").textContent = latest ? fmtRelative(latest) : "—";
    $("last-refresh").textContent = new Date().toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  function updateSystemStatus(system) {
    const poller = system.poller || {};
    const labels = {
      running: "Running",
      starting: "Starting",
      authenticating: "Authenticating",
      waiting_for_setup: "Setup required",
      waiting_for_authentication: "Authentication required",
      stopped: "Stopped",
      not_running: "Not running",
    };
    const label = labels[poller.state] || "Unknown";
    state.pollerLabel = label;
    $("poller-state").textContent = label;
    $("poller-success").textContent = poller.last_success_at
      ? fmtRelative(poller.last_success_at)
      : "Never";
    $("live-status").lastChild.textContent = ` ${label}`;
    $("live-status").classList.toggle(
      "degraded",
      poller.state === "waiting_for_authentication" ||
        poller.state === "waiting_for_setup" ||
        poller.state === "stopped",
    );
    $("settings-version").textContent = `v${system.version || "unknown"}`;
    $("settings-database").textContent = system.database_ready
      ? "Ready"
      : "Unavailable";
    $("settings-database").className = system.database_ready
      ? "value-good"
      : "value-warning";
    $("settings-poller").textContent = label;
    $("settings-last-poll").textContent = poller.last_success_at
      ? fmtDate(poller.last_success_at)
      : "Never";
    const configuration = system.configuration || {};
    $("settings-poll-interval").textContent =
      configuration.poll_min_interval == null
        ? "—"
        : `${configuration.poll_min_interval}–${configuration.poll_max_interval} min`;
    $("settings-retry").textContent =
      configuration.auth_retry_interval == null
        ? "—"
        : `${configuration.auth_retry_interval} min`;
    $("settings-timezone").textContent = configuration.timezone || "—";
    const requiresSetup = poller.state === "waiting_for_setup";
    const requiresAuthentication =
      poller.state === "waiting_for_authentication";
    $("system-banner").hidden = !requiresSetup && !requiresAuthentication;
    if (requiresSetup || requiresAuthentication) {
      $("system-banner-title").textContent = requiresSetup
        ? "Complete Apple setup"
        : "Apple authentication required";
      $("system-banner-message").textContent = requiresSetup
        ? "Add your Apple ID in Settings to begin recording location history."
        : "Location polling is paused. Renew the Apple session to continue recording.";
    }
  }

  async function loadStatsAndDevices() {
    const [stats, devices, system] = await Promise.all([
      fetchJson("/api/stats"),
      fetchJson("/api/devices"),
      fetchJson("/api/system/status"),
    ]);
    const byId = Object.fromEntries(
      stats.devices.map((item) => [item.id, item]),
    );
    state.devices = devices.map((device) => ({
      ...device,
      ...byId[device.id],
    }));
    renderDevices();
    updateMetrics(stats);
    updateSystemStatus(system);
  }

  function buildLocationUrl() {
    const params = new URLSearchParams({ limit: "5000" });
    if (state.selectedDevice) params.set("device_id", state.selectedDevice);
    if (state.start) params.set("start", state.start);
    else if (state.hours) params.set("hours", String(state.hours));
    if (state.end) params.set("end", state.end);
    return `/api/locations?${params}`;
  }

  async function loadLocations() {
    setBusy(true);
    try {
      state.locations = await fetchJson(buildLocationUrl());
      renderMap();
      renderTimeline();
    } catch (error) {
      toast(error.message);
    } finally {
      setBusy(false);
    }
  }

  async function refreshAll(showToast = false) {
    setBusy(true);
    try {
      await loadStatsAndDevices();
      await loadLocations();
      if (showToast) toast("Dashboard updated");
    } catch (error) {
      toast(error.message);
    } finally {
      setBusy(false);
    }
  }

  function escapeHtml(value) {
    return String(value ?? "").replace(
      /[&<>"]/g,
      (char) =>
        ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[char],
    );
  }

  document
    .querySelectorAll("[data-view]")
    .forEach((button) =>
      button.addEventListener("click", () => switchView(button.dataset.view)),
    );
  document.querySelectorAll("[data-hours]").forEach((button) =>
    button.addEventListener("click", () => {
      document
        .querySelectorAll("[data-hours]")
        .forEach((el) => el.classList.remove("active"));
      button.classList.add("active");
      state.hours = Number(button.dataset.hours);
      state.start = null;
      state.end = null;
      $("metric-range").textContent =
        state.hours === 0
          ? "All time"
          : state.hours === 24
            ? "24 hours"
            : `${state.hours / 24} days`;
      loadLocations();
    }),
  );
  $("apply-range").addEventListener("click", () => {
    state.start = $("start-time").value || null;
    state.end = $("end-time").value || null;
    if (!state.start && !state.end) return toast("Choose a start or end date");
    state.hours = 0;
    document
      .querySelectorAll("[data-hours]")
      .forEach((el) => el.classList.remove("active"));
    $("metric-range").textContent = "Custom range";
    loadLocations();
  });
  $("refresh-btn").addEventListener("click", () => refreshAll(true));
  $("clear-device").addEventListener("click", () => {
    state.selectedDevice = null;
    renderDevices();
    loadLocations();
  });
  $("system-banner-action").addEventListener("click", () =>
    switchView("settings"),
  );
  $("fit-map").addEventListener(
    "click",
    () =>
      state.bounds.length &&
      map.fitBounds(state.bounds, { padding: [40, 40], maxZoom: 15 }),
  );
  $("menu-button").addEventListener("click", () => {
    $("sidebar").classList.add("open");
    $("sidebar-backdrop").classList.add("visible");
  });
  $("mobile-devices").addEventListener("click", () => {
    $("sidebar").classList.add("open");
    $("sidebar-backdrop").classList.add("visible");
  });
  $("sidebar-close").addEventListener("click", closeSidebar);
  $("sidebar-backdrop").addEventListener("click", closeSidebar);

  refreshAll();
  setInterval(() => refreshAll(false), 5 * 60 * 1000);
})();
