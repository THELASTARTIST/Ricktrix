// Mobile Menu Toggle
const menuBtn = document.getElementById('menuBtn');
const mobileMenu = document.getElementById('mobileMenu');
const menuIcon = document.getElementById('menuIcon');
const closeIcon = document.getElementById('closeIcon');

function toggleMenu() {
    const isHidden = mobileMenu.classList.contains('hidden');
    if (isHidden) {
        mobileMenu.classList.remove('hidden');
        menuIcon.classList.add('hidden');
        closeIcon.classList.remove('hidden');
    } else {
        closeMenu();
    }
}

function closeMenu() {
    mobileMenu.classList.add('hidden');
    menuIcon.classList.remove('hidden');
    closeIcon.classList.add('hidden');
}

menuBtn.addEventListener('click', toggleMenu);

// Close menu when clicking on a link
document.querySelectorAll('#mobileMenu a').forEach(link => {
    link.addEventListener('click', closeMenu);
});

// Dark Mode Toggle for Desktop and Mobile
function toggleDarkMode() {
    const htmlElement = document.documentElement;
    
    if (htmlElement.classList.contains('dark')) {
        htmlElement.classList.remove('dark');
        localStorage.setItem('darkMode', 'false');
        updateDarkModeIcons('light');
    } else {
        htmlElement.classList.add('dark');
        localStorage.setItem('darkMode', 'true');
        updateDarkModeIcons('dark');
    }
}

function updateDarkModeIcons(mode) {
    // Desktop icons
    const sunIconDesktop = document.getElementById('sunIconDesktop');
    const moonIconDesktop = document.getElementById('moonIconDesktop');
    
    // Mobile icons
    const sunIconMobile = document.getElementById('sunIconMobile');
    const moonIconMobile = document.getElementById('moonIconMobile');
    
    // Mobile menu icons
    const sunIcon = document.getElementById('sunIcon');
    const moonIcon = document.getElementById('moonIcon');
    
    if (mode === 'dark') {
        sunIconDesktop?.classList.add('hidden');
        moonIconDesktop?.classList.remove('hidden');
        sunIconMobile?.classList.add('hidden');
        moonIconMobile?.classList.remove('hidden');
        sunIcon?.classList.add('hidden');
        moonIcon?.classList.remove('hidden');
    } else {
        sunIconDesktop?.classList.remove('hidden');
        moonIconDesktop?.classList.add('hidden');
        sunIconMobile?.classList.remove('hidden');
        moonIconMobile?.classList.add('hidden');
        sunIcon?.classList.remove('hidden');
        moonIcon?.classList.add('hidden');
    }
}

// Setup dark mode toggle buttons
document.getElementById('darkModeToggleDesktop')?.addEventListener('click', toggleDarkMode);
document.getElementById('darkModeToggleMobile')?.addEventListener('click', toggleDarkMode);
document.getElementById('darkModeToggle')?.addEventListener('click', toggleDarkMode);

// Initialize dark mode based on localStorage or system preference
function initializeDarkMode() {
    const savedDarkMode = localStorage.getItem('darkMode');
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    
    if (savedDarkMode === 'true' || (savedDarkMode === null && prefersDark)) {
        document.documentElement.classList.add('dark');
        updateDarkModeIcons('dark');
    } else {
        document.documentElement.classList.remove('dark');
        updateDarkModeIcons('light');
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', initializeDarkMode);