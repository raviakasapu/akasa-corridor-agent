import { useEffect, useMemo } from "react";
import {
  MapContainer,
  TileLayer,
  Marker,
  Polyline,
  Polygon,
  Popup,
  useMap,
} from "react-leaflet";
import L from "leaflet";
import { cellToBoundary } from "h3-js";
import type { Drone, Corridor } from "../types";

// Custom drone icon — bright blue with white border
const droneIcon = new L.DivIcon({
  className: "",
  html: `<div style="
    width: 22px; height: 22px;
    background: #2563eb;
    border: 3px solid white;
    border-radius: 50%;
    box-shadow: 0 0 12px rgba(37,99,235,0.7);
  "></div>`,
  iconSize: [22, 22],
  iconAnchor: [11, 11],
});

const startIcon = new L.DivIcon({
  className: "",
  html: `<div style="
    width: 16px; height: 16px;
    background: #16a34a;
    border: 3px solid white;
    border-radius: 50%;
    box-shadow: 0 0 6px rgba(22,163,74,0.5);
  "></div>`,
  iconSize: [16, 16],
  iconAnchor: [8, 8],
});

const endIcon = new L.DivIcon({
  className: "",
  html: `<div style="
    width: 16px; height: 16px;
    background: #dc2626;
    border: 3px solid white;
    border-radius: 50%;
    box-shadow: 0 0 6px rgba(220,38,38,0.5);
  "></div>`,
  iconSize: [16, 16],
  iconAnchor: [8, 8],
});

function MapUpdater({ center }: { center: [number, number] | null }) {
  const map = useMap();
  useEffect(() => {
    if (center) {
      map.setView(center, map.getZoom(), { animate: true });
    }
  }, [center, map]);
  return null;
}

interface Props {
  drone: Drone | null;
  corridor: Corridor | null;
  flightTrail: [number, number][];
}

export function DroneMap({ drone, corridor, flightTrail }: Props) {
  const defaultCenter: [number, number] = [37.79, -122.35];
  const dronePos: [number, number] | null = drone?.position
    ? [drone.position.lat, drone.position.lon]
    : null;

  // Corridor center line from start to end
  const corridorPath: [number, number][] = [];
  if (corridor?.start && corridor?.end && corridor.start.lat !== 0) {
    corridorPath.push(
      [corridor.start.lat, corridor.start.lon],
      [corridor.end.lat, corridor.end.lon]
    );
  }

  // Convert H3 cell IDs to polygon boundaries
  const hexPolygons = useMemo(() => {
    if (!corridor?.rail || corridor.rail.length === 0) return [];
    return corridor.rail.map((cellId) => {
      try {
        // cellToBoundary returns [[lat, lng], ...] by default
        const boundary = cellToBoundary(cellId);
        return boundary.map(([lat, lng]) => [lat, lng] as [number, number]);
      } catch {
        return null;
      }
    }).filter(Boolean) as [number, number][][];
  }, [corridor?.rail]);

  return (
    <div className="bg-white rounded-xl border border-gray-200 overflow-hidden h-full shadow-sm">
      <div className="px-4 py-3 bg-gray-50 border-b border-gray-200">
        <div className="flex items-center justify-between">
          <span className="text-gray-800 font-semibold text-sm">Corridor Map</span>
          {drone && (
            <span className="text-xs text-gray-500">
              Block {drone.blockIndex}/{drone.totalBlocks}
              {drone.progressPercent !== undefined && (
                <span className="ml-2 text-blue-600">{drone.progressPercent.toFixed(0)}%</span>
              )}
              {drone.status === "DEVIATING" && (
                <span className="text-red-600 font-medium ml-2">
                  DEVIATING {drone.deviationMeters?.toFixed(0)}m
                </span>
              )}
              {drone.status === "NOMINAL" && (
                <span className="text-green-600 font-medium ml-2">NOMINAL</span>
              )}
              {drone.status === "COMPLETE" && (
                <span className="text-green-700 font-medium ml-2">COMPLETE</span>
              )}
            </span>
          )}
        </div>
        {drone?.environment && (
          <div className="flex items-center gap-3 mt-1 text-[10px] text-gray-400">
            <span>Wind: {drone.environment.wind_speed_mps.toFixed(1)}m/s @ {drone.environment.wind_direction_deg.toFixed(0)}&deg;</span>
            <span>GPS noise: {drone.environment.gps_noise_meters.toFixed(1)}m</span>
            <span>Turb: {(drone.environment.turbulence_intensity * 100).toFixed(0)}%</span>
            {drone.autopilot && (
              <>
                <span>Corrections: {drone.autopilot.cumulative_corrections}</span>
                {drone.autopilot.correction_applied && (
                  <span className="text-amber-600 font-medium">CORRECTING</span>
                )}
              </>
            )}
          </div>
        )}
      </div>

      <MapContainer
        center={dronePos || defaultCenter}
        zoom={12}
        className="h-[500px] w-full"
        style={{ background: "#f9fafb" }}
      >
        <TileLayer
          url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a>'
        />

        <MapUpdater center={dronePos} />

        {/* H3 hexagonal corridor cells */}
        {hexPolygons.map((positions, i) => (
          <Polygon
            key={i}
            positions={positions}
            pathOptions={{
              color: "#3b82f6",
              weight: 1,
              fillColor: "#93c5fd",
              fillOpacity: 0.25,
            }}
          />
        ))}

        {/* Corridor center line */}
        {corridorPath.length >= 2 && (
          <>
            <Polyline
              positions={corridorPath}
              pathOptions={{
                color: "#2563eb",
                weight: 2,
                opacity: 0.5,
                dashArray: "6 4",
              }}
            />
            <Marker position={corridorPath[0]} icon={startIcon}>
              <Popup>
                <span style={{ fontWeight: 600 }}>Start:</span> {corridor?.name}
              </Popup>
            </Marker>
            <Marker
              position={corridorPath[corridorPath.length - 1]}
              icon={endIcon}
            >
              <Popup>
                <span style={{ fontWeight: 600 }}>End</span>
              </Popup>
            </Marker>
          </>
        )}

        {/* Flight trail (breadcrumb path) */}
        {flightTrail.length >= 2 && (
          <Polyline
            positions={flightTrail}
            pathOptions={{
              color: "#f59e0b",
              weight: 3,
              opacity: 0.8,
            }}
          />
        )}

        {/* Drone marker */}
        {dronePos && (
          <Marker position={dronePos} icon={droneIcon}>
            <Popup>
              <div style={{ fontSize: 12, lineHeight: 1.6 }}>
                <strong>Flight: {drone!.flightId}</strong>
                <br />
                Status:{" "}
                <span
                  style={{
                    color:
                      drone!.status === "NOMINAL"
                        ? "#16a34a"
                        : drone!.status === "DEVIATING"
                        ? "#dc2626"
                        : "#6b7280",
                    fontWeight: 600,
                  }}
                >
                  {drone!.status}
                </span>
                <br />
                Block: {drone!.blockIndex}/{drone!.totalBlocks}
                {drone!.deviationMeters > 0 && (
                  <>
                    <br />
                    Deviation: {drone!.deviationMeters.toFixed(1)}m
                  </>
                )}
              </div>
            </Popup>
          </Marker>
        )}
      </MapContainer>
    </div>
  );
}
