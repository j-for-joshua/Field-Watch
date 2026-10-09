/* Firebase handles background notifications. Only public Firebase config is sent here. */
importScripts(
  "https://www.gstatic.com/firebasejs/10.14.1/firebase-app-compat.js",
);
importScripts(
  "https://www.gstatic.com/firebasejs/10.14.1/firebase-messaging-compat.js",
);
const config = new URL(self.location.href).searchParams.get("config");
if (config) {
  firebase.initializeApp(JSON.parse(config));
  firebase.messaging();
}
