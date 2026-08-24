import React, { useEffect, useRef } from 'react';
import L from 'leaflet';
import { Navigation, Compass } from 'lucide-react';

interface MapViewerProps {
  latitude: number | null;
  longitude: number | null;
  onLocationChange?: (lat: number, lng: number) => void;
  isDraggable?: boolean;
}

export const MapViewer: React.FC<MapViewerProps> = ({
  latitude,
  longitude,
  onLocationChange,
  isDraggable = true,
}) => {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<L.Map | null>(null);
  const markerRef = useRef<L.Marker | null>(null);

  const hasCoords = latitude !== null && longitude !== null && !isNaN(latitude) && !isNaN(longitude);

  useEffect(() => {
    if (!mapContainerRef.current) return;

    if (!hasCoords) {
      if (mapInstanceRef.current) {
        mapInstanceRef.current.remove();
        mapInstanceRef.current = null;
      }
      return;
    }

    const lat = latitude!;
    const lng = longitude!;

    if (!mapInstanceRef.current) {
      const map = L.map(mapContainerRef.current, {
        center: [lat, lng],
        zoom: 15,
        zoomControl: false,
      });

      L.control.zoom({ position: 'bottomright' }).addTo(map);

      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; OpenStreetMap contributors',
        maxZoom: 19,
      }).addTo(map);

      mapInstanceRef.current = map;
    } else {
      mapInstanceRef.current.setView([lat, lng], mapInstanceRef.current.getZoom());
    }

    const map = mapInstanceRef.current;

    const icon = L.divIcon({
      className: 'custom-pulse-marker',
      html: `
        <div style="position: relative; display: flex; align-items: center; justify-content: center;">
          <div style="
            background: linear-gradient(135deg, #06b6d4, #6366f1);
            width: 28px; height: 28px; border-radius: 50% 50% 50% 0;
            transform: rotate(-45deg);
            border: 2px solid white;
            box-shadow: 0 4px 12px rgba(0,0,0,0.5);
            display: flex; align-items: center; justify-content: center;
          ">
            <div style="transform: rotate(45deg); width: 8px; height: 8px; background: white; border-radius: 50%;"></div>
          </div>
        </div>
      `,
      iconSize: [32, 32],
      iconAnchor: [16, 28],
      popupAnchor: [0, -28],
    });

    if (markerRef.current) {
      markerRef.current.remove();
    }

    const marker = L.marker([lat, lng], {
      icon,
      draggable: isDraggable,
      title: isDraggable ? 'Drag pin to correct delivery location' : 'Delivery coordinate',
    }).addTo(map);

    marker.bindPopup(`
      <div style="font-family: sans-serif; padding: 4px;">
        <strong style="color: #38bdf8; font-size: 12px;">📍 Ops Coordinate</strong>
        <div style="font-size: 11px; margin-top: 2px; color: #cbd5e1;">
          Lat: ${lat.toFixed(5)}, Lng: ${lng.toFixed(5)}
        </div>
        ${isDraggable ? '<div style="font-size: 10px; color: #38bdf8; margin-top: 4px;">💡 Drag pin to relocate delivery point</div>' : ''}
      </div>
    `);

    if (isDraggable && onLocationChange) {
      marker.on('dragend', (e) => {
        const newPos = e.target.getLatLng();
        onLocationChange(newPos.lat, newPos.lng);
      });
    }

    markerRef.current = marker;
  }, [latitude, longitude, isDraggable]);

  if (!hasCoords) {
    return (
      <div className="h-[280px] w-full rounded-2xl bg-slate-950 border border-slate-800 flex flex-col items-center justify-center p-6 text-center text-slate-500">
        <Compass className="h-10 w-10 text-slate-600 mb-2 animate-pulse" />
        <p className="text-xs font-semibold text-slate-400">No Coordinates Stored</p>
        <p className="text-[11px] text-slate-500 max-w-xs mt-1">
          This address had missing postal anchors. Use the manual coordinate input below to provide exact geocoding.
        </p>
      </div>
    );
  }

  return (
    <div className="relative h-[280px] w-full rounded-2xl overflow-hidden border border-slate-800 shadow-xl bg-slate-950">
      <div ref={mapContainerRef} className="h-full w-full" />
      <div className="absolute top-2 left-2 z-[400] flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-slate-900/90 backdrop-blur-md border border-slate-800 text-[11px] font-mono text-slate-300">
        <Navigation className="h-3 w-3 text-cyan-400" />
        <span>{latitude!.toFixed(5)}, {longitude!.toFixed(5)}</span>
      </div>
    </div>
  );
};
