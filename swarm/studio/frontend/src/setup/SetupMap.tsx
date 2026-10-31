import React, { useEffect, useRef } from 'react';
import { useProjectStore } from '../store/useProjectStore';
import L from 'leaflet';

const DRONE_COLORS: Record<number, string> = {
  1: '#E69F00',
  2: '#56B4E9',
  3: '#009E73',
  4: '#CC79A7',
};

export const SetupMap: React.FC = () => {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<L.Map | null>(null);
  const layersRef = useRef<L.LayerGroup>(new L.LayerGroup());

  const { field, project, preview, cropRows, hotspots, wizardStep, updateFieldCoords } = useProjectStore();

  // Initialize Leaflet Map
  useEffect(() => {
    if (!mapContainerRef.current || mapInstanceRef.current) return;

    const map = L.map(mapContainerRef.current, {
      center: [18.52043, 73.85671],
      zoom: 18,
      zoomControl: true,
      attributionControl: true,
    });

    // Esri World Imagery Satellite Tiles
    L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
      maxZoom: 19,
      attribution: 'Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community',
    }).addTo(map);

    layersRef.current.addTo(map);
    mapInstanceRef.current = map;

    return () => {
      map.remove();
      mapInstanceRef.current = null;
    };
  }, []);

  // Center on project or field
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map || !field?.polygon_geojson?.geometry?.coordinates) return;

    const coords = field.polygon_geojson.geometry.coordinates[0];
    const latlngs: [number, number][] = coords.map((c: any) => [c[1], c[0]]);
    if (latlngs.length >= 3) {
      const bounds = L.latLngBounds(latlngs);
      map.fitBounds(bounds, { padding: [50, 50], maxZoom: 18 });
    }
  }, [field?.area_m2]);

  // Redraw layers when state changes
  useEffect(() => {
    const group = layersRef.current;
    group.clearLayers();

    // 1. Draw Field Boundary Polygon
    if (field?.polygon_geojson?.geometry?.coordinates) {
      const coords = field.polygon_geojson.geometry.coordinates[0];
      const latlngs: [number, number][] = coords.map((c: any) => [c[1], c[0]]);

      const poly = L.polygon(latlngs, {
        color: '#10b981',
        weight: 3,
        fillColor: '#10b981',
        fillOpacity: 0.12,
        dashArray: '4, 4',
      });
      group.addLayer(poly);

      // Vertex markers
      latlngs.forEach((pt, idx) => {
        const marker = L.circleMarker(pt, {
          radius: 5,
          color: '#ffffff',
          weight: 2,
          fillColor: '#0284c7',
          fillOpacity: 1,
        }).bindTooltip(`V${idx + 1}: ${pt[0].toFixed(5)}°N, ${pt[1].toFixed(5)}°E`, {
          permanent: false,
          direction: 'top',
        });
        group.addLayer(marker);
      });
    }

    // 2. Draw Illustrative Crop Rows
    if (cropRows && cropRows.length > 0 && wizardStep >= 3) {
      cropRows.forEach((row) => {
        const line = L.polyline(row, {
          color: '#84cc16',
          weight: 1.5,
          opacity: 0.65,
          dashArray: '2, 3',
        });
        group.addLayer(line);
      });
    }

    // 3. Draw Grid Cells & Cell IDs
    if (preview?.grid?.cells && wizardStep >= 4) {
      preview.grid.cells.forEach((cell) => {
        const cellPoly = L.polygon(cell.polygon_latlon, {
          color: '#64748b',
          weight: 1,
          fillColor: '#0284c7',
          fillOpacity: 0.08,
        }).bindTooltip(`${cell.cell_id}`, { permanent: false, direction: 'center' });
        group.addLayer(cellPoly);
      });
    }

    // 4. Draw Planned Paths per Drone
    if (preview?.drone_paths && wizardStep >= 7) {
      Object.entries(preview.drone_paths).forEach(([droneIdStr, wps]) => {
        const dId = parseInt(droneIdStr);
        const color = DRONE_COLORS[dId] || '#38bdf8';
        const pts: [number, number][] = wps.map((w) => [w.lat, w.lon]);

        const pathLine = L.polyline(pts, {
          color,
          weight: 2.5,
          opacity: 0.85,
          dashArray: '4, 4',
        });
        group.addLayer(pathLine);

        // Capture point pins
        wps.forEach((wp) => {
          if (wp.action === 'CAPTURE') {
            const pin = L.circleMarker([wp.lat, wp.lon], {
              radius: 3,
              color: '#ffffff',
              weight: 1,
              fillColor: color,
              fillOpacity: 0.9,
            });
            group.addLayer(pin);
          }
        });
      });
    }

    // 5. Draw Base Station
    if (project) {
      const baseMarker = L.circleMarker([project.base_lat, project.base_lon], {
        radius: 8,
        color: '#f59e0b',
        weight: 2.5,
        fillColor: '#0f172a',
        fillOpacity: 1,
      }).bindTooltip('🏠 Base Launchpad (GCS)', { permanent: false, direction: 'bottom' });
      group.addLayer(baseMarker);
    }

    // 6. Draw Hotspots
    if (hotspots && hotspots.length > 0) {
      hotspots.forEach((h) => {
        const color = h.type === 'late_blight' ? '#ef4444' : '#f59e0b';
        const hMarker = L.circleMarker([h.lat, h.lon], {
          radius: 7,
          color: '#ffffff',
          weight: 2,
          fillColor: color,
          fillOpacity: 1,
        }).bindTooltip(`🚨 ${h.node_id}: ${h.type.replace('_', ' ')} (${(h.severity * 100).toFixed(0)}%)`, {
          permanent: false,
          direction: 'top',
        });
        group.addLayer(hMarker);
      });
    }
  }, [field, preview, cropRows, hotspots, project, wizardStep]);

  return <div ref={mapContainerRef} className="w-full h-full relative" />;
};
