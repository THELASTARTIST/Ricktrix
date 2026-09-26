// Adapt the fare dataset to the fields used by the route finder.
const autorouteRoutes = autoFares
    .filter(route => route.from !== 'Not Specified' && route.to !== 'Not Specified')
    .map(route => ({
        id: route.id,
        name: `${route.from} ↔ ${route.to}`,
        from: route.from,
        to: route.to,
        fare: route.fareINR,
        via: route.via
    }));

const stopRouteCounts = new Map();
autorouteRoutes.forEach(route => {
    [route.from, route.to].forEach(stop => {
        stopRouteCounts.set(stop, (stopRouteCounts.get(stop) || 0) + 1);
    });
});

const popularStops = Array.from(stopRouteCounts, ([name, count]) => ({ name, count }))
    .sort((first, second) => second.count - first.count)
    .slice(0, 8)
    .map(stop => ({ name: stop.name, count: `${stop.count} routes` }));