import { useEffect, useRef } from "react";
import { MapContainer, TileLayer, Marker, Polyline, Popup, useMap } from "react-leaflet";
import L from "leaflet";
import type { Drone, Corridor } from "../types";

// Custom drone icon
const droneIcon = new L.DivIcon({
  className: "",
  html: `<div style="
    width: 20px; height: 20px;
    background: #3b82f6;
    border: 2px solid white;
    border-radius: 50%;
    box-shadow: 0 0 10px rgba(59,130,246,0.6);
  "></div>`,
  iconSize: [20, 20],
  iconAnchor: [10, 10],
});

const startIcon = new L.DivIcon({
  className: "",
  html: `<div style="
    width: 14px; height: 14px;
    background: #22c55e;
    border: 2px solid white;
    border-radius: 50%;
  "></div>`,
  iconSize: [14, 14],
  iconAnchor: [7, 7],
});

const endIcon = new L.DivIcon({
  className: "",
  html: `<div style="
    width: 14px; height: 14px;
    background: #ef4444;
    border: 2px solid white;
    border-radius: 50%;
  "></div>`,
  iconSize: [14, 14],
  iconAnchor: [7, 7],
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
}

export function DroneMap({ drone, corridor }: Props) {
  const defaultCenter: [number, number] = [37.79, -122.35]; // SF Bay Area
  const dronePos: [number, number] | null = drone?.position
    ? [drone.position.lat, drone.position.lon]
    : null;

  // Corridor path from start to end (simple line)
  const corridorPath: [number, number][] = [];
  if (corridor?.start && corridor?.end) {
    corridorPath.push(
      [corridor.start.lat, corridor.start.lon],
      [corridor.end.lat, corridor.end.lon]
    );
  }

  return (
    <div className="bg-gray-900/50 rounded-xl border border-gray-800 overflow-hidden h-full">
      <div className="px-4 py-3 bg-gray-900/80 border-b border-gray-800 flex items-center justify-between">
        <span className="text-white font-medium text-sm">Corridor Map</span>
        {drone && (
          <span className="text-xs text-gray-400">
            Block {drone.blockIndex}/{drone.totalBlocks}
            {drone.status === "DEVIATING" && (
              <span className="text-red-400 ml-2">
                DEVIATING {drone.deviationMeters?.toFixed(0)}m
              </span>
            )}
          </span>
        )}
      </div>

      <MapContainer
        center={dronePos || defaultCenter}
        zoom={12}
        className="h-[500px] w-full"
        style={{ background: "#111827" }}
      >
        <TileLayer
          url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a>'
        />

        <MapUpdater center={dronePos} />

        {/* Corridor path */}
        {corridorPath.length >= 2 && (
          <>
            <Polyline
              positions={corridorPath}
              pathOptions={{ color: "#3b82f6", weight: 3, opacity: 0.6, dashArray: "8 4" }}
            />
            <Marker position={corridorPath[0]} icon={startIcon}>
              <Popup>Start: {corridor?.name}</Popup>
            </Marker>
            <Marker position={corridorPath[corridorPath.length - 1]} icon={endIcon}>
              <Popup>End</Popup>
            </Marker>
          </>
        )}

        {/* Drone marker */}
        {dronePos && (
          <Marker position={dronePos} icon={droneIcon}>
            <Popup>
              <div className="text-xs">
                <strong>Flight: {drone!.flightId}</strong>
                <br />
                Status: {drone!.status}
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
