/*
 * MamieTV service worker.
 *
 * Makes the app installable and usable offline: the page shell is cached on
 * install, static assets use stale-while-revalidate, and the guide
 * (`data/epg.json`) is network-first so a returning user gets the latest
 * program and the previous one only when offline.
 */

const CACHE = "mamietv-v1";

const CORE = [
	"./",
	"index.html",
	"manifest.webmanifest",
	"css/style.css",
	"js/app.js",
	"icons/icon-192.png",
	"icons/icon-512.png",
	"icons/apple-touch-icon.png",
	"favicon.ico",
];

self.addEventListener("install", (event) => {
	event.waitUntil(
		caches
			.open(CACHE)
			.then((cache) => cache.addAll(CORE))
			.then(() => self.skipWaiting()),
	);
});

self.addEventListener("activate", (event) => {
	event.waitUntil(
		caches
			.keys()
			.then((keys) => Promise.all(keys.filter((key) => key !== CACHE).map((key) => caches.delete(key))))
			.then(() => self.clients.claim()),
	);
});

self.addEventListener("fetch", (event) => {
	const request = event.request;
	if (request.method !== "GET") return;

	const url = new URL(request.url);
	if (url.origin !== self.location.origin) return;

	if (request.mode === "navigate") {
		event.respondWith(networkFirst(request, "index.html", true));
		return;
	}
	if (url.pathname.endsWith("/data/epg.json")) {
		event.respondWith(networkFirst(request));
		return;
	}
	event.respondWith(staleWhileRevalidate(request));
});

async function networkFirst(request, fallbackUrl, noStore) {
	const cache = await caches.open(CACHE);
	try {
		const response = await fetch(request, noStore ? { cache: "no-store" } : {});
		if (response && response.ok) cache.put(request, response.clone());
		return response;
	} catch (error) {
		const cached = (await cache.match(request)) || (fallbackUrl && (await cache.match(fallbackUrl)));
		if (cached) return cached;
		return new Response("Hors ligne — le programme n'est pas encore disponible.", {
			status: 503,
			headers: { "Content-Type": "text/plain; charset=utf-8" },
		});
	}
}

async function staleWhileRevalidate(request) {
	const cache = await caches.open(CACHE);
	const cached = await cache.match(request);
	const network = fetch(request)
		.then((response) => {
			if (response && response.ok) cache.put(request, response.clone());
			return response;
		})
		.catch(() => cached);
	return cached || network;
}
