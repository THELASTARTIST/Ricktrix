// Function to get unique locations from the data
function getAllLocations() {
    const locations = new Set();
    autoFares.forEach(route => {
        locations.add(route.from);
        locations.add(route.to);
    });
    return Array.from(locations).filter(loc => loc !== "Not Specified");
}

// Function to get suggestions based on input
function getSuggestions(input) {
    if (!input) return [];
    input = input.toLowerCase();
    const locations = getAllLocations();
    return locations
        .filter(loc => loc.toLowerCase().startsWith(input))
        .slice(0, 8);
}

// Function to create and show suggestions
function showSuggestions(inputElement, suggestions) {
    // Remove existing suggestions
    const existingList = document.querySelector(`#${inputElement.id}-suggestions`);
    if (existingList) {
        existingList.remove();
    }

    if (!suggestions.length) return;

    // Create suggestions list
    const suggestionList = document.createElement('div');
    suggestionList.id = `${inputElement.id}-suggestions`;
    suggestionList.className = 'location-suggestions';

    suggestions.forEach(suggestion => {
        const item = document.createElement('div');
        item.className = 'location-suggestion';
        item.textContent = suggestion;
        item.onclick = () => {
            inputElement.value = suggestion;
            suggestionList.remove();
        };
        suggestionList.appendChild(item);
    });

    // Insert suggestions after input
    inputElement.parentNode.appendChild(suggestionList);
}

// Setup autocomplete for both input fields
document.addEventListener('DOMContentLoaded', () => {
    const fromInput = document.getElementById('fromLocation');
    const toInput = document.getElementById('toLocation');

    [fromInput, toInput].forEach(input => {
        input.addEventListener('input', (e) => {
            const suggestions = getSuggestions(e.target.value);
            showSuggestions(input, suggestions);
        });

        // Close suggestions when clicking outside
        document.addEventListener('click', (e) => {
            if (!input.contains(e.target)) {
                const suggestionList = document.querySelector(`#${input.id}-suggestions`);
                if (suggestionList) {
                    suggestionList.remove();
                }
            }
        });
    });
});