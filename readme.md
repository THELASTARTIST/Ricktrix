# 🚗 AutoRoute - Smart Auto-Rickshaw Route Finder

> A modern web application for discovering shared auto-rickshaw routes in Kolkata. Built with vanilla JavaScript - zero dependencies, zero build process.

---

## 📋 Table of Contents

- [About](#-about)
- [Features](#-features)
- [Quick Start](#-quick-start)
- [Project Structure](#-project-structure)
- [Usage](#-usage)
- [Adding Routes](#-adding-routes)
- [Technology Stack](#-technology-stack)
- [Roadmap](#-roadmap)
- [Contributing](#-contributing)
- [License](#-license)

---

## 🎯 About

AutoRoute solves a common problem for Kolkata commuters: finding reliable information about shared auto-rickshaw routes. The app provides detailed route information including fares, travel times, stops, and frequencies in a clean, mobile-first interface.

**Why AutoRoute?**

- No centralized platform exists for auto-rickshaw route information
- Commuters struggle to estimate fares and travel times
- Newcomers find it difficult to navigate the city's auto network
- Real-time route frequency information is unavailable

---

## ✨ Features

🔍 **Smart Search** - Find routes between any two locations instantly  
💰 **Fare Information** - Transparent pricing for every route  
⏱️ **Travel Time** - Accurate time estimates for journey planning  
📍 **Popular Stops** - Quick access to major transit hubs  
⭐ **User Ratings** - Community-verified route reliability  
📱 **Installable** - Add to the home screen and launch full-screen  
🚀 **Lightning Fast** - No build step, no bundler, no framework  
🔌 **Genuinely Offline** - Route search works in aeroplane mode  

---

## 🚀 Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/autoroute.git
cd autoroute
```

### Run Locally

**Option 1: Direct Open**
```bash
# Just double-click index.html
open index.html
```

**Option 2: Local Server**
```bash
# Using Python
python -m http.server 8000

# Using Node.js
npx http-server

# Using PHP
php -S localhost:8000
```

Then open `http://localhost:8000` in your browser.

**Option 3: With the backend (recommended)**

```bash
cd backend
run.bat
```

This serves the API and the site from one process on one port, so the same
`http://localhost:8000` works, and a phone on the same Wi-Fi can reach it. See
[backend/README.md](backend/README.md).

### Install it on your phone

RICKTRIX is a Progressive Web App — it installs to the home screen, launches
full-screen, and keeps working with no network.

1. Start the server (`backend\run.bat`).
2. Open the printed `http://<LAN-IP>:8000` address on the phone.
3. **Android:** tap the download icon in the header.
   **iPhone:** Share → **Add to Home Screen**.

To install from outside your Wi-Fi you need an HTTPS address, because browsers
only allow installation and geolocation on secure origins. Deploy it (see
[backend/README.md](backend/README.md#deploying-it)) or use a tunnel.

---

## 📁 Project Structure

```
AUTO ROUTE/
├── index.html       # Main route finder and entry page
├── all_routes.html  # Searchable/filterable route directory
├── saved_routes.html # Routes bookmarked on this device
├── tracking.html    # Live tracking demo
├── community.html   # Community demo
├── about.html       # About page and charts
├── offline.html     # Shown when a page opens with no connection
├── autofare.js      # Fare records, bus stops and the official tariff
├── data.js          # Maps fare records to route finder data
├── autocomplete.js  # Location suggestions from fare records
├── api.js           # Optional backend client; falls back to the local arrays
├── pwa.js           # Service worker registration and the install button
├── sw.js            # Precaches the app so it works with no network
├── manifest.webmanifest # Name, icons, colours, home-screen shortcuts
├── assets/          # App icons, generated from the SVGs
├── style.css        # Shared styles and responsive page navigation
├── backend/         # FastAPI service - see backend/README.md
├── app.js           # Legacy controller; not loaded by the current pages
├── navigation.js    # Legacy navigation/theme controller
├── translations.js  # Legacy translation module
├── setup.txt        # Setup notes
└── readme.md        # Project documentation
```

`index.html`, `all_routes.html`, and `saved_routes.html` load `autofare.js` followed by `data.js`, so route cards, directory filters, autocomplete, and saved-route fare details use the same records. Home and the route directory share bookmarks through the `ricktrix-saved` local-storage key. All six HTML pages link across the site, load `style.css`, and load `pwa.js`. The three legacy JavaScript files are retained but not loaded because their expected page IDs and data model do not match the current pages.

`autofare.js` is the single source of truth. The backend parses it directly rather than keeping a second copy, so the API and the site cannot drift apart.

---

## 💻 Usage

### Search for Routes

1. **Enter Start Location** - Type your starting point (e.g., "Howrah Station")
2. **Enter Destination** - Type where you want to go (e.g., "Garia")
3. **Click Search** - Or press Enter to find routes
4. **View Results** - See all matching routes with details

### Browse Routes

- Scroll down to see all available routes
- Click any route card to expand full details
- View stops, frequency, ratings, and more

### Quick Search

- Click on popular stops to auto-fill the search
- Use keyboard navigation (Tab/Enter) for faster access

---

## 📝 Adding Routes

Routes live in the `autoFares` array in **`autofare.js`** — that file is the
single source of truth, and `data.js`, the backend, and the ML training set all
read from it. Add your record there:

```javascript
{
    id: 138,
    from: 'Jadavpur',
    to: 'Park Circus',
    via: ['Rashbehari', 'Panjab'],
    fareINR: 20,
    fareSource: 'user-reported',
    fromMatchedBusStop: 'Jadavpur',
    toMatchedBusStop: 'Park Circus',
    flag: ''
}
```

**Route properties:**

- `id` - Unique identifier
- `from` / `to` - Start and end stops
- `via` - Intermediate stops, as an array
- `fareINR` - Fare in rupees (a number, not a range)
- `fareSource` - Where the number came from, e.g. `user-reported`
- `fromMatchedBusStop` / `toMatchedBusStop` - Cross-reference into `busRouteStops`
- `flag` - Optional marker, e.g. for a fare you could not verify

Two things to know. Records with `from` or `to` set to `"Not Specified"` are
hidden by `data.js`, so an incomplete route is stored but not shown. And these
fares are user-provided and unverified — the honesty note at the top of
`autofare.js` says so, and the app does not claim otherwise.

---

## 🛠️ Technology Stack

**Frontend**

- **HTML5** - Semantic structure
- **CSS3** - Styling and animations
- **JavaScript (ES6+)** - Application logic
- **Service Worker + Web App Manifest** - Offline support and installation

**Backend** (optional, in `backend/`)

- **Python / FastAPI** - Route, stop and fare endpoints
- **TensorFlow + Keras** - Trains a fare estimator (used with a ridge baseline)
- **Supabase** - Optional Postgres for submissions and cross-device bookmarks

**Why These Technologies?**

✅ No build process or bundler on the frontend  
✅ Works in any modern browser  
✅ Frontend is fully functional with no backend at all  
✅ Easy to customize  
✅ Deploys as a single container  

---

## 🗺️ Roadmap

### ✅ Phase 1 - Current

- Basic route search functionality
- Route information display
- Mobile responsive design
- Popular stops feature
- Installable PWA with offline support
- FastAPI backend: routes, stops, fares, submissions, bookmarks
- Fare estimator trained and cross-validated against a linear baseline

### 🔄 Phase 2 - In Progress

- [ ] Public HTTPS deployment
- [ ] Real-time GPS tracking
- [ ] User route submissions reaching the moderation queue
- [ ] Social sharing
- [ ] Route notifications

### 📅 Phase 3 - Planned

- [ ] User authentication
- [ ] Interactive map view
- [ ] Multi-language support (Bengali/Hindi)
- [ ] Store listings (Play Store / App Store)

---

## 🤝 Contributing

Contributions make the open-source community amazing! Any contributions are **greatly appreciated**.

### How to Contribute

1. **Fork the Project**
2. **Create Feature Branch**
   ```bash
   git checkout -b feature/AmazingFeature
   ```
3. **Commit Changes**
   ```bash
   git commit -m 'Add some AmazingFeature'
   ```
4. **Push to Branch**
   ```bash
   git push origin feature/AmazingFeature
   ```
5. **Open Pull Request**

### Ideas for Contribution

💡 Add more Kolkata routes  
🎨 Improve UI/UX design  
🌐 Add Bengali language support  
🗺️ Integrate map visualization  
🐛 Fix bugs and issues  
📚 Improve documentation  

---

## 📄 License

Distributed under the MIT License. See `LICENSE` for more information.

```
MIT License - Copyright (c) 2025 AutoRoute
```


## 🙏 Acknowledgments

- Kolkata auto-rickshaw drivers for their essential service
- Local commuters for route information and feedback
- Open-source community for inspiration
- Tailwind CSS team for the excellent framework

⭐ Star this repo if you find it helpful!

</div>