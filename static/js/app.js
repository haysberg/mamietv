"use strict";

/*
 * Ce soir à la télé — front-end.
 *
 * Le backend a déjà téléchargé et découpé le guide : cette page ne fait que
 * charger /data/epg.json (même origine, aucun proxy, aucun parsing XML) et
 * l'afficher, en recalculant « en ce moment » à la volée.
 */

const DATA_URL = window.MAMIETV_DATA || "data/epg.json";
const TZ = "Europe/Paris";

const state = {
  channels: [],
  signature: "",
  day: null,
  eveningStart: 0,
  eveningEnd: 0,
};

const $ = (sel) => document.querySelector(sel);

const fmtTime = new Intl.DateTimeFormat("fr-FR", { timeZone: TZ, hour: "2-digit", minute: "2-digit" });
const fmtClock = new Intl.DateTimeFormat("fr-FR", {
  timeZone: TZ, weekday: "long", hour: "2-digit", minute: "2-digit",
});
const fmtDate = new Intl.DateTimeFormat("fr-FR", {
  timeZone: "UTC", weekday: "long", day: "numeric", month: "long",
});

function capitalize(str) {
  return str ? str.charAt(0).toUpperCase() + str.slice(1) : str;
}

function todayKey() {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: TZ, year: "numeric", month: "2-digit", day: "2-digit",
  }).format(new Date());
}

function dayOffset(day) {
  const a = Date.parse(`${day}T00:00:00Z`);
  const b = Date.parse(`${todayKey()}T00:00:00Z`);
  return Math.round((a - b) / 86400000);
}

function dayLabel(day) {
  if (!day) return "Ce soir";
  const off = dayOffset(day);
  if (off === 0) return "Ce soir";
  if (off === -1) return "Hier soir";
  if (off === 1) return "Demain soir";
  return capitalize(fmtDate.format(new Date(`${day}T12:00:00Z`)));
}

function timeLabel(iso) {
  const parts = new Intl.DateTimeFormat("fr-FR", {
    timeZone: TZ, hour: "2-digit", minute: "2-digit", hourCycle: "h23",
  }).formatToParts(new Date(iso));
  const hour = Number(parts.find((p) => p.type === "hour").value);
  const minute = Number(parts.find((p) => p.type === "minute").value);
  if (hour === 0 && minute === 0) return "minuit";
  return minute ? `${hour} h ${String(minute).padStart(2, "0")}` : `${hour} h`;
}

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

  const time = el("div", { class: "time" }, [
    document.createTextNode(fmtTime.format(new Date(start))),
    el("small", { text: fmtTime.format(new Date(stop)) }),
  ]);

  const chips = el("div", { class: "chips" }, [
    isNow ? el("span", { class: "chip now", text: "En ce moment" }) : null,
    ended ? el("span", { class: "chip", text: "Terminé" }) : null,
    program.category ? el("span", { class: "chip", text: program.category }) : null,
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
  }, [time, body]);

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
  const hasNow = Boolean(list.querySelector(".is-now"));
  return el("section", { class: `channel${hasNow ? " has-now" : ""}` }, [
    el("div", { class: "channel-head" }, [
      logo,
      el("span", { class: "channel-name", text: channel.name }),
    ]),
    list,
  ]);
}

function signature() {
  return state.channels.map((c) => `${c.id}:${visiblePrograms(c.programs).length}`).join("|");
}

function render() {
  const now = Date.now();
  const container = $("#channels");
  container.replaceChildren();
  let withNow = 0;
  for (const channel of state.channels) {
    const card = channelCard(channel, now);
    if (card.classList.contains("has-now")) withNow += 1;
    container.append(card);
  }
  state.signature = signature();

  const total = state.channels.length;
  const status = $("#status");
  status.textContent = total
    ? `${total} chaînes${withNow ? ` · ${withNow} en direct` : ""}`
    : "Aucun programme pour cette soirée.";
  status.className = total ? "status muted" : "status";
}

function updateNow() {
  const now = Date.now();
  if (signature() !== state.signature) {
    render();
    return;
  }
  document.querySelectorAll(".program").forEach((row) => {
    const start = Number(row.dataset.start);
    const stop = Number(row.dataset.stop);
    const isNow = now >= start && now < stop;
    row.classList.toggle("is-now", isNow);
    const existing = row.querySelector(".chip.now");
    if (isNow && !existing) {
      row.querySelector(".chips")?.prepend(el("span", { class: "chip now", text: "En ce moment" }));
    } else if (!isNow && existing) {
      existing.remove();
    }
  });
  document.querySelectorAll(".channel").forEach((card) => {
    card.classList.toggle("has-now", Boolean(card.querySelector(".is-now")));
  });
}

function tickClock() {
  $("#clock").textContent = capitalize(fmtClock.format(new Date()));
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

  const data = await response.json();
  state.channels = data.channels || [];
  state.day = data.day;
  state.eveningStart = Date.parse(data.evening_start);
  state.eveningEnd = Date.parse(data.evening_end);

  $("#subtitle").textContent =
    `${dayLabel(data.day)} — de ${timeLabel(data.evening_start)} à ${timeLabel(data.evening_end)}`;
  $("#generated").textContent = `Mis à jour le ${new Date(data.generated_at).toLocaleString("fr-FR")}`;
  render();
}

async function init() {
  tickClock();
  setInterval(tickClock, 20000);
  setInterval(updateNow, 30000);
  $("#refresh").addEventListener("click", async () => {
    try {
      await load(true);
    } catch (err) {
      showError();
      console.error(err);
    }
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
