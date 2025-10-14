// Main JavaScript for AutoRoute App

// State management
let selectedRoute = null;

// DOM Elements
const menuBtn = document.getElementById('menuBtn');
const mobileMenu = document.getElementById('mobileMenu');
const menuIcon = document.getElementById('menuIcon');
const closeIcon = document.getElementById('closeIcon');
const searchBtn = document.getElementById('searchBtn');
const fromLocation = document.getElementById('fromLocation');
const toLocation = document.getElementById('toLocation');
const routesList = document.getElementById('routesList');
const popularStopsContainer = document.getElementById('popularStops');

// Toggle mobile menu
menuBtn.addEventListener('click', () => {
    mobileMenu.classList.toggle('hidden');
    menuIcon.classList.toggle('hidden');
    closeIcon.classList.toggle('hidden');
    if (!mobileMenu.classList.contains('hidden')) {
        mobileMenu.classList.add('menu-open');
    }
});

// Search functionality
searchBtn.addEventListener('click', () => {
    const from = fromLocation.value.trim().toLowerCase();
    const to = toLocation.value.trim().toLowerCase();
    
    if (from && to) {
        filterRoutes(from, to);
    } else {
        alert('Please enter both FROM and TO locations');
    }
});

// Filter routes based on search
function filterRoutes(from, to) {
    const filtered = routes.filter(route => 
        route.from.toLowerCase().includes(from) && route.to.toLowerCase().includes(to) ||
        route.to.toLowerCase().includes(from) && route.from.toLowerCase().includes(to)
    );
    
    if (filtered.length > 0) {
        renderRoutes(filtered);
        document.getElementById('routesList').scrollIntoView({ behavior: 'smooth' });
    } else {
        alert('No routes found between these locations. Try different stops!');
    }
}

// Render popular stops
function renderPopularStops() {
    popularStopsContainer.innerHTML = popularStops.map((stop, idx) => `
        <button onclick="quickSearch('${stop.name}')" class="bg-white p-4 rounded-xl shadow-sm hover:shadow-md transition-shadow text-left">
            <div class="font-semibold text-gray-800 mb-1">${stop.name}</div>
            <div class="text-sm text-gray-500">${stop.count}</div>
        </button>
    `).join('');
}

// Quick search from popular stops
function quickSearch(stopName) {
    fromLocation.value = stopName;
    fromLocation.focus();
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

// Render routes
function renderRoutes(routesToRender = routes) {
    routesList.innerHTML = routesToRender.map(route => `
        <div class="bg-white rounded-xl shadow-sm hover:shadow-md transition-all cursor-pointer overflow-hidden route-card" 
             onclick="toggleRoute(${route.id})">
            <div class="p-5">
                <div class="flex items-start justify-between mb-3">
                    <div class="flex-1">
                        <h3 class="text-lg font-bold text-gray-800 mb-1">${route.name}</h3>
                        <div class="flex items-center gap-2 text-sm text-gray-600 flex-wrap">
                            <span class="px-2 py-1 bg-amber-100 text-amber-700 rounded-md text-xs font-medium">
                                ${route.type}
                            </span>
                            <span class="flex items-center gap-1">
                                <svg class="w-4 h-4 text-yellow-500 fill-yellow-500" viewBox="0 0 20 20">
                                    <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z"/>
                                </svg>
                                ${route.rating}
                            </span>
                            <span class="text-gray-400">•</span>
                            <span>${route.users} users</span>
                        </div>
                    </div>
                </div>

                <div class="grid grid-cols-3 gap-4 py-3 border-t border-gray-100">
                    <div class="flex items-center gap-2">
                        <svg class="w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                        </svg>
                        <div>
                            <div class="text-xs text-gray-500">Fare</div>
                            <div class="font-semibold text-gray-800">₹${route.fare}</div>
                        </div>
                    </div>
                    <div class="flex items-center gap-2">
                        <svg class="w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                        </svg>
                        <div>
                            <div class="text-xs text-gray-500">Time</div>
                            <div class="font-semibold text-gray-800">${route.time} min</div>
                        </div>
                    </div>
                    <div class="flex items-center gap-2">
                        <svg class="w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"></path>
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"></path>
                        </svg>
                        <div>
                            <div class="text-xs text-gray-500">Distance</div>
                            <div class="font-semibold text-gray-800">${route.distance} km</div>
                        </div>
                    </div>
                </div>

                <div id="details-${route.id}" class="hidden mt-4 pt-4 border-t border-gray-100 space-y-3 route-details">
                    <div class="flex justify-between text-sm">
                        <span class="text-gray-600">Total Stops:</span>
                        <span class="font-semibold">${route.stops}</span>
                    </div>
                    <div class="flex justify-between text-sm">
                        <span class="text-gray-600">Frequency:</span>
                        <span class="font-semibold text-green-600">${route.frequency}</span>
                    </div>
                    <button class="w-full mt-3 bg-gradient-to-r from-amber-500 to-orange-600 text-white py-2.5 rounded-lg font-medium hover:shadow-lg transition-all">
                        View on Map
                    </button>
                </div>
            </div>
        </div>
    `).join('');
}

// Toggle route details
function toggleRoute(routeId) {
    const detailsElement = document.getElementById(`details-${routeId}`);
    
    // Close all other details
    document.querySelectorAll('[id^="details-"]').forEach(el => {
        if (el.id !== `details-${routeId}`) {
            el.classList.add('hidden');
        }
    });
    
    // Toggle current route
    if (selectedRoute === routeId) {
        detailsElement.classList.add('hidden');
        selectedRoute = null;
    } else {
        detailsElement.classList.remove('hidden');
        selectedRoute = routeId;
    }
}

// Initialize app on page load
document.addEventListener('DOMContentLoaded', () => {
    renderRoutes();
    renderPopularStops();
    
    // Add enter key support for search
    fromLocation.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            toLocation.focus();
        }
    });
    
    toLocation.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            searchBtn.click();
        }
    });
});

// Close mobile menu when clicking outside
document.addEventListener('click', (e) => {
    if (!mobileMenu.classList.contains('hidden') && 
        !mobileMenu.contains(e.target) && 
        !menuBtn.contains(e.target)) {
        mobileMenu.classList.add('hidden');
        menuIcon.classList.remove('hidden');
        closeIcon.classList.add('hidden');
    }
});