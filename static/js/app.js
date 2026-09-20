"use strict";

/*
 * MamieTV — front-end.
 *
 * Le backend a déjà téléchargé et découpé le guide : cette page ne fait que
 * charger data/epg.json (même origine) et l'afficher. « En ce moment » est
 * recalculé en continu, et le guide est rechargé tout seul pour ne jamais
 * rester bloqué sur une soirée périmée.
 */

const DATA_URL = window.MAMIETV_DATA || "data/epg.json";
const TZ = "Europe/Paris";
const REFRESH_MS = 15 * 60 * 1000;
const MIN_REFRESH_GAP_MS = 60 * 1000;

const state = {
  channels: [],
  eveningStart: 0,
  eveningEnd: 0,
  generatedAt: null,
};
let lastLoad = 0;

const $ = (sel) => document.querySelector(sel);

const fmtTime = new Intl.DateTimeFormat("fr-FR", {
  timeZone: TZ, hour: "2-digit", minute: "2-digit",
});

function el(tag, props = {}, children = []) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(props)) {
    if (key === "class") node.className = value;
    else if (key === "text") node.textContent = value;
    else if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
    else if (value !== null && value !== undefined) node.setAttribute(key, value);
  }
  for (const child of [].concat(children)) if (child) node.append(child);
  return node;
}

function visiblePrograms(programs) {
  // Strict prime time: only programs that *start* in [eveningStart, eveningEnd].
  return programs.filter((p) => {
    const start = Date.parse(p.start);
    return start >= state.eveningStart && start < state.eveningEnd;
  });
}

function programRow(program, now) {
  const start = Date.parse(program.start);
  const stop = Date.parse(program.stop);
  const isNow = now >= start && now < stop;
  const ended = stop <= now;

  const chips = el("div", { class: "chips" }, [
    el("span", { class: "time", text: fmtTime.format(new Date(start)) }),
    program.category ? el("span", { class: "chip", text: program.category }) : null,
    isNow ? el("span", { class: "chip now", text: "En ce moment" }) : null,
    ended ? el("span", { class: "chip ended", text: "Terminé" }) : null,
  ]);

  const body = el("div", { class: "program-body" }, [
    el("p", { class: "program-title", text: program.title }),
    program.subtitle ? el("p", { class: "program-sub", text: program.subtitle }) : null,
    chips,
    program.desc ? el("p", { class: "desc", text: program.desc }) : null,
    program.desc && program.desc.length > 140
      ? el("button", { class: "more", type: "button", text: "Plus de détails" })
      : null,
  ]);

  const row = el("li", {
    class: `program${isNow ? " is-now" : ""}${ended ? " is-ended" : ""}`,
    "data-start": String(start),
    "data-stop": String(stop),
  }, [body]);

  row.addEventListener("click", () => {
    row.classList.toggle("expanded");
    const button = row.querySelector(".more");
    if (button) {
      button.textContent = row.classList.contains("expanded")
        ? "Moins de détails" : "Plus de détails";
    }
  });
  return row;
}

function channelCard(channel, now) {
  const logo = channel.icon
    ? el("img", { src: channel.icon, alt: "", loading: "lazy", referrerpolicy: "no-referrer" })
    : el("span", { class: "no-logo", text: "📺" });

  const list = el("ul", { class: "programs" });
  for (const program of visiblePrograms(channel.programs)) {
    list.append(programRow(program, now));
  }

  const head = el("div", { class: "channel-head" }, [
    logo,
    el("span", { class: "channel-name", text: channel.name }),
    channel.number ? el("span", { class: "channel-number", text: String(channel.number) }) : null,
  ]);

  return el("section", { class: `channel${list.querySelector(".is-now") ? " has-now" : ""}` }, [
    head,
    list,
  ]);
}

function render() {
  const now = Date.now();
  const container = $("#channels");
  container.replaceChildren();
  for (const channel of state.channels) {
    container.append(channelCard(channel, now));
  }

  const status = $("#status");
  status.className = "status";
  status.textContent = state.channels.length ? "" : "Aucun programme pour cette soirée.";
}

function updateNow() {
  const now = Date.now();
  document.querySelectorAll(".program").forEach((row) => {
    const start = Number(row.dataset.start);
    const stop = Number(row.dataset.stop);
    const isNow = now >= start && now < stop;
    const ended = stop <= now;
    row.classList.toggle("is-now", isNow);
    row.classList.toggle("is-ended", ended);

    const chips = row.querySelector(".chips");
    if (!chips) return;

    const existingNow = row.querySelector(".chip.now");
    if (isNow && !existingNow) {
      chips.append(el("span", { class: "chip now", text: "En ce moment" }));
    } else if (!isNow && existingNow) {
      existingNow.remove();
    }

    const existingEnded = row.querySelector(".chip.ended");
    if (ended && !existingEnded) {
      chips.append(el("span", { class: "chip ended", text: "Terminé" }));
    } else if (!ended && existingEnded) {
      existingEnded.remove();
    }
  });

  document.querySelectorAll(".channel").forEach((card) => {
    card.classList.toggle("has-now", Boolean(card.querySelector(".is-now")));
  });
}

function showError() {
  const status = $("#status");
  status.className = "status error";
  status.textContent = "Impossible de charger le programme. Réessayez dans un instant.";
}

async function load(force = false) {
  const url = force ? `${DATA_URL}${DATA_URL.includes("?") ? "&" : "?"}t=${Date.now()}` : DATA_URL;
  const response = await fetch(url, { cache: force ? "no-store" : "default" });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  lastLoad = Date.now();

  const data = await response.json();
  // Unchanged guide: keep what is on screen (and its scroll position).
  if (data.generated_at === state.generatedAt) return;

  state.generatedAt = data.generated_at;
  state.channels = data.channels || [];
  state.eveningStart = Date.parse(data.evening_start);
  state.eveningEnd = Date.parse(data.evening_end);

  $("#generated").textContent = `Mis à jour le ${new Date(data.generated_at).toLocaleString("fr-FR")}`;
  render();
}

async function refresh() {
  try {
    await load(true);
  } catch (err) {
    // Offline or transient: the current guide stays displayed.
    console.warn("Rafraîchissement du guide impossible :", err);
  }
}

async function init() {
  setInterval(updateNow, 30000);
  setInterval(refresh, REFRESH_MS);
  // Coming back to the tab/app (typically the next day on a phone) reloads it.
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden && Date.now() - lastLoad > MIN_REFRESH_GAP_MS) refresh();
  });

  try {
    await load(false);
  } catch (err) {
    showError();
    console.error(err);
  }
}

init();

// Installable PWA: the service worker precaches the shell and serves the guide
// network-first (falling back to the last copy when offline).
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("sw.js").catch((err) => console.warn("Service worker", err));
  });
}
