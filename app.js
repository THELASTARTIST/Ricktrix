// Final Enhanced Main JavaScript for AutoRoute App with Multi-language and Dark Mode

// State management
let selectedRoute = null;
let currentLanguage = localStorage.getItem('autoroute-language') || 'en';
let darkMode = localStorage.getItem('autoroute-darkmode') === 'true';

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
const darkModeToggle = document.getElementById('darkModeToggle');

// Initialize dark mode
function initDarkMode() {
    if (darkMode) {
        document.documentElement.classList.add('dark');
        document.getElementById('sunIcon').classList.add('hidden');
        document.getElementById('moonIcon').classList.remove('hidden');
        document.getElementById('menu-theme').textContent = t('lightMode');
    } else {
        document.documentElement.classList.remove('dark');
        document.getElementById('sunIcon').classList.remove('hidden');
        document.getElementById('moonIcon').classList.add('hidden');
        document.getElementById('menu-theme').textContent = t('darkMode');
    }
}

// Toggle dark mode
darkModeToggle.addEventListener('click', () => {
    darkMode = !darkMode;
    localStorage.setItem('autoroute-darkmode', darkMode);
    initDarkMode();
});

// Change language function
function changeLanguage(lang) {
    currentLanguage = lang;
    localStorage.setItem('autoroute-language', lang);
    updatePageLanguage();
    renderRoutes();
    renderPopularStops();
    closeMenu();
}

// Close menu helper
function closeMenu() {
    mobileMenu.classList.add('hidden');
    menuIcon.classList.remove('hidden');
    closeIcon.classList.add('hidden');
}

// Update all text on page based on selected language
function updatePageLanguage() {
    // Hero section
    document.getElementById('heroTitle').textContent = t('heroTitle');
    document.getElementById('heroSubtitle').textContent = t('heroSubtitle');
    
    // Placeholders
    fromLocation.placeholder = t('fromPlaceholder');
    toLocation.placeholder = t('toPlaceholder');
    
    // Search button
    document.getElementById('searchBtnText').textContent = t('findRoutes');
    
    // Stats
    document.getElementById('stat1').textContent = t('routes');
    document.getElementById('stat2').textContent = t('users');
    document.getElementById('stat3').textContent = t('areas');
    
    // Headings
    document.getElementById('popularStopsTitle').textContent = t('popularStops');
    document.getElementById('availableRoutesTitle').textContent = t('availableRoutes');
    
    // CTA Section
    document.getElementById('ctaTitle').textContent = t('ctaTitle');
    document.getElementById('ctaSubtitle').textContent = t('ctaSubtitle');
    document.getElementById('ctaButton').textContent = t('submitRoute');
    
    // Footer
    document.getElementById('footerText').textContent = t('footerText');
    document.getElementById('copyright').textContent = t('copyright');
    
    // Menu items
    document.getElementById('menu-popular').textContent = t('popularRoutes');
    document.getElementById('menu-saved').textContent = t('savedRoutes');
    document.getElementById('menu-community').textContent = t('community');
    document.getElementById('menu-about').textContent = t('aboutUs');
    document.getElementById('menu-language').textContent = t('language');
    document.getElementById('menu-theme').textContent = darkMode ? t('lightMode') : t('darkMode');
}

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
    } else if (from || to) {
        // If only one field is filled, show all routes containing that location
        const searchTerm = from || to;
        const filtered = routes.filter(route => {
            const routeFrom = route.from.toLowerCase();
            const routeTo = route.to.toLowerCase();
            return routeFrom.includes(searchTerm) || routeTo.includes(searchTerm);
        });
        
        if (filtered.length > 0) {
            renderRoutes(filtered);
            document.getElementById('routesList').scrollIntoView({ behavior: 'smooth' });
        } else {
            alert(t('noRoutes') + '. ' + t('noRoutesDesc'));
        }
    } else {
        alert('Please enter at least one location');
    }
});

// Filter routes based on search
function filterRoutes(from, to) {
    const filtered = routes.filter(route => {
        const routeFrom = route.from.toLowerCase();
        const routeTo = route.to.toLowerCase();
        return (routeFrom.includes(from) && routeTo.includes(to)) ||
               (routeTo.includes(from) && routeFrom.includes(to));
    });
    
    if (filtered.length > 0) {
        renderRoutes(filtered);
        document.getElementById('routesList').scrollIntoView({ behavior: 'smooth' });
    } else {
        alert(t('noRoutes') + '. ' + t('noRoutesDesc'));
        renderRoutes(routes); // Show all routes
    }
}

// Render popular stops with translation support
function renderPopularStops() {
    popularStopsContainer.innerHTML = popularStops.map((stop, idx) => `
        <button onclick="quickSearch('${stop.name}')" class="bg-white dark:bg-gray-800 p-4 rounded-xl shadow-sm hover:shadow-md transition-shadow text-left">
            <div class="font-semibold text-gray-800 dark:text-gray-200 mb-1">${translateLocation(stop.name)}</div>
            <div class="text-sm text-gray-500 dark:text-gray-400">${stop.count}</div>
        </button>
    `).join('');
}

// Quick search from popular stops
function quickSearch(stopName) {
    fromLocation.value = translateLocation(stopName);
    fromLocation.focus();
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

// Render routes with full translation and dark mode support
function renderRoutes(routesToRender = routes) {
    routesList.innerHTML = routesToRender.map(route => `
        <div class="bg-white dark:bg-gray-800 rounded-xl shadow-sm hover:shadow-md transition-all cursor-pointer overflow-hidden route-card" 
             onclick="toggleRoute(${route.id})">
            <div class="p-5">
                <div class="flex items-start justify-between mb-3">
                    <div class="flex-1">
                        <h3 class="text-lg font-bold text-gray-800 dark:text-gray-200 mb-1">
                            ${translateLocation(route.from)} ↔ ${translateLocation(route.to)}
                        </h3>
                        <div class="text-sm text-gray-600 dark:text-gray-400">Shared auto</div>
                    </div>
                </div>

                <div class="py-3 border-t border-gray-100 dark:border-gray-700">
                    <div class="text-xs text-gray-500 dark:text-gray-400">${t('fare')}</div>
                    <div class="font-semibold text-gray-800 dark:text-gray-200">₹${route.fare}</div>
                </div>

                <div id="details-${route.id}" class="hidden mt-4 pt-4 border-t border-gray-100 dark:border-gray-700 space-y-3 route-details">
                    <div class="text-sm text-gray-600 dark:text-gray-400">
                        Via: <span class="font-semibold text-gray-800 dark:text-gray-200">${route.via.length ? route.via.join(' → ') : 'Direct'}</span>
                    </div>
                    <button class="w-full mt-3 bg-gradient-to-r from-amber-500 to-orange-600 text-white py-2.5 rounded-lg font-medium hover:shadow-lg transition-all">
                        ${t('viewOnMap')}
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

// Display routes
function displayRoutes() {
    const routesList = document.getElementById('routesList');
    if (!routesList) {
        console.log('routesList element not found');
        return;
    }
    
    if (sampleRoutes.length === 0) {
        routesList.innerHTML = '<div class="text-center text-gray-500">No routes found</div>';
        return;
    }
    
    routesList.innerHTML = sampleRoutes.map((route, index) => `
        <div class="bg-white dark:bg-gray-800 rounded-2xl shadow-lg p-6 hover:shadow-2xl transition-all hover:scale-[1.01] border border-gray-100 dark:border-gray-700">
            <div class="flex items-start justify-between mb-4">
                <div class="flex-1">
                    <h3 class="text-xl font-bold text-gray-800 dark:text-gray-200 mb-2 leading-tight">
                        ${route.from} <span class="text-orange-500">→</span> ${route.to}
                    </h3>
                    ${route.middleStops && route.middleStops.length > 0 ? `
                        <div class="flex flex-wrap gap-2 mt-3">
                            ${route.middleStops.map(stop => `
                                <span class="text-xs bg-orange-50 dark:bg-orange-900/30 text-orange-700 dark:text-orange-300 px-3 py-1 rounded-full font-medium border border-orange-200 dark:border-orange-700">
                                    ${stop}
                                </span>
                            `).join('')}
                        </div>
                    ` : ''}
                </div>
                <div class="ml-4">
                    <div class="bg-gradient-to-br from-orange-500 to-orange-600 text-white px-4 py-2 rounded-xl text-center shadow-lg">
                        <div class="text-xs font-semibold opacity-90">Fare</div>
                        <div class="text-lg font-black">${route.fare}</div>
                    </div>
                </div>
            </div>
            
            <div class="flex items-center justify-between pt-4 border-t border-gray-100 dark:border-gray-700">
                <div class="flex items-center gap-2 text-gray-600 dark:text-gray-400">
                    <svg class="w-5 h-5 text-orange-500" fill="currentColor" viewBox="0 0 24 24">
                        <path d="M18.92 6.01C18.72 5.42 18.16 5 17.5 5h-11c-.66 0-1.21.42-1.42 1.01L3 12v8c0 .55.45 1 1 1h1c.55 0 1-.45 1-1v-1h12v1c0 .55.45 1 1 1h1c.55 0 1-.45 1-1v-8l-2.08-5.99zM6.5 16c-.83 0-1.5-.67-1.5-1.5S5.67 13 6.5 13s1.5.67 1.5 1.5S7.33 16 6.5 16zm11 0c-.83 0-1.5-.67-1.5-1.5s.67-1.5 1.5-1.5 1.5.67 1.5 1.5-.67 1.5-1.5 1.5zM5 11l1.5-4.5h11L19 11H5z"/>
                    </svg>
                    <span class="font-semibold">${route.vehicles} RickTrix</span>
                </div>
                <button onclick="viewRouteDetails(${index})" class="bg-orange-50 dark:bg-orange-900/30 text-orange-600 dark:text-orange-400 px-5 py-2 rounded-xl font-bold text-sm hover:bg-orange-100 dark:hover:bg-orange-900/50 transition-all flex items-center gap-2 border border-orange-200 dark:border-orange-700">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7"></path>
                    </svg>
                    View Details
                </button>
            </div>
        </div>
    `).join('');
}

// Display popular stops
function displayPopularStops() {
    const popularStops = document.getElementById('popularStops');
    if (!popularStops) {
        console.log('popularStops element not found');
        return;
    }
    
    popularStops.innerHTML = popularStopsData.map(stop => `
        <button class="bg-orange-50 dark:bg-orange-900 hover:bg-orange-100 dark:hover:bg-orange-800 text-orange-700 dark:text-orange-200 px-4 py-3 rounded-xl font-semibold transition-colors flex items-center gap-2 border border-orange-200 dark:border-orange-700">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"></path>
            </svg>
            ${stop}
        </button>
    `).join('');
}

// View route details
function viewRouteDetails(index) {
    const route = sampleRoutes[index];
    alert(`Route Details:\n\nFrom: ${route.from}\nTo: ${route.to}\nFare: ${route.fare}\nAvailable RickTrix: ${route.vehicles}\n\nThis feature will show live tracking and detailed route information soon!`);
}

// Initialize on page load
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function() {
        displayRoutes();
        displayPopularStops();
    });
} else {
    // DOM is already loaded
    displayRoutes();
    displayPopularStops();
}