/* Home screen and five-step registration. Draft values survive Back/Next navigation. */
"use strict";
let data = { farms: [], reports: [], communities: [], states: [], notices: [] },
  step = -1,
  panel = "overview",
  selected = null,
  reporting = false,
  farm = null;
const draft = {
  state: "",
  lga: "",
  community: "",
  name: "",
  phone: "",
  password: "",
};
const steps = [
  "Select state",
  "Select LGA",
  "Select community",
  "Your details",
  "Select your plot",
];
function field(name, label, value = "", type = "text") {
  return `<label>${label}<input name="${name}" type="${type}" value="${escapeHTML(value)}" required></label>`;
}
function validStep() {
  return step === 0
    ? !!draft.state
    : step === 1
      ? !!draft.lga
      : step === 2
        ? !!draft.community.trim()
        : step === 3
          ? draft.name.trim().length > 1 &&
            /^(0|\+234)[789]\d{9}$/.test(draft.phone.replace(/\s/g, "")) &&
            draft.password.length >= 10
          : !!selected;
}
function topbar() {
  $("topbar").classList.toggle("expanded", step === 3);
  $("sidebar").classList.toggle("slid-out", step >= 0);
  if (step < 0) {
    $("topbar-content").innerHTML =
      `<div class="location-label" style="opacity:0;">${icon("pin")}<span>${escapeHTML(data.me?.community || "Community early warning")}<small>${escapeHTML(data.me?.lga || "Explore the community map")}</small></span></div><div class="auth-buttons">${data.me ? `<button data-panel="account" class="topbar-button">${escapeHTML(data.me.name)}</button><button data-action="logout" aria-label="Log out" class="topbar-button" style="border:none;" >${icon("logout")}</button>` : '<button class="login-button" data-action="login">Log in</button><button class="primary" data-action="signup">Sign up</button>'}</div>`;
    return;
  }
  const lgas = data.states.find((s) => s.state === draft.state)?.lgas || [];
  const communities = data.communities.filter(
    (c) => c.state === draft.state && c.lga === draft.lga,
  );
  let content = "";
  if (step === 0)
    content = `<select name="state" aria-label="Select state"><option value="">Choose your state</option>${[
      ...data.states,
    ]
      .sort((a, b) => a.state.localeCompare(b.state))
      .map((s) => option(s.state, draft.state))
      .join("")}</select>`;
  if (step === 1)
    content = `<select name="lga" aria-label="Select LGA"><option value="">Choose your LGA</option>${lgas.map((l) => option(l, draft.lga)).join("")}</select>`;
  if (step === 2)
    content = `<select id="community-choice" aria-label="Select community"><option value="">Choose a community</option>${communities.map((c) => option(c.name, draft.community)).join("")}${option("__new", draft.community && !communities.some((c) => c.name === draft.community) ? "__new" : "", "My community is not listed")}</select><div id="custom-community">${field("community", "Community name", draft.community)}</div><small>Unlisted community names are checked during admin review.</small>`;
  if (step === 3)
    content = `<div class="details-grid">${field("name", "Full name", draft.name)}${field("phone", "Phone number", draft.phone, "tel")}<div class="full-field">${field("password", "Password — at least 10 characters", draft.password, "password")}</div></div><p class="quiet-card">Enable browser push notifications from your account after registering.</p>`;
  if (step === 4)
    content = `<div class="plot-instruction">${icon("pin")}<div>${selected ? "Plot selected" : "Tap your plot on the map"}<small>${selected ? `${selected.lat.toFixed(6)}, ${selected.lng.toFixed(6)}` : "Use the location button to find your area, then adjust the pin."}</small></div></div>`;
  $("topbar-content").innerHTML =
    `<div class="registration"><div class="step-heading"><span class="step-count">0${step + 1} / 05</span><strong>${steps[step]}</strong><button class="icon-button close-register" data-action="cancel-signup" aria-label="Close registration">${icon("close")}</button></div><div class="step-content" id="registration-fields">${content}</div><div class="step-actions"><button class="back" data-action="back">${icon("back")}Back</button><span class="step-dots">${steps.map((_, i) => `<i class="${i <= step ? "filled" : ""}"></i>`).join("")}</span><button id="next" class="primary ${validStep() ? "ready" : ""}" data-action="next" ${validStep() ? "" : "disabled"}>${step === 4 ? "Submit registration" : "Next"}</button></div></div>`;
}
function transition(next) {
  document.querySelector(".step-content")?.classList.add("leaving");
  setTimeout(() => {
    step = next;
    mapView.selecting = step === 4 || reporting;
    topbar();
    mapView.draw();
    if (step === 4)
      toast("Tap your plot on the map, then submit your registration.");
  }, 180);
}
// Telephone links let the user's device open its dialler; clicking does not place a call automatically.
function callSection() {
  const contacts = data.contacts || [];
  return `<section class="call-section"><h3>Call instead</h3><p>Prefer to speak to an officer? Choose a contact below.</p>${contacts.length ? contacts.map((c) => `<a class="call-contact" href="tel:${escapeHTML(c.phone)}"><strong>${escapeHTML(c.label)}</strong><span>${escapeHTML(c.phone)}</span></a>`).join("") : "<small>No telephone contacts have been added yet.</small>"}</section>`;
}
function sidebar() {
  document
    .querySelectorAll("[data-panel]")
    .forEach((b) => b.classList.toggle("active", b.dataset.panel === panel));
  let html = "";
  if (panel === "overview")
    html = `<h1>If You See Something,<br><span>Say Something.</span></h1><p class="intro">Register your farm or report a concern without an account. Help your community respond early.</p><button class="primary report-cta" data-action="report">${icon("plus")}Report an issue</button><div class="stats"><div><strong>${data.farms.length}</strong><span>Registered farms</span></div><div><strong>${data.reports.length}</strong><span>Active advisories</span></div></div><div class="section-title">ON THE MAP</div><div class="legend-row"><i class="legend-dot farm-dot"></i>Registered farm</div><div class="legend-row"><i class="legend-dot report-dot"></i>Verified advisory</div><div class="quiet-card">${icon("shield")}<div><strong>Every report gets a review.</strong><p>Officers verify concerns before issuing community advisories.</p></div></div>`;
  if (panel === "about")
    html =
      "<h2>Your community, on the map.</h2><p>1. Sign up, choose your area and select your plot.</p><p>2. Anyone can report concerns by clicking the map or selecting a farm. No account is needed.</p><p>3. Officers verify reports, coordinate mediation and record outcomes.</p><p>Owner contact details and reporter identities remain private. Location labels and plot pins are approximate.</p>";
  if (panel === "alerts")
    html = `<h2>Active advisories</h2>${data.reports.length ? data.reports.map((r) => `<article class="advisory">${badge(r.status)}<h3>${escapeHTML(r.type)}</h3><p>${escapeHTML(r.community)}</p><small>${dateText(r.created)}</small></article>`).join("") : '<div class="empty-state"><h3>No active advisories</h3><p>An empty map does not guarantee an area is safe.</p></div>'}${data.notices.map((n) => `<article class="advisory"><p>${escapeHTML(n.message)}</p><small>${dateText(n.created)}</small></article>`).join("")}<small>Updates refresh every 20 seconds.</small>`;
  if (panel === "farm" && farm)
    html = `<div class="eyebrow">REGISTERED FARM</div><h2>${escapeHTML(farm.community)}</h2><p>Farm reference ${escapeHTML(farm.id.slice(0, 8))}</p><button class="primary" data-action="report-farm">Report an issue here</button>`;
  if (panel === "account" && data.me) {
    const u = data.me;
    html = `<h2>${escapeHTML(u.name)}</h2>${badge(u.status)}<p>${escapeHTML(u.community || "Officer account")}</p>${u.id === "admin" ? '<a href="/admin">Open admin workspace</a>' : `<p>${escapeHTML(u.phone)}</p>${u.status === "pending" ? '<div class="quiet-card">Your plot is saved and awaiting approval.</div>' : ""}<button data-action="enable-push">Enable push on this device</button><p>Browser push notifications provide case updates.</p><form id="password-form"><h3>Change password</h3>${field("old_password", "Current password", "", "password")}${field("new_password", "New password (10+ characters)", "", "password")}<button>Update password</button></form>`}`;
  }
  if (panel === "report")
    html = `<div class="eyebrow">REPORT A CONCERN</div><h2>What happened?</h2><div id="incident-location" class="selected-note">${selected ? "Location selected — tap map to adjust" : "Tap the incident location on the map"}</div><form id="report-form"><label>Incident type<select name="type">${data.types.map((t) => option(t, "")).join("")}</select></label>${field("community", "Community / nearest landmark", farm?.community || "")}${field("observed", "Time observed", localTime(), "datetime-local")}<label>Description<textarea name="description" required maxlength="2000" placeholder="Describe what you observed. Avoid assumptions."></textarea></label><button class="primary">Submit report</button><button type="button" data-action="cancel-report" style="margin:0.5rem;">Cancel</button></form>`;
  if (["overview", "report", "about"].includes(panel)) html += callSection();
  $("sidebar-content").innerHTML = html;
}
function localTime() {
  const d = new Date();
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000)
    .toISOString()
    .slice(0, 16);
}
function startReport(knownFarm = null, incidentPoint = null) {
  step = -1;
  farm = knownFarm;
  reporting = true;
  selected = incidentPoint || (farm ? { lat: farm.lat, lng: farm.lng } : null);
  panel = "report";
  mapView.selecting = true;
  mapView.selected = selected;
  mapView.draw();
  topbar();
  sidebar();
  $("sidebar").classList.add("mobile-open");
  if (selected) mapView.onPick(selected);
}
async function refresh(first = false) {
  try {
    data = await readAPI();
    // Restore the receiver after reload without prompting for permission again.
    if (data.me && data.me.id !== "admin") restorePush(data);
    await mapView.initialise(data.mapsKey, data.mapSettings);
    mapView.farms = data.farms;
    mapView.reports = data.reports;
    mapView.draw();
    if (step < 0) topbar();
    if (first || !["report", "account"].includes(panel)) sidebar();
  } catch (e) {
    toast(e.message);
    if (first)
      $("sidebar-content").innerHTML =
        '<p>Could not load records.</p><button data-action="reload">Try again</button>';
  }
}
mapView.onPick = async (point) => {
  selected = point;
  mapView.selected = point;
  mapView.draw();
  if (step === 4) topbar();
  if (reporting) {
    $("incident-location").textContent =
      "Location selected — tap elsewhere to adjust";
    try {
      const result = await api("geocode", point);
      const input = document.querySelector('#report-form [name="community"]');
      if (result.label && input && !input.value) input.value = result.label;
    } catch (e) {
      console.warn(e.message);
    }
  }
};
mapView.onReportHere = (point) => startReport(null, point);
mapView.onFarm = (point) => {
  if (step === 4) {
    mapView.onPick(point);
    return;
  }
  farm = point;
  panel = "farm";
  sidebar();
  $("sidebar").classList.add("mobile-open");
};
// Delegation keeps events working when a registration step is replaced.
document.addEventListener("input", (event) => {
  if (event.target.closest("#registration-fields") && event.target.name) {
    draft[event.target.name] = event.target.value;
    const next = $("next");
    next.disabled = !validStep();
    next.classList.toggle("ready", validStep());
  }
});
document.addEventListener("change", (event) => {
  const el = event.target;
  if (el.id === "map-type") {
    mapView.setType(el.value);
    return;
  }
  if (!el.closest("#registration-fields")) return;
  if (el.name === "state") {
    draft.state = el.value;
    draft.lga = "";
    draft.community = "";
  }
  if (el.name === "lga") {
    draft.lga = el.value;
    draft.community = "";
    mapView.focusArea(draft.state, draft.lga);
  }
  if (el.id === "community-choice") {
    draft.community = el.value === "__new" ? "" : el.value;
    document.querySelector('[name="community"]').value = draft.community;
  }
  $("next").disabled = !validStep();
  $("next").classList.toggle("ready", validStep());
});
document.addEventListener("click", (event) => {
  const button = event.target.closest("button");
  if (!button) return;
  if (button.dataset.panel) {
    panel = button.dataset.panel;
    reporting = false;
    mapView.selecting = step === 4;
    sidebar();
    return;
  }
  // Submit buttons are handled by the submit event, not the click handler.
  if (!button.dataset.action) return;
  withButton(button, async () => {
    switch (button.dataset.action) {
      case "signup":
        $("login-modal").hidden = true;
        reporting = false;
        step = 0;
        topbar();
        break;
      case "cancel-signup":
        step = -1;
        selected = null;
        mapView.selected = null;
        mapView.selecting = false;
        mapView.draw();
        topbar();
        break;
      case "back":
        transition(step - 1);
        break;
      case "next":
        if (!validStep()) return;
        if (step < 4) transition(step + 1);
        else {
          const r = await api("register", { ...draft, ...selected });
          toast(r.message);
          step = -1;
          selected = null;
          mapView.selected = null;
          mapView.selecting = false;
          panel = "account";
          await refresh();
          topbar();
          sidebar();
        }
        break;
      case "login":
        $("login-modal").hidden = false;
        break;
      case "close-login":
        $("login-modal").hidden = true;
        break;
      case "logout":
        await api("logout");
        panel = "overview";
        await refresh();
        break;
      case "toggle-panel":
        $("sidebar").classList.toggle("mobile-open");
        break;
      case "zoom-in":
        mapView.zoom(1);
        break;
      case "zoom-out":
        mapView.zoom(-1);
        break;
      case "locate":
        mapView.locate();
        break;
      case "report":
        startReport();
        break;
      case "report-farm":
        startReport(farm);
        break;
      case "cancel-report":
        reporting = false;
        mapView.selecting = false;
        mapView.selected = null;
        mapView.draw();
        panel = "overview";
        sidebar();
        break;
      case "enable-push":
        await enablePush(data);
        break;
      case "reload":
        await refresh(true);
        break;
    }
  });
});
document.addEventListener("submit", (event) => {
  event.preventDefault();
  const form = event.target;
  withButton(form.querySelector('button[type="submit"],button'), async () => {
    const values = formValues(form);
    if (form.id === "login-form") {
      await api("login", values);
      $("login-modal").hidden = true;
      form.reset();
      await refresh();
    }
    if (form.id === "password-form") {
      await api("change_password", values);
      form.reset();
      toast("Password updated.");
    }
    if (form.id === "report-form") {
      if (!selected)
        throw new Error("Select the incident location on the map.");
      values.observed = new Date(values.observed).toISOString();
      const result = await api("report", {
        ...values,
        ...selected,
        farmId: farm?.id || null,
      });
      toast(result.message);
      reporting = false;
      mapView.selecting = false;
      mapView.selected = null;
      panel = "overview";
      await refresh();
    }
  });
});
refresh(true);
setInterval(() => refresh(), 20000);
