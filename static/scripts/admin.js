/* Officer workspace: approval, case history, warning rules and delivery logs. */
"use strict";
let records = null,
  publicData = null,
  tab = "users",
  filter = "pending";
const titles = {
  contacts: "Call instead contacts",
  users: "Approve new users",
  reports: "Resolve issues",
  warnings: "Early warnings",
  notifications: "Notification log",
  settings: "Settings & communities",
};
const input = (name, label, value = "", type = "text") =>
  `<label>${label}<input name="${name}" type="${type}" step="any" value="${escapeHTML(value)}" required></label>`;
const empty = (title, text) =>
  `<div class="admin-empty">${icon("shield", 32)}<h2>${title}</h2><p>${text}</p></div>`;
function modal(html) {
  $("admin-modal-content").innerHTML =
    `<button class="modal-close icon-button" data-action="close-modal" aria-label="Close">${icon("close")}</button>${html}`;
  $("admin-modal").hidden = false;
}
async function refresh(paint = true) {
  try {
    records = await readAPI(true);
    if (!publicData) publicData = await readAPI();
    $("admin-login").hidden = true;
    $("admin-layout").hidden = false;
    $("admin-logout").hidden = false;
    $("admin-loading").hidden = true;
    if (paint) render();
  } catch (e) {
    $("admin-loading").hidden = true;
    if (e.status === 403) {
      $("admin-login").hidden = false;
      $("admin-layout").hidden = true;
      $("admin-logout").hidden = true;
    } else toast(e.message);
  }
}
const contactTab = document.createElement("button");
contactTab.dataset.tab = "contacts";
contactTab.textContent = "Call instead contacts";
document
  .querySelector(".admin-nav")
  .insertBefore(contactTab, document.querySelector(".admin-nav-foot"));
function render() {
  $("admin-heading").innerHTML =
    `<div class="eyebrow">FIELDWATCH / ${tab.toUpperCase()}</div><h1>${titles[tab]}</h1>`;
  $("admin-stats").innerHTML = [
    [
      "Awaiting approval",
      records.users.filter((u) => u.status === "pending").length,
    ],
    [
      "Approved farms",
      records.users.filter((u) => u.status === "approved").length,
    ],
    [
      "Open reports",
      records.reports.filter(
        (r) => !["resolved", "rejected"].includes(r.status),
      ).length,
    ],
  ]
    .map(
      ([label, n]) => `<div><span>${label}</span><strong>${n}</strong></div>`,
    )
    .join("");
  document
    .querySelectorAll("[data-tab]")
    .forEach((b) => b.classList.toggle("active", b.dataset.tab === tab));
  let html = "";
  if (tab === "users") {
    const users = records.users.filter(
      (u) => filter === "all" || u.status === filter,
    );
    html = `<div class="admin-toolbar"><div class="segmented">${["pending", "approved", "rejected", "all"].map((s) => `<button data-filter="${s}" class="${filter === s ? "active" : ""}">${s}</button>`).join("")}</div><button class="primary" data-action="add-farm">Add farm</button></div><div class="data-card">${users.length ? `<div class="table-scroll"><table><thead><tr><th>Farmer</th><th>Community</th><th>Plot</th><th>Status</th><th>Review</th></tr></thead><tbody>${users.map((u) => `<tr><td><strong>${escapeHTML(u.name)}</strong><small>${escapeHTML(u.phone)}</small></td><td>${escapeHTML(u.community)}<small>${escapeHTML(u.lga)}, ${escapeHTML(u.state)}</small></td><td><a href="https://www.google.com/maps?q=${u.lat},${u.lng}" target="_blank" rel="noreferrer">${u.lat.toFixed(4)}, ${u.lng.toFixed(4)}</a></td><td>${badge(u.status)}</td><td><div class="row-actions">${u.status !== "approved" ? `<button data-approve="${u.id}" data-status="approved">Approve</button>` : ""}${u.status !== "rejected" ? `<button class="reject" data-approve="${u.id}" data-status="rejected">Reject</button>` : ""}</div></td></tr>`).join("")}</tbody></table></div>` : empty("No registrations here", "Submitted registrations will appear here for review.")}</div>`;
  }
  if (tab === "reports")
    html = `<div class="data-card">${records.reports.length ? records.reports.map((r) => `<button class="report-row" data-report="${r.id}"><span class="report-icon">${icon("warning")}</span><span><strong>${escapeHTML(r.type)}</strong><small>${escapeHTML(r.community)} · ${dateText(r.observed)}</small></span>${badge(r.status)}<span class="review-link">Review</span></button>`).join("") : empty("No reports to review", "New concerns will appear with their location and observation time.")}</div>`;
  if (tab === "warnings")
    html = `<div class="data-card">${records.warnings.length ? records.warnings.map((r) => `<article class="warning-row">${icon("warning")}<div><h3>${escapeHTML(r.community)}</h3><p>Multiple reporter sessions submitted nearby concerns. Verify the reports before issuing an advisory.</p><button data-report="${r.id}">Review report</button></div></article>`).join("") : empty("No pattern flags", `At least ${escapeHTML(records.settings.threshold)} reporter sessions within ${Number(records.settings.radius) / 1000} km over ${escapeHTML(records.settings.window_hours)} hours are required. A flag prompts review; it does not prove a conflict.`)}</div>`;
  if (tab === "notifications")
    html = `<div class="data-card">${records.notifications.length ? `<div class="table-scroll"><table><thead><tr><th>Recipient / message</th><th>Channel</th><th>Result</th><th>Action</th></tr></thead><tbody>${records.notifications.map((n) => `<tr><td><strong>${escapeHTML(n.name)}</strong><p>${escapeHTML(n.message)}</p></td><td>${escapeHTML(n.channel)}</td><td>${badge(n.status)}<small>${escapeHTML(n.detail)}</small></td><td>${["retry", "failed", "unavailable", "queued"].includes(n.status) ? `<button data-retry="${escapeHTML(n.id)}">Retry</button>` : ""}</td></tr>`).join("")}</tbody></table></div>` : empty("No delivery attempts yet", "Verified reports generate advisories for nearby approved farms.")}</div>`;
  if (tab === "settings") {
    const s = records.settings;
    html = `<div class="settings-grid"><form id="settings-form" class="data-card settings-card"><h2>Map & warning rules</h2><label>Google Maps browser API key<input name="maps_key" value="${escapeHTML(s.maps_key)}"></label><small>Restrict your key to your website. The fallback map is used until a key is connected.</small><h3>Map opening view</h3><div class="details-grid">${input("default_lat", "Default latitude", s.default_lat, "number")}${input("default_lng", "Default longitude", s.default_lng, "number")}</div>${input("default_zoom", "Default zoom (1–20)", s.default_zoom, "number")}<label>Default map view<select name="default_type">${[
      ["roadmap", "Map"],
      ["satellite", "Satellite"],
      ["hybrid", "Satellite + labels"],
      ["terrain", "Terrain"],
    ]
      .map(([v, l]) => option(v, s.default_type, l))
      .join(
        "",
      )}</select></label><small>Refresh the map after saving. Live location will not override this starting view.</small>${input("radius", "Alert radius (metres)", s.radius, "number")}${input("window_hours", "Review window (hours)", s.window_hours, "number")}${input("threshold", "Distinct reporters", s.threshold, "number")}<button class="primary">Save settings</button></form><div><section class="data-card settings-card"><h2>Delivery services</h2>${[
      ["maps", "Google Maps"],
      ["push", "Push notifications"],
    ]
      .map(
        ([key, label]) =>
          `<div class="service">${label}${badge(records.services[key] ? "configured" : "unavailable")}</div>`,
      )
      .join(
        "",
      )}<p>Missing provider credentials must be configured on the server. Messages are never labelled delivered simply because they were queued.</p></section><form id="community-form" class="data-card settings-card"><h2>Add a community</h2>${areaFields()}${input("name", "Community name")}<button class="primary">Add community</button></form><form id="admin-password-form" class="data-card settings-card"><h2>Change admin password</h2>${input("old_password", "Current password", "", "password")}${input("new_password", "New password (10+ characters)", "", "password")}<button class="primary">Change password</button></form></div></div>`;
  }
  if (tab === "contacts")
    html = `<div class="settings-grid"><form id="contact-form" class="data-card settings-card"><h2>Add or edit a contact</h2><input type="hidden" name="id" value="">${input("label", "Name / office")}${input("phone", "Telephone number", "", "tel")}<small>Publish numbers belonging to officers or offices responsible for responding to reports.</small><button class="primary">Save contact</button></form><div class="data-card settings-card"><h2>Published contacts</h2>${records.contacts.length ? records.contacts.map((c) => `<article class="contact-admin"><strong>${escapeHTML(c.label)}</strong><p>${escapeHTML(c.phone)}</p><div class="row-actions"><button data-edit-contact="${c.id}">Edit</button><button class="reject" data-delete-contact="${c.id}">Remove</button></div></article>`).join("") : "<p>No contacts added yet.</p>"}</div></div>`;
  $("admin-content").innerHTML = html;
}
function areaFields() {
  return `<label>State<select name="state" data-area-state required><option value="">Choose state</option>${[
    ...publicData.states,
  ]
    .sort((a, b) => a.state.localeCompare(b.state))
    .map((s) => option(s.state, ""))
    .join(
      "",
    )}</select></label><label>LGA<select name="lga" required><option value="">Choose LGA</option></select></label>`;
}
function caseModal(id) {
  const r = records.reports.find((r) => r.id === id);
  if (!r) return;
  modal(
    `<div class="eyebrow">CASE ${r.id.slice(0, 8)}</div><h2>${escapeHTML(r.type)}</h2><p>${escapeHTML(r.community)}</p><p>${escapeHTML(r.description)}</p><small>Observed ${dateText(r.observed)} · Reporter: ${escapeHTML(records.users.find((u) => u.id === r.user_id)?.name || (r.user_id.startsWith("guest:") ? "Anonymous reporter" : "Administrator"))}</small><a class="case-map-link" target="_blank" rel="noreferrer" href="https://www.google.com/maps?q=${r.lat},${r.lng}">View incident location</a><form id="case-form"><input type="hidden" name="id" value="${r.id}"><label>Case status<select name="status">${[
      ["under_review", "Verified · Under review"],
      ["mediation", "In mediation"],
      ["resolved", "Resolved"],
      ["rejected", "Rejected / duplicate"],
    ]
      .map(([s, l]) =>
        option(s, r.status === "submitted" ? "under_review" : r.status, l),
      )
      .join(
        "",
      )}</select></label><label>Assigned officer / mediator<input name="mediator" value="${escapeHTML(r.mediator)}"></label><label>Action taken / outcome<textarea name="note" required maxlength="2000"></textarea></label><button class="primary">Save case update</button></form><h3>Case history</h3>${records.events
      .filter((e) => e.report_id === r.id)
      .map(
        (e) =>
          `<article class="history-item"><strong>${escapeHTML(e.status.replaceAll("_", " "))}</strong><p>${escapeHTML(e.note)}</p><small>${dateText(e.created)}</small></article>`,
      )
      .join("")}`,
  );
}
function farmModal() {
  modal(
    `<h2>Add a farm</h2><p>Give the owner their initial password securely. Registration will enter the approval queue.</p><form id="farm-form">${input("name", "Full name")}${input("phone", "Phone number", "", "tel")}${input("password", "Initial password (10+ characters)", "", "password")}${areaFields()}${input("community", "Community name")}<div class="details-grid"><label>Latitude<input name="lat" type="number" step="any" required></label><label>Longitude<input name="lng" type="number" step="any" required></label></div><p>Farmers receive browser push notifications after enabling their device.</p><button class="primary">Add registration</button></form>`,
  );
}
document.addEventListener("change", (event) => {
  if (event.target.matches("[data-area-state]")) {
    const form = event.target.closest("form");
    form.elements.lga.innerHTML =
      '<option value="">Choose LGA</option>' +
      (
        publicData.states.find((s) => s.state === event.target.value)?.lgas ||
        []
      )
        .map((l) => option(l, ""))
        .join("");
  }
});
document.addEventListener("click", (event) => {
  const b = event.target.closest("button");
  if (!b) return;
  if (b.dataset.tab) {
    tab = b.dataset.tab;
    render();
    return;
  }
  if (b.dataset.filter) {
    filter = b.dataset.filter;
    render();
    return;
  }
  if (b.dataset.editContact) {
    const contact = records.contacts.find(
      (c) => c.id === b.dataset.editContact,
    );
    const form = $("contact-form");
    form.elements.id.value = contact.id;
    form.elements.label.value = contact.label;
    form.elements.phone.value = contact.phone;
    form.elements.label.focus();
    return;
  }
  if (b.dataset.report) {
    caseModal(b.dataset.report);
    return;
  }
  if (
    !b.dataset.action &&
    !b.dataset.approve &&
    !b.dataset.retry &&
    !b.dataset.deleteContact
  )
    return;
  withButton(b, async () => {
    if (b.dataset.approve) {
      await api("approve", { id: b.dataset.approve, status: b.dataset.status });
      await refresh();
      toast("Registration updated.");
    }
    if (b.dataset.deleteContact) {
      await api("delete_contact", { id: b.dataset.deleteContact });
      await refresh();
      toast("Contact removed.");
    }
    if (b.dataset.retry) {
      await api("retry", { id: b.dataset.retry });
      await refresh();
      toast("Delivery retried. Check the result.");
    }
    if (b.dataset.action === "close-modal") $("admin-modal").hidden = true;
    if (b.dataset.action === "add-farm") farmModal();
    if (b.dataset.action === "logout") {
      await api("logout");
      await refresh();
    }
  });
});
// Surface required-field errors explicitly, including notes required for a case update.
document.addEventListener("invalid", (event) => {
  if (event.target.closest("#case-form")) toast(event.target.validationMessage || "Complete the required case fields.");
}, true);
document.addEventListener("submit", (event) => {
  event.preventDefault();
  const form = event.target;
  withButton(event.submitter || form.querySelector("button"), async () => {
    const values = formValues(form);
    // A field named "id" can shadow HTMLFormElement.id. Read the HTML attribute instead.
    switch (form.getAttribute("id")) {
      case "admin-login-form":
        await api("login", { ...values, admin: true });
        form.reset();
        await refresh();
        return;
      case "contact-form":
        await api("save_contact", values);
        toast("Contact saved.");
        break;
      case "settings-form":
        await api("settings", values);
        toast("Settings saved.");
        break;
      case "community-form":
        await api("community", values);
        publicData = await readAPI();
        toast("Community added.");
        break;
      case "case-form":
        await api("update_report", values);
        $("admin-modal").hidden = true;
        toast("Case saved. Notifications are sent automatically; check the delivery log.");
        break;
      case "farm-form":
        await api("admin_add", {
          ...values,
          lat: Number(values.lat),
          lng: Number(values.lng),
        });
        $("admin-modal").hidden = true;
        tab = "users";
        filter = "pending";
        toast("Farm added to the approval queue.");
        break;
      case "admin-password-form":
        await api("change_password", values);
        toast("Administrator password changed.");
        break;
    }
    await refresh();
  });
});
refresh();
// Background refresh never replaces an active form and discards unsaved typing.
setInterval(
  () =>
    refresh(!["settings", "contacts"].includes(tab) && $("admin-modal").hidden),
  20000,
);
