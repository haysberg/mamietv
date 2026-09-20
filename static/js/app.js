"use strict";

/*
 * MamieTV — front-end.
 *
 * La page est rendue côté serveur : le HTML contient déjà les programmes, donc
 * rien ne bouge au chargement. Ce script ne gère que le dépliage d'un
 * programme, le marquage « Terminé », le rechargement automatique du guide et
 * l'installation de la PWA.
 */

const DATA_URL = window.MAMIETV_DATA || "data/epg.json";
const REFRESH_MS = 15 * 60 * 1000;
const MIN_REFRESH_GAP_MS = 60 * 1000;

const channelsElement = document.getElementById("channels");
let lastRefresh = 0;

function updateEnded() {
  const now = Date.now();
  const rows = document.querySelectorAll(".program");
  for (let i = 0; i < rows.length; i += 1) {
    const row = rows[i];
    const ended = Number(row.getAttribute("data-stop")) <= now;
    row.classList.toggle("is-ended", ended);

    const chips = row.querySelector(".chips");
    if (!chips) continue;
    const existing = row.querySelector(".chip.ended");
    if (ended && !existing) {
      const chip = document.createElement("span");
      chip.className = "chip ended";
      chip.textContent = "Terminé";
      chips.appendChild(chip);
    } else if (!ended && existing) {
      existing.remove();
    }
  }
}

function toggleProgram(row) {
  row.classList.toggle("expanded");
  const button = row.querySelector(".more");
  if (button) {
    button.textContent = row.classList.contains("expanded") ? "Moins de détails" : "Plus de détails";
  }
}

async function refresh() {
  lastRefresh = Date.now();
  try {
    const url = DATA_URL + (DATA_URL.indexOf("?") === -1 ? "?" : "&") + "t=" + Date.now();
    const response = await fetch(url, { cache: "no-store" });
    if (!response.ok) return;
    const data = await response.json();
    const current = channelsElement && channelsElement.getAttribute("data-generated-at");
    // New guide available: reload so the freshly server-rendered HTML is shown.
    if (data.generated_at !== current) window.location.reload();
  } catch (err) {
    console.warn("Rafraîchissement du guide impossible :", err);
  }
}

function init() {
  if (channelsElement) {
    channelsElement.addEventListener("click", (event) => {
      const row = event.target.closest(".program");
      if (row) toggleProgram(row);
    });
  }

  updateEnded();
  setInterval(updateEnded, 30000);
  setInterval(refresh, REFRESH_MS);
  // Coming back to the tab/app (typically the next day on a phone) checks too.
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden && Date.now() - lastRefresh > MIN_REFRESH_GAP_MS) refresh();
  });
}

init();

// Installable PWA: the service worker precaches the shell and serves the guide
// network-first (falling back to the last copy when offline).
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("sw.js").catch((err) => console.warn("Service worker", err));
  });
}

// "Installer" button, shown only when the app is not already running as an
// installed PWA. Uses the native prompt when the browser offers one, otherwise
// points to the "Add to Home Screen" browser menu (iOS Safari).
const installButton = document.getElementById("install");
let installPrompt = null;

function isInstalledPWA() {
  const modes = ["standalone", "fullscreen", "minimal-ui"];
  for (let i = 0; i < modes.length; i += 1) {
    if (window.matchMedia("(display-mode: " + modes[i] + ")").matches) return true;
  }
  return window.navigator.standalone === true;
}

function updateInstallButton() {
  if (installButton) installButton.hidden = isInstalledPWA();
}

if (installButton) {
  updateInstallButton();

  window.addEventListener("beforeinstallprompt", (event) => {
    event.preventDefault();
    installPrompt = event;
    updateInstallButton();
  });

  installButton.addEventListener("click", async () => {
    if (installPrompt) {
      installPrompt.prompt();
      await installPrompt.userChoice;
      installPrompt = null;
      updateInstallButton();
    } else {
      window.alert(
        "Pour installer MamieTV : ouvrez le menu du navigateur, puis " +
          "« Installer l'application » ou « Ajouter à l'écran d'accueil ».",
      );
    }
  });

  window.addEventListener("appinstalled", () => {
    installPrompt = null;
    updateInstallButton();
  });
}
