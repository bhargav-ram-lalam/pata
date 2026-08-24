import React, { useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import { MapPin, Navigation, Compass, Check, ArrowRight, RotateCcw, AlertTriangle } from 'lucide-react';
import { confirmResolution, resolveCorrection } from '../services/api';

interface MapViewerProps {
  latitude: number | null;
  longitude: number | null;
  confidence: number;
  needsHumanReview: boolean;
  requestId?: string;
  landmarkMatch?: {
    name?: string;
    lat?: number;
    lon?: number;
    osm_id?: number | string;
    distance_m?: number;
  } | null;
  onLocationUpdated?: (newLat: number, newLng: number) => void;
}

export const MapViewer: React.FC<MapViewerProps> = ({
  latitude,
  longitude,
  confidence,
  needsHumanReview,
  requestId,
  landmarkMatch,
  onLocationUpdated,
}) => {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<L.Map | null>(null);
  const mainMarkerRef = useRef<L.Marker | null>(null);
  const poiMarkerRef = useRef<L.Marker | null>(null);
  const polylineRef = useRef<L.Polyline | null>(null);

  const [draggedCoords, setDraggedCoords] = useState<{ lat: number; lng: number } | null>(null);
  const [isConfirming, setIsConfirming] = useState(false);
  const [confirmStatus, setConfirmStatus] = useState<string | null>(null);

  const isMedium = confidence >= 0.5 && confidence < 0.8;
  const hasValidCoords = latitude !== null && longitude !== null && !isNaN(latitude) && !isNaN(longitude);

  // Initialize or update Leaflet map
  useEffect(() => {
    if (!mapContainerRef.current) return;

    if (!hasValidCoords) {
      if (mapInstanceRef.current) {
        mapInstanceRef.current.remove();
        mapInstanceRef.current = null;
      }
      return;
    }

    const currentLat = draggedCoords?.lat ?? latitude!;
    const currentLng = draggedCoords?.lng ?? longitude!;

    // Create map if not exists
    if (!mapInstanceRef.current) {
      const map = L.map(mapContainerRef.current, {
        center: [currentLat, currentLng],
        zoom: 15,
        zoomControl: false,
      });

      L.control.zoom({ position: 'bottomright' }).addTo(map);

      // OpenStreetMap Standard Tiles (No API key needed, matches backend OSM/Overpass usage)
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        maxZoom: 19,
      }).addTo(map);

      mapInstanceRef.current = map;
    } else {
      mapInstanceRef.current.setView([currentLat, currentLng], mapInstanceRef.current.getZoom());
    }

    const map = mapInstanceRef.current;

    // Custom Icon for resolved point
    const tierColor = confidence >= 0.8 ? '#10b981' : confidence >= 0.5 ? '#f59e0b' : '#f43f5e';
    const mainIcon = L.divIcon({
      className: 'custom-pulse-marker',
      html: `
        <div style="position: relative; display: flex; align-items: center; justify-content: center;">
          <div class="marker-pulse-ring" style="background-color: ${tierColor}40;"></div>
          <div style="
            background: linear-gradient(135deg, ${tierColor}, #0284c7);
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
      iconSize: [36, 36],
      iconAnchor: [18, 32],
      popupAnchor: [0, -32],
    });

    // Remove existing main marker
    if (mainMarkerRef.current) {
      mainMarkerRef.current.remove();
    }

    // Create main marker (draggable if medium tier)
    const marker = L.marker([currentLat, currentLng], {
      icon: mainIcon,
      draggable: isMedium,
      title: isMedium ? 'Drag to refine location' : 'Resolved Delivery Coordinate',
    }).addTo(map);

    marker.bindPopup(`
      <div style="font-family: sans-serif; padding: 4px;">
        <strong style="color: #38bdf8; font-size: 13px;">📍 Resolved Delivery Location</strong>
        <div style="font-size: 11px; margin-top: 4px; color: #cbd5e1;">
          Lat: ${currentLat.toFixed(5)}, Lng: ${currentLng.toFixed(5)}
        </div>
        ${isMedium ? '<div style="margin-top: 6px; font-size: 10px; color: #fbbf24; font-weight: bold;">⚠️ Draggable Pin: Move pin to adjust entrance</div>' : ''}
      </div>
    `);

    // Handle drag events for Medium tier
    if (isMedium) {
      marker.on('dragend', (event) => {
        const newPos = event.target.getLatLng();
        setDraggedCoords({ lat: newPos.lat, lng: newPos.lng });
        if (onLocationUpdated) {
          onLocationUpdated(newPos.lat, newPos.lng);
        }
      });
    }

    mainMarkerRef.current = marker;

    // POI Landmark Marker (if Agent 3 matched an OSM POI)
    if (poiMarkerRef.current) {
      poiMarkerRef.current.remove();
      poiMarkerRef.current = null;
    }
    if (polylineRef.current) {
      polylineRef.current.remove();
      polylineRef.current = null;
    }

    if (landmarkMatch && landmarkMatch.lat && landmarkMatch.lon) {
      const poiIcon = L.divIcon({
        className: 'custom-poi-marker',
        html: `
          <div style="
            background: linear-gradient(135deg, #06b6d4, #3b82f6);
            width: 22px; height: 22px; border-radius: 50%;
            border: 2px solid white;
            box-shadow: 0 4px 10px rgba(0,0,0,0.4);
            display: flex; align-items: center; justify-content: center;
          ">
            <span style="font-size: 10px; color: white;">🏛️</span>
          </div>
        `,
        iconSize: [24, 24],
        iconAnchor: [12, 12],
        popupAnchor: [0, -12],
      });

      const poiMarker = L.marker([landmarkMatch.lat, landmarkMatch.lon], {
        icon: poiIcon,
      }).addTo(map);

      poiMarker.bindPopup(`
        <div style="font-family: sans-serif; padding: 4px;">
          <strong style="color: #67e8f9; font-size: 12px;">🏛️ Matched OSM Landmark</strong>
          <div style="font-size: 11px; margin-top: 2px; color: #f8fafc; font-weight: 600;">
            ${landmarkMatch.name || 'OSM POI'}
          </div>
          ${landmarkMatch.distance_m ? `<div style="font-size: 10px; color: #94a3b8; margin-top: 2px;">Distance to centroid: ~${Math.round(landmarkMatch.distance_m)}m</div>` : ''}
        </div>
      `);

      poiMarkerRef.current = poiMarker;

      // Draw dashed connecting line
      const polyline = L.polyline(
        [
          [currentLat, currentLng],
          [landmarkMatch.lat, landmarkMatch.lon],
        ],
        {
          color: '#38bdf8',
          weight: 3,
          dashArray: '6, 8',
          opacity: 0.8,
        }
      ).addTo(map);

      polylineRef.current = polyline;

      // Fit bounds to show both points with padding
      const group = L.featureGroup([marker, poiMarker]);
      map.fitBounds(group.getBounds().pad(0.2));
    }

    // Clean-up on unmount
    return () => {
      // Keep map instance alive across rerenders unless coords become null
    };
  }, [latitude, longitude, confidence, isMedium, landmarkMatch]);

  // Reset map view to initial resolved coords
  const handleResetLocation = () => {
    if (latitude !== null && longitude !== null && mapInstanceRef.current) {
      setDraggedCoords(null);
      mapInstanceRef.current.setView([latitude, longitude], 15);
      if (mainMarkerRef.current) {
        mainMarkerRef.current.setLatLng([latitude, longitude]);
      }
    }
  };

  // Handle Confirm Location for MEDIUM tier (calls POST /v1/review/{id}/confirm)
  const handleConfirmLocation = async () => {
    if (!requestId) return;
    setIsConfirming(true);
    try {
      if (draggedCoords) {
        // If pin was moved, call resolve correction
        await resolveCorrection(requestId, {
          reviewerId: 'playground_user',
          correctedLat: draggedCoords.lat,
          correctedLng: draggedCoords.lng,
          notes: 'Customer confirmed adjusted pin in Playground',
        });
        setConfirmStatus('Pin location updated and confirmed in review log! ✓');
      } else {
        // If pin was unchanged, call confirm
        await confirmResolution(requestId, 'playground_user');
        setConfirmStatus('Location auto-confirmed in backend review queue! ✓');
      }
    } catch (err: any) {
      setConfirmStatus(`Failed: ${err.message}`);
    } finally {
      setIsConfirming(false);
    }
  };

  if (!hasValidCoords) {
    return (
      <div className="h-full min-h-[360px] w-full rounded-2xl bg-slate-900/60 border border-slate-800 flex flex-col items-center justify-center p-8 text-center text-slate-500">
        <Compass className="h-12 w-12 text-slate-600 mb-3 animate-pulse" />
        <h4 className="text-sm font-semibold text-slate-300 mb-1">No Coordinate Resolved</h4>
        <p className="text-xs max-w-xs text-slate-400">
          {needsHumanReview
            ? 'Address was flagged for human verification. Enter a valid address above to generate delivery coordinates.'
            : 'Enter an Indian address in the playground input to view the Leaflet map preview.'}
        </p>
      </div>
    );
  }

  const activeLat = draggedCoords?.lat ?? latitude!;
  const activeLng = draggedCoords?.lng ?? longitude!;

  return (
    <div className="flex flex-col h-full space-y-3">
      {/* Map Container */}
      <div className="relative h-[380px] sm:h-[420px] w-full rounded-2xl overflow-hidden border border-slate-800 shadow-2xl bg-slate-950">
        <div ref={mapContainerRef} className="h-full w-full" />

        {/* Map Header Overlay */}
        <div className="absolute top-3 left-3 z-[400] flex items-center gap-2 px-3 py-1.5 rounded-xl bg-slate-900/90 backdrop-blur-md border border-slate-800 text-xs font-mono text-slate-200 shadow-lg">
          <Navigation className="h-3.5 w-3.5 text-cyan-400" />
          <span>{activeLat.toFixed(5)}, {activeLng.toFixed(5)}</span>
          {draggedCoords && (
            <span className="text-[10px] bg-amber-500/20 text-amber-300 px-1.5 py-0.5 rounded font-sans font-bold">
              Adjusted
            </span>
          )}
        </div>

        {/* OSM Landmark Legend */}
        {landmarkMatch && (
          <div className="absolute bottom-3 left-3 z-[400] px-3 py-1.5 rounded-xl bg-slate-900/90 backdrop-blur-md border border-slate-800 text-[11px] text-slate-300 shadow-lg flex items-center gap-2">
            <span className="h-2.5 w-2.5 rounded-full bg-cyan-400" />
            <span>OSM Landmark: <strong>{landmarkMatch.name || 'POISpatialMatch'}</strong></span>
          </div>
        )}

        {/* Reset button if pin was moved */}
        {draggedCoords && (
          <button
            onClick={handleResetLocation}
            className="absolute top-3 right-3 z-[400] flex items-center gap-1.5 px-2.5 py-1.5 rounded-xl bg-slate-900/90 hover:bg-slate-800 border border-slate-700 text-xs font-medium text-slate-200 shadow-lg transition-colors"
          >
            <RotateCcw className="h-3 w-3 text-slate-400" />
            <span>Reset Pin</span>
          </button>
        )}
      </div>

      {/* Interactive MEDIUM-Tier Verification Panel */}
      {isMedium && requestId && (
        <div className="p-4 rounded-xl bg-gradient-to-r from-amber-950/40 via-slate-900 to-amber-950/40 border border-amber-500/30 space-y-2 animate-fade-in">
          <div className="flex items-start justify-between gap-3">
            <div className="flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-amber-400 shrink-0" />
              <div>
                <h5 className="text-xs font-bold text-amber-300">Customer Location Confirmation UX</h5>
                <p className="text-[11px] text-slate-400">
                  {draggedCoords
                    ? 'You adjusted the delivery pin location. Confirm to update the backend review record.'
                    : 'Drag the pin on the map to fine-tune building entrance, or confirm the resolved location.'}
                </p>
              </div>
            </div>

            <button
              onClick={handleConfirmLocation}
              disabled={isConfirming}
              className="px-3.5 py-2 rounded-lg bg-amber-500 hover:bg-amber-400 text-slate-950 font-bold text-xs flex items-center gap-1.5 transition-colors shadow-lg shadow-amber-500/20 shrink-0 disabled:opacity-50"
            >
              <Check className="h-3.5 w-3.5 stroke-[3]" />
              <span>{isConfirming ? 'Submitting...' : draggedCoords ? 'Save Adjusted Pin' : 'Confirm Location'}</span>
            </button>
          </div>

          {confirmStatus && (
            <p className="text-[11px] font-mono text-emerald-400 pt-1 border-t border-amber-500/20">
              {confirmStatus}
            </p>
          )}
        </div>
      )}
    </div>
  );
};
