# PixelBin analytics dashboard

Static GA4 dashboard for PixelBin properties. Pages fetch `data/dashboard.json` and render with `assets/dashboard.js`; `scripts/refresh_dashboard.py` regenerates the export from the GA4 Data API.

**The committed `data/dashboard.json` is synthetic.** It keeps the real export's structure (properties, daily series, AI-tool rankings, funnels) but every number is generated. Run the refresh script with your own GA4 credentials to see real data.
