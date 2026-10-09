/* Map provider wrapper. Coordinates are always {lat, lng}, regardless of provider. */
"use strict";
const mapView = {
  map: null,
  provider: "",
  key: null,
  markers: [],
  group: null,
  userLocation: null,
  selected: null,
  farms: [],
  reports: [],
  selecting: false,
  onPick: () => {},
  onFarm: () => {},
  watch: null,
  popup: null,
  viewChosen: false,
  areaVersion: 0,
  onReportHere: () => {},
  async initialise(key, defaults = {}) {
    if (this.map && this.key === key) return;
    this.key = key;
    const start = {
      lat: Number(defaults.lat ?? 7.732),
      lng: Number(defaults.lng ?? 8.539),
    };
    const startZoom = Number(defaults.zoom ?? 13);
    const startType = defaults.type || "roadmap";
    if (this.watch !== null) navigator.geolocation.clearWatch(this.watch);
    if (this.provider === "leaflet" && this.map) this.map.remove();
    this.markers.forEach((marker) => marker.setMap?.(null));
    this.markers = [];
    $("map").innerHTML = "";
    try {
      if (key) {
        if (!window.google?.maps)
          await loadScript(
            "https://maps.googleapis.com/maps/api/js?key=" +
              encodeURIComponent(key),
          );
        window.gm_authFailure = () =>
          toast(
            "Google Maps rejected the key. Check its restrictions in Admin settings.",
          );
        this.provider = "google";
        this.map = new google.maps.Map($("map"), {
          center: start,
          zoom: startZoom,
          mapTypeId: startType,
          disableDefaultUI: true,
          clickableIcons: false,
          gestureHandling: "greedy",
        });
        this.map.addListener("click", (event) => {
          this.handleClick({
            lat: event.latLng.lat(),
            lng: event.latLng.lng(),
          });
        });
        $("map-credit").textContent = "Google Maps";
      } else {
        if (!window.L)
          throw new Error(
            "The map could not load. Check your internet connection.",
          );
        this.provider = "leaflet";
        this.map = L.map("map", { zoomControl: false }).setView(
          [start.lat, start.lng],
          startZoom,
        );
        L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
          maxZoom: 19,
          attribution:
            '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
        }).addTo(this.map);
        this.group = L.layerGroup().addTo(this.map);
        this.map.on("click", (event) => {
          this.handleClick({ lat: event.latlng.lat, lng: event.latlng.lng });
        });
        $("map-credit").textContent =
          "OpenStreetMap · Google Maps not connected";
      }
      // Live location is only displayed; it is not silently submitted as an incident.
      // Display the live-location marker without overriding the officer's saved opening view.
      if (navigator.geolocation)
        this.watch = navigator.geolocation.watchPosition(
          (position) => {
            this.userLocation = {
              lat: position.coords.latitude,
              lng: position.coords.longitude,
            };
            this.draw();
          },
          () => {},
          { enableHighAccuracy: true, maximumAge: 30000, timeout: 10000 },
        );
      // Older cached templates may not contain the map-view dropdown yet.
      const typeSelect = $("map-type");
      if (typeSelect) {
      typeSelect.value = this.provider === "google" ? startType : "roadmap";
      typeSelect.disabled = this.provider !== "google";
      typeSelect.title =
        this.provider === "google"
          ? "Choose a map view"
          : "Satellite view requires a connected Google Maps key";
      }
      this.draw();
    } catch (error) {
      console.error(error);
      toast(error.message);
    }
  },
  centre(point, zoom) {
    if (!this.map) return;
    this.viewChosen = true;
    if (this.provider === "google") {
      this.map.setCenter(point);
      if (zoom) this.map.setZoom(zoom);
    } else this.map.setView([point.lat, point.lng], zoom || this.map.getZoom());
  },
  // A normal map click opens an anchored question. Plot/report selection places a pin directly.
  handleClick(point) {
    if (this.selecting) {
      this.onPick(point);
      return;
    }
    this.popup?.close?.();
    const content = document.createElement("div");
    const title = document.createElement("strong");
    title.textContent = "Report issue here?";
    const button = document.createElement("button");
    button.className = "primary";
    button.textContent = "Report issue here";
    button.type = "button";
    button.addEventListener("click", (event) => {
      event.stopPropagation();
      this.popup?.close?.();
      if (this.provider === "leaflet") this.map.closePopup();
      this.onReportHere(point);
    });
    content.className = "report-map-popup";
    content.append(title, button);
    if (this.provider === "google") {
      this.popup = new google.maps.InfoWindow({ content, position: point });
      this.popup.open({ map: this.map });
    } else {
      this.popup = L.popup()
        .setLatLng([point.lat, point.lng])
        .setContent(content)
        .openOn(this.map);
    }
  },
  setType(type) {
    if (this.provider !== "google") {
      toast("Connect Google Maps to use satellite and terrain views.");
      return;
    }
    if (!["roadmap", "satellite", "hybrid", "terrain"].includes(type)) return;
    this.map.setMapTypeId(type);
    if ($("map-type")) $("map-type").value = type;
  },
  async focusArea(state, lga) {
    if (!state || !lga || !this.map) return;
    const version = ++this.areaVersion;
    this.viewChosen = true; // Late geolocation callbacks must not move the view away from the chosen LGA.
    try {
      if (this.provider === "google") {
        this.setType("satellite");
        const result = await new google.maps.Geocoder().geocode({
          address: `${lga} Local Government Area, ${state}, Nigeria`,
          componentRestrictions: { country: "NG" },
        });
        if (version !== this.areaVersion) return;
        const place = result.results[0];
        if (!place)
          throw new Error(
            "Google could not locate this LGA. Use the map or location button to find your plot.",
          );
        if (place.geometry.viewport)
          this.map.fitBounds(place.geometry.viewport, 50);
        else
          this.centre(
            {
              lat: place.geometry.location.lat(),
              lng: place.geometry.location.lng(),
            },
            12,
          );
      } else {
        const place = await api("lookup_area", { state, lga });
        if (version !== this.areaVersion) return;
        this.centre(place, 12);
      }
      toast(
        `Map moved to ${lga}, ${state}. Zoom in and confirm your plot's position.`,
      );
    } catch (error) {
      console.warn(error);
      toast(
        "Could not locate the LGA automatically. Enable Geocoding API for your key, or move the map manually.",
      );
    }
  },
  zoom(amount) {
    if (this.map) this.map.setZoom(this.map.getZoom() + amount);
  },
  locate() {
    if (!navigator.geolocation) {
      toast("Location is unavailable. Select a point manually.");
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (position) => {
        const point = {
          lat: position.coords.latitude,
          lng: position.coords.longitude,
        };
        this.userLocation = point;
        this.centre(point, 16);
        if (this.selecting) this.onPick(point);
        this.draw();
        toast(
          `Location accuracy: approximately ${Math.round(position.coords.accuracy)} metres. Adjust the pin if needed.`,
        );
      },
      () =>
        toast(
          "Location unavailable. Move the map and select a point manually.",
        ),
      { enableHighAccuracy: true, timeout: 12000 },
    );
  },
  draw() {
    if (!this.map) return;
    const points = [
      ...this.farms.map((f) => ({ ...f, kind: "farm" })),
      ...this.reports.map((r) => ({ ...r, kind: "report" })),
      ...(this.selected ? [{ ...this.selected, kind: "selected" }] : []),
      ...(this.userLocation
        ? [{ ...this.userLocation, kind: "location" }]
        : []),
    ];
    this.markers.forEach((marker) => marker.setMap?.(null));
    this.markers = [];
    this.group?.clearLayers();
    points.forEach((point) => {
      const colour =
        point.kind === "report"
          ? "#db8f22"
          : point.kind === "location"
            ? "#378ff1"
            : "#078271";
      if (this.provider === "google") {
        const marker = new google.maps.Marker({
          position: { lat: point.lat, lng: point.lng },
          map: this.map,
          title: point.kind === "farm" ? "Registered farm" : point.kind,
          icon: {
            path: google.maps.SymbolPath.CIRCLE,
            scale: point.kind === "selected" ? 12 : 9,
            fillColor: colour,
            fillOpacity: 1,
            strokeColor: "#fff",
            strokeWeight: 3,
          },
        });
        if (point.kind === "farm")
          marker.addListener("click", () => this.onFarm(point));
        this.markers.push(marker);
      } else {
        const marker = L.circleMarker([point.lat, point.lng], {
          radius: point.kind === "selected" ? 12 : 8,
          color: "#fff",
          weight: 3,
          fillColor: colour,
          fillOpacity: 1,
          bubblingMouseEvents: false,
        }).addTo(this.group);
        const tooltip = document.createElement("span");
        tooltip.textContent =
          point.kind === "farm"
            ? "Registered farm · " + point.community
            : point.type || point.kind;
        marker.bindTooltip(tooltip);
        if (point.kind === "farm") marker.on("click", () => this.onFarm(point));
      }
    });
    $("map").classList.toggle("picking", this.selecting);
  },
};
