// Route Data for AutoRoute App

const routes = [
    {
        id: 1,
        name: 'Ramlal Bazar (Haltu) ↔ B.B.D. Bag',
        from: 'Ramlal Bazar (Haltu)',
        to: 'B.B.D. Bag',
        fare: '18-25',
        time: '40-50',
        distance: '14.2',
        type: 'Shared',
        stops: 10,
        frequency: 'Every 7 min',
        rating: 4.4,
        users: 312
    },
    {
        id: 2,
        name: 'Ballygunge Station ↔ Esplanade',
        from: 'Ballygunge Station',
        to: 'Esplanade',
        fare: '12-18',
        time: '25-35',
        distance: '8.5',
        type: 'Shared',
        stops: 7,
        frequency: 'Every 4 min',
        rating: 4.6,
        users: 428
    },
    {
        id: 3,
        name: 'Bagbazar ↔ Kidderpore',
        from: 'Bagbazar',
        to: 'Kidderpore',
        fare: '15-20',
        time: '35-45',
        distance: '11.8',
        type: 'Shared',
        stops: 9,
        frequency: 'Every 6 min',
        rating: 4.3,
        users: 267
    },
    {
        id: 4,
        name: 'Sealdah ↔ Thakurpukur',
        from: 'Sealdah',
        to: 'Thakurpukur',
        fare: '20-28',
        time: '50-60',
        distance: '16.5',
        type: 'Shared',
        stops: 12,
        frequency: 'Every 8 min',
        rating: 4.2,
        users: 298
    },
    {
        id: 5,
        name: 'Kankurgachi (C.I.T. Scheme) ↔ Behala',
        from: 'Kankurgachi (C.I.T. Scheme)',
        to: 'Behala',
        fare: '18-24',
        time: '45-55',
        distance: '15.3',
        type: 'Shared',
        stops: 11,
        frequency: 'Every 10 min',
        rating: 4.1,
        users: 189
    },
    {
        id: 6,
        name: 'Esplanade ↔ Amtala',
        from: 'Esplanade',
        to: 'Amtala',
        fare: '22-30',
        time: '55-65',
        distance: '18.2',
        type: 'Shared',
        stops: 13,
        frequency: 'Every 12 min',
        rating: 4.0,
        users: 234
    },
    {
        id: 7,
        name: 'Tollygunge (Kundghat) ↔ Esplanade',
        from: 'Tollygunge (Kundghat)',
        to: 'Esplanade',
        fare: '15-22',
        time: '40-50',
        distance: '13.5',
        type: 'Shared',
        stops: 10,
        frequency: 'Every 5 min',
        rating: 4.5,
        users: 456
    },
    {
        id: 8,
        name: 'Garia ↔ Howrah Station',
        from: 'Garia',
        to: 'Howrah Station',
        fare: '15-20',
        time: '35-45',
        distance: '12.5',
        type: 'Shared',
        stops: 8,
        frequency: 'Every 5 min',
        rating: 4.7,
        users: 523
    },
    {
        id: 9,
        name: 'Garia ↔ Rashbehari',
        from: 'Garia',
        to: 'Rashbehari',
        fare: '10-15',
        time: '20-30',
        distance: '7.8',
        type: 'Shared',
        stops: 6,
        frequency: 'Every 4 min',
        rating: 4.6,
        users: 389
    }
];

const popularStops = [
    { name: 'Howrah Station', count: '142 routes' },
    { name: 'Sealdah', count: '98 routes' },
    { name: 'Esplanade', count: '87 routes' },
    { name: 'Park Street', count: '76 routes' }
];