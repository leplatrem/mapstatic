import {
  LeafletMap,
  TileLayer,
  GeoJSON,
  CircleMarker,
  ZoomControl,
} from "leaflet";

const map = new LeafletMap("map", {
  zoomControl: false,
  scrollWheelZoom: false,
});
new ZoomControl({ position: "bottomright" }).addTo(map);

const configResponse = await fetch("./map-config.json");
const config = await configResponse.json();
new TileLayer(config.tileUrl, {
  maxZoom: 19,
  attribution: config.tileAttribution,
}).addTo(map);
const response = await fetch("./features.geojson");
const data = await response.json();
const styleResponse = await fetch("./style.json");
const style = await styleResponse.json();
const detailsResponse = await fetch("./details.json");
const details = await detailsResponse.json();
const panel = document.querySelector("#detail-panel");
const panelContent = document.querySelector("#detail-content");
const closeButton = document.querySelector("#close-panel");

function closePanel() {
  panel.hidden = true;
  panel.setAttribute("aria-hidden", "true");
  map.getContainer().focus();
}

function openPanel(featureId) {
  panelContent.innerHTML = details[featureId];
  panel.hidden = false;
  panel.setAttribute("aria-hidden", "false");
  closeButton.focus();
}

closeButton.addEventListener("click", closePanel);
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && !panel.hidden) closePanel();
});

const layer = new GeoJSON(data, {
  pointToLayer: (_feature, latlng) => new CircleMarker(latlng, style.point),
  style: () => style.geometry,
  onEachFeature: (feature, item) => {
    const title = feature.properties.title;
    const tooltip = document.createElement("span");
    tooltip.textContent = title;
    item.bindTooltip(tooltip, {
      sticky: true,
      direction: "top",
      className: "feature-tooltip",
      opacity: 0.96,
    });
    item.on("click", () => openPanel(feature.id));
  },
}).addTo(map);
const bounds = layer.getBounds();
if (bounds.isValid()) map.fitBounds(bounds, { padding: [48, 48], maxZoom: 14 });
else map.setView([20, 0], 2);
