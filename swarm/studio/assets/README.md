# AgriVyaan Mission Studio — Assets & Imagery

## 1. Imagery Licensing & Terms

### Public Satellite Tiles (Esri World Imagery)
- AgriVyaan Mission Studio uses Esri World Imagery slippy tiles (`https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}`) for background farm visualization.
- **Attribution Required:** "Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community".
- Public satellite tiles are cached locally in `studio/data/cache/tiles/` using proper HTTP User-Agents to prevent unnecessary network requests and respect server rate limits.
- **Licensing Notice:** Do not bundle or commit proprietary or unfree satellite or aerial imagery to version control without explicit written licenses.

### Custom Orthophoto Uploads
- Users may upload their own high-resolution orthophoto GeoTIFF/PNG files via Step 2 of the Mission Setup Wizard.
- Uploaded orthophotos are stored in `studio/data/uploads/` and paired with WGS84 bounding coordinates `[min_lon, min_lat, max_lon, max_lat]`.

---

## 2. Known Imagery Resolution Limitations

> **Honesty Notice:** Satellite imagery provided via public tile servers has a native ground resolution of roughly **0.3 to 0.6 metres per pixel**.
>
> In this simulator, when a virtual drone conducts a Stage 2 targeted micro-inspection at 8 metres altitude (which optically computes to ~1.5 mm/pixel GSD), the displayed crop image is cropped from available orthomosaic tiles or user-uploaded samples. Public satellite zoom levels **cannot** depict real microscopic leaf-level disease symptoms. The interface explicitly badges all crops as synthetic simulation approximations.
