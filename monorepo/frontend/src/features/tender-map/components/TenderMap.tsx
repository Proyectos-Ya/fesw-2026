"use client";

import "leaflet/dist/leaflet.css";
import "react-leaflet-cluster/dist/assets/MarkerCluster.css";
import L, { type MarkerCluster } from "leaflet";
import { useEffect } from "react";
import { MapContainer, Marker, Popup, TileLayer, useMap } from "react-leaflet";
import MarkerClusterGroup from "react-leaflet-cluster";
import type { RegionCenter } from "../data/regionCenters";
import type { TenderMapPoint } from "../types";
import { TenderMapSummary } from "./TenderMapSummary";

export interface TenderMapProps {
  center: RegionCenter;
  points: TenderMapPoint[];
}

// Íconos propios en vez de las imágenes de Leaflet: el bundler de Next no
// resuelve las rutas que Leaflet arma para `marker-icon.png`, y el marcador
// sale como una imagen rota.
const MARKER_ICON = L.divIcon({
  className: "",
  html: '<span class="block size-4 rounded-full border-2 border-white bg-primary shadow-md"></span>',
  iconSize: [16, 16],
  iconAnchor: [8, 8],
  popupAnchor: [0, -8],
});

function clusterIcon(cluster: MarkerCluster): L.DivIcon {
  const count = cluster.getChildCount();
  return L.divIcon({
    className: "",
    html: `<span class="flex size-10 items-center justify-center rounded-full border-2 border-white bg-primary font-mono text-sm font-bold text-white shadow-md" aria-label="${count} licitaciones">${count}</span>`,
    iconSize: [40, 40],
  });
}

/** `MapContainer` solo lee el centro al montarse: los cambios de zona se aplican acá. */
function FlyToZone({ center }: { center: RegionCenter }) {
  const map = useMap();
  useEffect(() => {
    map.flyTo([center.lat, center.lng], center.zoom, { duration: 0.8 });
  }, [map, center]);
  return null;
}

/**
 * Mapa de Leaflet con un marcador por licitación, agrupados cuando están
 * cerca (HU-22, #314). Se carga solo en el navegador: Leaflet usa `window`.
 */
export default function TenderMap({ center, points }: TenderMapProps) {
  return (
    <MapContainer
      center={[center.lat, center.lng]}
      zoom={center.zoom}
      scrollWheelZoom
      className="h-[70vh] min-h-[420px] w-full rounded-lg border border-border-subtle"
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <FlyToZone center={center} />
      <MarkerClusterGroup chunkedLoading iconCreateFunction={clusterIcon}>
        {points.map((point) => (
          <Marker
            key={point.id}
            position={[point.lat, point.lng]}
            icon={MARKER_ICON}
            title={point.name}
          >
            <Popup>
              <TenderMapSummary point={point} />
            </Popup>
          </Marker>
        ))}
      </MarkerClusterGroup>
    </MapContainer>
  );
}
