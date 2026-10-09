/* Shared helpers: plain JavaScript, with no React or build step. */
"use strict";
const $ = (id) => document.getElementById(id);
// Escape every database/user value before placing it in an HTML template.
const escapeHTML = (value = "") =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const icon = (name, size = 20) =>
  `<svg class="icon" width="${size}" height="${size}" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><use href="/static/icons/icons.svg#${name}"></use></svg>`;
const dateText = (value) => new Date(value).toLocaleString();
const formValues = (form) => Object.fromEntries(new FormData(form).entries());
const option = (value, selected, label = value) =>
  `<option value="${escapeHTML(value)}" ${value === selected ? "selected" : ""}>${escapeHTML(label)}</option>`;
const badge = (status) =>
  `<span class="badge ${status === "pending" || status === "unavailable" ? "amber" : ""}">${escapeHTML(status.replaceAll("_", " "))}</span>`;
let toastTimer;
function toast(message) {
  $("toast").innerHTML =
    `${icon("info")}<span>${escapeHTML(message)}</span><button aria-label="Dismiss message" onclick="this.parentElement.hidden=true">${icon("close", 17)}</button>`;
  $("toast").hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => ($("toast").hidden = true), 10000);
}
async function readAPI(admin = false) {
  const response = await fetch(
    "/api/fieldwatch" + (admin ? "?view=admin" : ""),
  );
  const data = await response.json();
  if (!response.ok) {
    const error = new Error(data.error || "Could not load records.");
    error.status = response.status;
    throw error;
  }
  return data;
}
async function api(action, fields = {}) {
  const response = await fetch("/api/fieldwatch", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRF-Token": document.querySelector('meta[name="csrf-token"]').content,
    },
    body: JSON.stringify({ action, ...fields }),
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Could not save changes.");
  return data;
}
async function withButton(button, task) {
  if (button?.disabled) return;
  if (button) button.disabled = true;
  try {
    await task();
  } catch (error) {
    console.error(error);
    toast(error.message);
  } finally {
    if (button) button.disabled = false;
  }
}
function loadScript(url) {
  return new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = url;
    script.onload = resolve;
    script.onerror = () =>
      reject(
        new Error("Could not load an external service. Check your connection."),
      );
    document.head.appendChild(script);
  });
}
// Initialise once per page and restore the token after refresh or login.
let pushSetup = null, pushUnsubscribe = null, pushUser = null;
async function connectPush(config) {
  if (!config.firebase || !config.vapidKey)
    throw new Error("The administrator needs to connect Firebase and its public push key.");
  if (!window.isSecureContext)
    throw new Error("Push requires HTTPS, or localhost when testing on this computer.");
  if (!("Notification" in window) || !("serviceWorker" in navigator))
    throw new Error("Push notifications are unavailable in this browser.");
  if (!window.firebase) {
    await loadScript("https://www.gstatic.com/firebasejs/10.14.1/firebase-app-compat.js");
    await loadScript("https://www.gstatic.com/firebasejs/10.14.1/firebase-messaging-compat.js");
  }
  if (!(await firebase.messaging.isSupported()))
    throw new Error("This browser does not support Firebase push notifications.");
  if (!firebase.apps.length) firebase.initializeApp(config.firebase);
  const registration = await navigator.serviceWorker.register(
    "/firebase-messaging-sw.js?config=" + encodeURIComponent(JSON.stringify(config.firebase)),
  );
  await navigator.serviceWorker.ready;
  const messaging = firebase.messaging();
  // Firebase automatically displays background notification payloads. When
  // the page has focus, show an in-app alert and a desktop notification here.
  if (pushUnsubscribe) pushUnsubscribe();
  pushUnsubscribe = messaging.onMessage(async (payload) => {
    const notice = payload.notification || {};
    const title = notice.title || "Fieldwatch advisory";
    const body = notice.body || "A case has been updated. Check your account.";
    toast(body);
    try {
      if (Notification.permission === "granted") {
        await registration.showNotification(title, {
          body,
          tag: payload.data?.notificationId || payload.messageId || "fieldwatch-advisory",
          icon: "/static/icons/favicon.svg",
        });
      }
    } catch (error) {
      console.error("Could not display the desktop notification:", error);
    }
  });
  const token = await messaging.getToken({
    vapidKey: config.vapidKey, serviceWorkerRegistration: registration,
  });
  if (!token) throw new Error("Firebase did not return a device token. Try enabling push again.");
  await api("push", { token });
  pushUser = config.me?.id;
}
async function setupPush(config) {
  // Avoid two SDK loads when the refresh timer overlaps a button click.
  if (!pushSetup) pushSetup = connectPush(config).finally(() => { pushSetup = null; });
  return pushSetup;
}
async function enablePush(config) {
  if (!("Notification" in window)) throw new Error("This browser does not support notifications.");
  if ((await Notification.requestPermission()) !== "granted")
    throw new Error("Push permission was not granted. Allow notifications in this site's browser settings.");
  await setupPush(config);
  toast("Push enabled on this device.");
}
function restorePush(config) {
  if (pushUser === config.me?.id || !config.firebase || !config.vapidKey ||
      !("Notification" in window) || Notification.permission !== "granted") return;
  // Never request permission without a click. Errors stay visible in the console.
  setupPush(config).catch((error) => console.error("Push connection failed:", error));
}
document
  .querySelectorAll("[data-icon]")
  .forEach((element) => (element.innerHTML = icon(element.dataset.icon)));
// Escape closes dialogs without discarding the underlying registration form.
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape")
    document
      .querySelectorAll(".modal-backdrop")
      .forEach((el) => (el.hidden = true));
});
document.querySelectorAll(".modal-backdrop").forEach((el) =>
  el.addEventListener("click", (event) => {
    if (event.target === el) el.hidden = true;
  }),
);
