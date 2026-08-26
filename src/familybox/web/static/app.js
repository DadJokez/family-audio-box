(() => {
  "use strict";

  const formatTime = (seconds) => {
    if (!Number.isFinite(seconds) || seconds < 0) return "--:--";
    const rounded = Math.floor(seconds);
    const hours = Math.floor(rounded / 3600);
    const minutes = Math.floor((rounded % 3600) / 60);
    const remainder = rounded % 60;
    return hours > 0
      ? `${hours}:${String(minutes).padStart(2, "0")}:${String(remainder).padStart(2, "0")}`
      : `${minutes}:${String(remainder).padStart(2, "0")}`;
  };

  const bindText = (name, value) => {
    document.querySelectorAll(`[data-bind="${name}"]`).forEach((node) => {
      node.textContent = value;
    });
  };

  const updateStatus = (payload) => {
    const playback = payload.playback || {};
    const nfc = payload.nfc || {};
    bindText("title", playback.title || "Nothing playing");
    bindText("track_title", playback.track_title || "Place a known tag on the box");
    bindText("play_label", playback.playing ? "Pause" : "Play");
    bindText("state_label", playback.state_label || "Ready");
    bindText("track_number", playback.track_number || "—");
    bindText("track_count", playback.track_count ?? 0);
    bindText("volume", Math.round(playback.volume ?? 50));
    bindText("position_label", formatTime(playback.position_seconds ?? 0));
    bindText("duration_label", formatTime(playback.duration_seconds));
    bindText("resume_label", playback.resume_label || "No position yet");
    bindText("nfc_uid", nfc.uid || "Waiting for a tag");
    if (nfc.last_unknown_uid) bindText("last_unknown_uid", nfc.last_unknown_uid);
    const unknownCard = document.querySelector("[data-unknown-card]");
    if (
      unknownCard &&
      nfc.last_unknown_uid &&
      unknownCard.dataset.currentUnknown !== nfc.last_unknown_uid
    ) {
      window.location.reload();
      return;
    }

    const duration = playback.duration_seconds || 0;
    const position = playback.position_seconds || 0;
    const percent = duration > 0 ? Math.min(100, Math.max(0, (position / duration) * 100)) : 0;
    document.querySelectorAll("[data-progress-bar]").forEach((node) => {
      node.style.width = `${percent}%`;
    });
    document.querySelectorAll("[data-volume]").forEach((node) => {
      if (document.activeElement !== node) node.value = playback.volume ?? 50;
    });
  };

  let requestInFlight = false;
  const refreshStatus = async () => {
    if (requestInFlight || document.hidden) return;
    requestInFlight = true;
    try {
      const response = await fetch("/api/status", { headers: { Accept: "application/json" } });
      if (response.ok) updateStatus(await response.json());
    } catch (_) {
      // Physical playback remains independent if the web process or network drops.
    } finally {
      requestInFlight = false;
    }
  };

  document.querySelectorAll("[data-action]").forEach((button) => {
    button.addEventListener("click", async () => {
      button.disabled = true;
      try {
        const response = await fetch(`/api/controls/${button.dataset.action}`, { method: "POST" });
        if (response.ok) updateStatus(await response.json());
      } finally {
        button.disabled = false;
      }
    });
  });

  let volumeTimer;
  document.querySelectorAll("[data-volume]").forEach((slider) => {
    slider.addEventListener("input", () => {
      bindText("volume", slider.value);
      window.clearTimeout(volumeTimer);
      volumeTimer = window.setTimeout(async () => {
        const data = new FormData();
        data.set("volume", slider.value);
        const response = await fetch("/api/volume", { method: "POST", body: data });
        if (response.ok) updateStatus(await response.json());
      }, 120);
    });
  });

  document.querySelectorAll("[data-dialog-open]").forEach((button) => {
    button.addEventListener("click", () => document.getElementById(button.dataset.dialogOpen)?.showModal());
  });
  document.querySelectorAll("[data-dialog-close]").forEach((button) => {
    button.addEventListener("click", () => button.closest("dialog")?.close());
  });
  document.querySelectorAll("dialog").forEach((dialog) => {
    dialog.addEventListener("click", (event) => {
      if (event.target === dialog) dialog.close();
    });
  });

  const devForm = document.querySelector("[data-dev-nfc]");
  if (devForm) {
    devForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      await fetch("/api/dev/nfc", { method: "POST", body: new FormData(devForm) });
      await refreshStatus();
    });
    devForm.querySelector("[data-dev-remove]")?.addEventListener("click", async () => {
      await fetch("/api/dev/nfc/remove", { method: "POST" });
      await refreshStatus();
    });
  }

  refreshStatus();
  window.setInterval(refreshStatus, 2000);
})();
