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
📱 **Mobile Optimized** - Seamless experience on all devices  
🚀 **Lightning Fast** - Under 50KB total size  
🔌 **Offline Ready** - Works without internet after first load  

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

---

## 📁 Project Structure

```
autoroute/
├── index.html          # 🏠 Main application UI
├── styles.css          # 🎨 Custom styling
├── data.js             # 📊 Route database
├── app.js              # ⚙️ Application logic
└── README.md           # 📖 Documentation
```

**File Overview:**

| File | Purpose | Size |
|------|---------|------|
| `index.html` | Application structure and layout | ~12KB |
| `styles.css` | Custom styles and animations | ~2KB |
| `data.js` | Route data and popular stops | ~4KB |
| `app.js` | Search logic and interactions | ~6KB |

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

Edit `data.js` and add new route objects to the `routes` array:

```javascript
{
    id: 10,
    name: 'Jadavpur ↔ Park Circus',
    from: 'Jadavpur',
    to: 'Park Circus',
    fare: '12-16',
    time: '25-30',
    distance: '9.2',
    type: 'Shared',
    stops: 7,
    frequency: 'Every 4 min',
    rating: 4.4,
    users: 312
}
```

**Route Properties:**

- `id` - Unique identifier
- `name` - Display name with arrow (↔)
- `from` / `to` - Start and end locations
- `fare` - Price range in rupees
- `time` - Duration in minutes
- `distance` - Distance in kilometers
- `type` - Route type (Shared/Direct)
- `stops` - Number of stops
- `frequency` - How often autos run
- `rating` - User rating (0-5)
- `users` - Number of users who rated

---

## 🛠️ Technology Stack

- **HTML5** - Semantic structure
- **CSS3** - Styling and animations
- **JavaScript (ES6+)** - Application logic
- **Tailwind CSS** - Utility-first styling (CDN)

**Why These Technologies?**

✅ No build process required  
✅ Works in any modern browser  
✅ Fast and lightweight  
✅ Easy to customize  
✅ Simple deployment  

---

## 🗺️ Roadmap

### ✅ Phase 1 - Current

- Basic route search functionality
- Route information display
- Mobile responsive design
- Popular stops feature

### 🔄 Phase 2 - In Progress

- [ ] Real-time GPS tracking
- [ ] User route submissions
- [ ] Favorite routes
- [ ] Social sharing
- [ ] Route notifications

### 📅 Phase 3 - Planned

- [ ] Backend API integration
- [ ] User authentication
- [ ] Interactive map view
- [ ] Multi-language support (Bengali/Hindi)
- [ ] Native mobile apps

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