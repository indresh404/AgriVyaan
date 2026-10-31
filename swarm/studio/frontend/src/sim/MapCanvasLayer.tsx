import React, { useEffect, useRef } from 'react';
import { useSimStore } from '../store/useSimStore';
import { useProjectStore } from '../store/useProjectStore';
import { interpolateFrames } from '../lib/interpolate';
import L from 'leaflet';

const DRONE_COLORS: Record<number, string> = {
  1: '#E69F00',
  2: '#56B4E9',
  3: '#009E73',
  4: '#CC79A7',
};

export const MapCanvasLayer: React.FC = () => {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const animFrameRef = useRef<number | null>(null);

  const { recording, currentTime, isPlaying, playbackSpeed, layers, setCurrentTime, setSelectedCapture } = useSimStore();
  const { field } = useProjectStore();

  // Initialize Leaflet Map
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    const map = L.map(containerRef.current, {
      center: [18.52043, 73.85671],
      zoom: 18,
      zoomControl: false,
      attributionControl: true,
    });

    L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
      maxZoom: 19,
      attribution: 'Esri World Imagery &mdash; Simulation Prototype',
    }).addTo(map);

    // Create transparent overlay Canvas
    const canvas = document.createElement('canvas');
    canvas.style.position = 'absolute';
    canvas.style.top = '0';
    canvas.style.left = '0';
    canvas.style.pointerEvents = 'none';
    canvas.style.zIndex = '500';
    containerRef.current.appendChild(canvas);
    canvasRef.current = canvas;

    const resizeCanvas = () => {
      if (!canvas || !map) return;
      const size = map.getSize();
      canvas.width = size.x;
      canvas.height = size.y;
    };
    resizeCanvas();
    map.on('resize', resizeCanvas);
    map.on('move', () => {}); // Redraw on pan/zoom

    mapRef.current = map;

    return () => {
      map.remove();
      mapRef.current = null;
      if (canvas.parentNode) {
        canvas.parentNode.removeChild(canvas);
      }
    };
  }, []);

  // Fit bounds to field
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !field?.polygon_geojson?.geometry?.coordinates) return;
    const coords = field.polygon_geojson.geometry.coordinates[0];
    const latlngs: [number, number][] = coords.map((c: any) => [c[1], c[0]]);
    if (latlngs.length >= 3) {
      map.fitBounds(L.latLngBounds(latlngs), { padding: [60, 60] });
    }
  }, [field?.area_m2]);

  // Main 60 FPS RequestAnimationFrame Animation Loop
  useEffect(() => {
    let lastTimestamp = performance.now();

    const loop = (timestamp: number) => {
      const dt = (timestamp - lastTimestamp) / 1000.0;
      lastTimestamp = timestamp;

      if (isPlaying && recording) {
        const nextTime = currentTime + dt * playbackSpeed;
        if (nextTime >= recording.summary.total_time_s) {
          setCurrentTime(recording.summary.total_time_s);
          useSimStore.getState().setIsPlaying(false);
        } else {
          setCurrentTime(nextTime);
        }
      }

      drawCanvas(currentTime);
      animFrameRef.current = requestAnimationFrame(loop);
    };

    animFrameRef.current = requestAnimationFrame(loop);
    return () => {
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
    };
  }, [isPlaying, currentTime, playbackSpeed, recording, layers]);

  const drawCanvas = (time: number) => {
    const canvas = canvasRef.current;
    const map = mapRef.current;
    if (!canvas || !map || !recording) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // 1. Draw Field Boundary Polygon
    if (field?.polygon_geojson?.geometry?.coordinates) {
      const coords = field.polygon_geojson.geometry.coordinates[0];
      ctx.beginPath();
      coords.forEach((c: any, i: number) => {
        const pt = map.latLngToContainerPoint([c[1], c[0]]);
        if (i === 0) ctx.moveTo(pt.x, pt.y);
        else ctx.lineTo(pt.x, pt.y);
      });
      ctx.closePath();
      ctx.strokeStyle = '#10b981';
      ctx.lineWidth = 2.5;
      ctx.setLineDash([4, 4]);
      ctx.stroke();
      ctx.fillStyle = 'rgba(16, 185, 129, 0.08)';
      ctx.fill();
      ctx.setLineDash([]);
    }

    // 2. Draw Captured Cell Sweeps & Footprints up to current time
    if (layers.coverage) {
      recording.captures
        .filter((cap) => cap.t <= time)
        .forEach((cap) => {
          if (cap.footprint_polygon && cap.footprint_polygon.length >= 3) {
            ctx.beginPath();
            cap.footprint_polygon.forEach((pt, idx) => {
              const screenPt = map.latLngToContainerPoint([pt[0], pt[1]]);
              if (idx === 0) ctx.moveTo(screenPt.x, screenPt.y);
              else ctx.lineTo(screenPt.x, screenPt.y);
            });
            ctx.closePath();
            ctx.fillStyle = cap.stage === 1 ? 'rgba(56, 189, 248, 0.18)' : 'rgba(168, 85, 247, 0.25)';
            ctx.fill();
            ctx.strokeStyle = cap.stage === 1 ? '#38bdf8' : '#c084fc';
            ctx.lineWidth = 1;
            ctx.stroke();
          }
        });
    }

    // 3. Draw Hotspots with Pulsing Radar Rings
    if (layers.hotspots) {
      recording.events
        .filter((ev) => ev.type === 'HOTSPOT_REVEALED' && ev.t <= time)
        .forEach((ev) => {
          const cap = recording.captures.find((c) => c.hotspot_type && c.t <= time);
          if (cap) {
            const pt = map.latLngToContainerPoint([cap.lat, cap.lon]);
            const pulse = (time * 3) % 20;

            ctx.beginPath();
            ctx.arc(pt.x, pt.y, 8 + pulse, 0, Math.PI * 2);
            ctx.strokeStyle = 'rgba(239, 68, 68, 0.8)';
            ctx.lineWidth = 1.5;
            ctx.stroke();

            ctx.beginPath();
            ctx.arc(pt.x, pt.y, 6, 0, Math.PI * 2);
            ctx.fillStyle = '#ef4444';
            ctx.fill();
            ctx.strokeStyle = '#ffffff';
            ctx.lineWidth = 1.5;
            ctx.stroke();
          }
        });
    }

    // 4. Interpolate and Render Virtual Drones at current timestamp
    const activeDrones = interpolateFrames(recording.frames, time);

    activeDrones.forEach((d) => {
      const screenPt = map.latLngToContainerPoint([d.lat, d.lon]);
      const color = DRONE_COLORS[d.id] || '#38bdf8';

      // 3D Altitude Drop Shadow
      ctx.beginPath();
      ctx.ellipse(screenPt.x, screenPt.y + 12, 12, 6, 0, 0, Math.PI * 2);
      ctx.fillStyle = 'rgba(2, 6, 23, 0.7)';
      ctx.fill();

      // Heading indicator cone
      ctx.save();
      ctx.translate(screenPt.x, screenPt.y);
      ctx.rotate((d.heading * Math.PI) / 180);

      // Spinning Propellers (animated)
      const propAngle = (time * 40) % (Math.PI * 2);
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.4)';
      ctx.lineWidth = 1.5;
      [-10, 10].forEach((px) => {
        [-10, 10].forEach((py) => {
          ctx.beginPath();
          ctx.arc(px, py, 6, propAngle, propAngle + Math.PI);
          ctx.stroke();
        });
      });

      // Drone Body Quadrotor X-Frame
      ctx.beginPath();
      ctx.moveTo(-10, -10);
      ctx.lineTo(10, 10);
      ctx.moveTo(-10, 10);
      ctx.lineTo(10, -10);
      ctx.strokeStyle = '#475569';
      ctx.lineWidth = 3;
      ctx.stroke();

      // Central Aviation Beacon Ring
      ctx.beginPath();
      ctx.arc(0, 0, 7, 0, Math.PI * 2);
      ctx.fillStyle = color;
      ctx.fill();
      ctx.strokeStyle = '#ffffff';
      ctx.lineWidth = 2;
      ctx.stroke();

      // Forward Heading Arrow
      ctx.beginPath();
      ctx.moveTo(0, -7);
      ctx.lineTo(0, -16);
      ctx.strokeStyle = '#ffffff';
      ctx.lineWidth = 2;
      ctx.stroke();

      ctx.restore();

      // Badge Label & Battery
      ctx.fillStyle = 'rgba(15, 23, 42, 0.85)';
      ctx.strokeStyle = color;
      ctx.lineWidth = 1;
      ctx.fillRect(screenPt.x - 30, screenPt.y - 28, 60, 16);
      ctx.strokeRect(screenPt.x - 30, screenPt.y - 28, 60, 16);

      ctx.fillStyle = '#ffffff';
      ctx.font = 'bold 9px monospace';
      ctx.textAlign = 'center';
      ctx.fillText(`D${d.id} • ${d.battery_pct}%`, screenPt.x, screenPt.y - 17);
    });
  };

  return <div ref={containerRef} className="w-full h-full relative" />;
};
