/** Sample data — preview what Atlas OS looks like at scale. */

function daysAgo(n) {
  const d = new Date();
  d.setDate(d.getDate() - n);
  return d.toISOString().slice(0, 10);
}

function isoDaysAgo(n) {
  const d = new Date();
  d.setDate(d.getDate() - n);
  return d.toISOString();
}

function assets(done = []) {
  const keys = ['logo', 'photos', 'phone', 'email', 'services', 'about'];
  const o = {};
  keys.forEach((k) => { o[k] = done.includes(k); });
  return o;
}

export function getDemoClients() {
  return [
    {
      id: 'demo-1',
      businessName: 'Gulf Coast Air & Heat',
      contactName: 'Mike Torres',
      email: 'mike@gulfcoastair.com',
      phone: '(727) 555-0142',
      website: 'https://gulfcoastair.com',
      status: 'live',
      dateSigned: daysAgo(94),
      monthlyCharge: 297,
      assets: assets(['logo', 'photos', 'phone', 'email', 'services', 'about']),
      requests: [
        { id: 'dr-1', title: 'Add financing page', description: 'Customer asked for financing options.', status: 'submitted', dateSubmitted: daysAgo(3) },
      ],
      notes: [{ id: 'dn-1', text: 'Very happy with launch. Referred a plumber.', createdAt: isoDaysAgo(12), updatedAt: isoDaysAgo(12) }],
    },
    {
      id: 'demo-2',
      businessName: 'Sunshine State Cooling',
      contactName: 'Jennifer Walsh',
      email: 'jen@sunshinecooling.com',
      phone: '(407) 555-0198',
      website: '',
      status: 'building',
      dateSigned: daysAgo(18),
      assets: assets(['logo', 'phone', 'email', 'services']),
      requests: [
        { id: 'dr-2', title: 'Homepage hero photos', description: 'Waiting on truck photos from client.', status: 'in_progress', dateSubmitted: daysAgo(10) },
        { id: 'dr-3', title: 'Service area map', description: 'Orlando + Kissimmee coverage.', status: 'submitted', dateSubmitted: daysAgo(5) },
      ],
      notes: [{ id: 'dn-2', text: 'Deadline: go live before summer rush.', createdAt: isoDaysAgo(8), updatedAt: isoDaysAgo(2) }],
    },
    {
      id: 'demo-3',
      businessName: 'Panhandle HVAC Pros',
      contactName: 'Derek Brooks',
      email: 'derek@panhandlehvac.com',
      phone: '(850) 555-0167',
      website: 'https://panhandlehvac.com',
      status: 'waiting_on_client',
      dateSigned: daysAgo(31),
      assets: assets(['logo', 'phone']),
      requests: [],
      notes: [{ id: 'dn-3', text: 'Chasing logo files — emailed twice.', createdAt: isoDaysAgo(4), updatedAt: isoDaysAgo(1) }],
    },
    {
      id: 'demo-4',
      businessName: 'Cool Breeze Mechanical',
      contactName: 'Carlos Mendez',
      email: 'carlos@coolbreezefl.com',
      phone: '(305) 555-0133',
      website: '',
      status: 'onboarding',
      dateSigned: daysAgo(6),
      assets: assets(['phone', 'email']),
      requests: [],
      notes: [],
    },
    {
      id: 'demo-5',
      businessName: 'First Coast Comfort',
      contactName: 'Sarah Nguyen',
      email: 'sarah@firstcoastcomfort.com',
      phone: '(904) 555-0181',
      website: 'https://firstcoastcomfort.com',
      status: 'live',
      dateSigned: daysAgo(120),
      monthlyCharge: 347,
      assets: assets(['logo', 'photos', 'phone', 'email', 'services', 'about']),
      requests: [
        { id: 'dr-4', title: 'Update summer promo banner', description: '$49 tune-up special.', status: 'complete', dateSubmitted: daysAgo(22) },
      ],
      notes: [],
    },
    {
      id: 'demo-6',
      businessName: 'Tampa Bay AC Repair',
      contactName: 'James Okafor',
      email: 'james@tampabayac.com',
      phone: '(813) 555-0155',
      website: '',
      status: 'building',
      dateSigned: daysAgo(25),
      assets: assets(['logo', 'photos', 'phone', 'email']),
      requests: [
        { id: 'dr-5', title: 'Add Google reviews widget', description: '', status: 'in_progress', dateSubmitted: daysAgo(7) },
      ],
      notes: [{ id: 'dn-4', text: 'Wants dark blue color scheme.', createdAt: isoDaysAgo(14), updatedAt: isoDaysAgo(14) }],
    },
    {
      id: 'demo-7',
      businessName: 'Emerald Coast Heating',
      contactName: 'Lisa Harmon',
      email: 'lisa@emeraldcoasthvac.com',
      phone: '(850) 555-0199',
      website: 'https://emeraldcoasthvac.com',
      status: 'live',
      dateSigned: daysAgo(67),
      monthlyCharge: 297,
      assets: assets(['logo', 'photos', 'phone', 'email', 'services', 'about']),
      requests: [],
      notes: [],
    },
    {
      id: 'demo-8',
      businessName: 'Space Coast Climate Control',
      contactName: 'Tom Bradley',
      email: 'tom@spacecoastcc.com',
      phone: '(321) 555-0174',
      website: '',
      status: 'waiting_on_client',
      dateSigned: daysAgo(14),
      assets: assets(['logo', 'phone', 'email']),
      requests: [
        { id: 'dr-6', title: 'About us copy', description: 'Client writing bio this week.', status: 'submitted', dateSubmitted: daysAgo(6) },
      ],
      notes: [],
    },
    {
      id: 'demo-9',
      businessName: 'Gainesville Air Solutions',
      contactName: 'Amy Chen',
      email: 'amy@gainesvilleair.com',
      phone: '(352) 555-0128',
      website: 'https://gainesvilleair.com',
      status: 'live',
      dateSigned: daysAgo(88),
      monthlyCharge: 397,
      assets: assets(['logo', 'photos', 'phone', 'email', 'services', 'about']),
      requests: [
        { id: 'dr-7', title: 'Add commercial services page', description: '', status: 'in_progress', dateSubmitted: daysAgo(9) },
      ],
      notes: [],
    },
    {
      id: 'demo-10',
      businessName: 'Sarasota Cool Tech',
      contactName: 'Rick Delaney',
      email: 'rick@sarasotacool.com',
      phone: '(941) 555-0163',
      website: '',
      status: 'building',
      dateSigned: daysAgo(21),
      assets: assets(['logo', 'phone', 'services']),
      requests: [],
      notes: [{ id: 'dn-5', text: 'Signed at in-home preview.', createdAt: isoDaysAgo(20), updatedAt: isoDaysAgo(20) }],
    },
    {
      id: 'demo-11',
      businessName: 'Fort Myers Comfort Co',
      contactName: 'Maria Santos',
      email: 'maria@fmcomfort.com',
      phone: '(239) 555-0147',
      website: 'https://fmcomfort.com',
      status: 'live',
      dateSigned: daysAgo(45),
      monthlyCharge: 297,
      assets: assets(['logo', 'photos', 'phone', 'email', 'services', 'about']),
      requests: [],
      notes: [],
    },
    {
      id: 'demo-12',
      businessName: 'Jacksonville HVAC Express',
      contactName: 'Kevin Price',
      email: 'kevin@jaxhvacexpress.com',
      phone: '(904) 555-0139',
      website: '',
      status: 'onboarding',
      dateSigned: daysAgo(4),
      assets: assets(['phone']),
      requests: [],
      notes: [],
    },
    {
      id: 'demo-13',
      businessName: 'Naples Arctic Air',
      contactName: 'Paul Fitzgerald',
      email: 'paul@naplesarctic.com',
      phone: '(239) 555-0188',
      website: 'https://naplesarctic.com',
      status: 'waiting_on_client',
      dateSigned: daysAgo(38),
      assets: assets(['logo', 'email', 'phone']),
      requests: [
        { id: 'dr-8', title: 'Photo shoot scheduling', description: 'Need client availability.', status: 'submitted', dateSubmitted: daysAgo(2) },
      ],
      notes: [],
    },
    {
      id: 'demo-14',
      businessName: 'Daytona Beach Air Masters',
      contactName: 'Nicole Rivers',
      email: 'nicole@daytonaairmasters.com',
      phone: '(386) 555-0151',
      website: 'https://daytonaairmasters.com',
      status: 'live',
      dateSigned: daysAgo(72),
      monthlyCharge: 347,
      assets: assets(['logo', 'photos', 'phone', 'email', 'services', 'about']),
      requests: [
        { id: 'dr-9', title: 'SSL certificate renewal', description: 'Annual check.', status: 'complete', dateSubmitted: daysAgo(30) },
      ],
      notes: [{ id: 'dn-6', text: 'Upsell opportunity: monthly maintenance plan page.', createdAt: isoDaysAgo(5), updatedAt: isoDaysAgo(5) }],
    },
  ];
}

export function getDemoDashboard() {
  const paying = getDemoClients().filter(
    (c) => c.status === 'live' && (c.monthlyCharge || 0) > 0,
  );
  const mrr = paying.reduce((sum, c) => sum + (c.monthlyCharge || 0), 0);

  return {
    clients: {
      total: 14,
      active: 11,
      open_requests: 7,
      mrr,
      paying_clients: paying.length,
    },
    leads: {
      total: 186,
      called: 186,
      previews: 24,
      clients: 14,
      conversion_rate: 7.5,
      callbacks: 31,
      interest_rate: 28.5,
    },
    recent_calls: [
      { business_name: 'Orlando Chill HVAC', outcome: 'preview', outcome_label: 'Preview', city: 'Orlando, FL', score: 82 },
      { business_name: 'Bay Area AC Services', outcome: 'callback', outcome_label: 'Call Back', city: 'Tampa, FL', score: 76 },
      { business_name: 'Keys Cooling & Heat', outcome: 'client', outcome_label: 'Client', city: 'Key West, FL', score: 91 },
      { business_name: 'Lakeland Air Pros', outcome: 'no_answer', outcome_label: 'No Answer', city: 'Lakeland, FL', score: 68 },
      { business_name: 'Palm Beach HVAC', outcome: 'preview', outcome_label: 'Preview', city: 'West Palm Beach, FL', score: 79 },
    ],
    charts: {
      outcomes: [
        { key: 'no_answer', label: 'No Answer', value: 62 },
        { key: 'not_interested', label: 'Not Interested', value: 48 },
        { key: 'callback', label: 'Call Back', value: 31 },
        { key: 'preview', label: 'Preview', value: 24 },
        { key: 'client', label: 'Client', value: 14 },
      ],
      calls_by_week: [
        { label: 'May 5', calls: 18, clients: 1 },
        { label: 'May 12', calls: 22, clients: 2 },
        { label: 'May 19', calls: 24, clients: 1 },
        { label: 'May 26', calls: 20, clients: 2 },
        { label: 'Jun 2', calls: 26, clients: 3 },
        { label: 'Jun 9', calls: 28, clients: 2 },
        { label: 'Jun 16', calls: 24, clients: 2 },
        { label: 'Jun 23', calls: 24, clients: 1 },
      ],
      client_pipeline: [
        { key: 'live', label: 'Live', value: 8 },
        { key: 'building', label: 'Building', value: 3 },
        { key: 'waiting_on_client', label: 'Waiting On Client', value: 2 },
        { key: 'onboarding', label: 'Onboarding', value: 1 },
      ],
    },
    learning: { active: true, total_calls: 186, openai_enabled: true, openai_min_calls: 25 },
    storage: { clients_in_db: 14, calls_in_db: 186, remote: 'github' },
  };
}

export function getDemoStats() {
  return {
    total_calls: 186,
    dead_interest: 32,
    no_interest: 26,
    top_cities_interest: [
      { city: 'Tampa, FL', calls: 28, rate: 39.3 },
      { city: 'Orlando, FL', calls: 34, rate: 35.3 },
      { city: 'Jacksonville, FL', calls: 22, rate: 31.8 },
      { city: 'Fort Myers, FL', calls: 15, rate: 33.3 },
      { city: 'Sarasota, FL', calls: 12, rate: 41.7 },
    ],
    top_cities_close: [
      { city: 'Tampa, FL', calls: 28, rate: 10.7 },
      { city: 'Orlando, FL', calls: 34, rate: 8.8 },
      { city: 'Naples, FL', calls: 11, rate: 9.1 },
      { city: 'Gainesville, FL', calls: 9, rate: 11.1 },
    ],
  };
}

export function getDemoLearning() {
  return {
    active: true,
    total_calls: 186,
    min_calls: 10,
    openai_enabled: true,
    openai_min_calls: 25,
    openai_cooldown_sec: 0,
  };
}

export function getDemoStorage() {
  return {
    clients_in_db: 14,
    calls_in_db: 186,
    local_snapshot: true,
    remote: 'github',
    data_dir: '/data (preview)',
  };
}

/** Sample call list — matches dashboard “recent calls” vibe. */
export function getDemoLeads() {
  return [
    {
      name: 'Orlando Chill HVAC',
      phone: '(407) 555-0144',
      city: 'Orlando, FL',
      website: 'http://orlandochillhvac.oldsite.com',
      site_status: 'dead',
      score: 82,
      reason: 'Outdated site, no mobile layout, strong reviews',
      opener: 'Hi, I noticed your website might be costing you calls on mobile — we help HVAC companies fix that.',
      address: '1420 Colonial Dr, Orlando, FL',
    },
    {
      name: 'Bay Area AC Services',
      phone: '(813) 555-0177',
      city: 'Tampa, FL',
      website: '',
      site_status: 'none',
      score: 76,
      reason: 'No website, 4.6★ on Google, 89 reviews',
      opener: 'I saw you have great reviews but no website — homeowners often skip businesses they can’t find online.',
      address: '5802 W Hillsborough Ave, Tampa, FL',
    },
    {
      name: 'Keys Cooling & Heat',
      phone: '(305) 555-0191',
      city: 'Key West, FL',
      website: 'https://keyscooling.com',
      site_status: 'working',
      score: 91,
      reason: 'High score — already a client in pipeline',
      opener: 'Following up on the site preview we sent over last week.',
      address: '1210 Duval St, Key West, FL',
    },
    {
      name: 'Lakeland Air Pros',
      phone: '(863) 555-0122',
      city: 'Lakeland, FL',
      website: 'http://lakelandairpros.net',
      site_status: 'dead',
      score: 68,
      reason: 'Broken contact form, SSL expired',
      opener: 'Your contact form looks broken — we help HVAC shops capture more leads from their site.',
      address: '220 N Kentucky Ave, Lakeland, FL',
    },
    {
      name: 'Palm Beach HVAC',
      phone: '(561) 555-0166',
      city: 'West Palm Beach, FL',
      website: '',
      site_status: 'none',
      score: 79,
      reason: 'No website, busy season approaching',
      opener: 'Summer’s coming — a lot of HVAC companies in Palm Beach are getting sites live before the rush.',
      address: '400 Clematis St, West Palm Beach, FL',
    },
    {
      name: 'Brevard Climate Control',
      phone: '(321) 555-0183',
      city: 'Melbourne, FL',
      website: 'http://brevardclimate.net',
      site_status: 'dead',
      score: 74,
      reason: 'Template site, no local SEO',
      opener: 'I took a quick look at your site — it doesn’t mention Melbourne or your service area.',
      address: '1800 W New Haven Ave, Melbourne, FL',
    },
    {
      name: 'Capital City Comfort',
      phone: '(850) 555-0159',
      city: 'Tallahassee, FL',
      website: '',
      site_status: 'none',
      score: 71,
      reason: 'No web presence, owner-operated',
      opener: 'Most homeowners in Tallahassee search online first — wanted to see if that’s on your radar.',
      address: '600 W Tennessee St, Tallahassee, FL',
    },
    {
      name: 'Venice Beach Air',
      phone: '(941) 555-0137',
      city: 'Venice, FL',
      website: 'http://venicebeachair.com',
      site_status: 'dead',
      score: 85,
      reason: 'Copyright 2019, slow load time',
      opener: 'Your site still shows 2019 in the footer — we refresh HVAC sites in about two weeks.',
      address: '200 Tampa Ave W, Venice, FL',
    },
    {
      name: 'Ocala Heating & Air',
      phone: '(352) 555-0148',
      city: 'Ocala, FL',
      website: '',
      site_status: 'none',
      score: 73,
      reason: 'Strong local presence, no digital storefront',
      opener: 'You’ve got a solid reputation in Ocala — a simple site could bring in more after-hours calls.',
      address: '310 SE 3rd St, Ocala, FL',
    },
    {
      name: 'Port St Lucie AC Co',
      phone: '(772) 555-0171',
      city: 'Port St. Lucie, FL',
      website: 'http://pslac.com',
      site_status: 'dead',
      score: 77,
      reason: 'Not mobile-friendly, missing service pages',
      opener: 'I tried your site on my phone — the menu was hard to use. We fix that for HVAC companies.',
      address: '1050 SE Port St Lucie Blvd, Port St. Lucie, FL',
    },
    {
      name: 'St Augustine Cool Air',
      phone: '(904) 555-0125',
      city: 'St. Augustine, FL',
      website: '',
      site_status: 'none',
      score: 69,
      reason: 'Historic area, tourist + residential mix',
      opener: 'St. Augustine homeowners search “AC repair near me” — without a site you’re invisible there.',
      address: '50 San Marco Ave, St. Augustine, FL',
    },
    {
      name: 'Pensacola Breeze HVAC',
      phone: '(850) 555-0194',
      city: 'Pensacola, FL',
      website: 'http://pensacolabreezehvac.org',
      site_status: 'dead',
      score: 80,
      reason: 'Generic template, no trust signals',
      opener: 'Your site doesn’t show licenses or reviews — we build that in for HVAC shops.',
      address: '220 W Garden St, Pensacola, FL',
    },
  ];
}

/** Pre-filled outcomes for a few demo leads (phone keys = last 10 digits). */
export function getDemoLeadOutcomes() {
  return {
    by_phone: {
      4075550144: { outcome: 'preview', business_name: 'Orlando Chill HVAC' },
      8135550177: { outcome: 'callback', business_name: 'Bay Area AC Services' },
      3055550191: { outcome: 'client', business_name: 'Keys Cooling & Heat' },
      8635550122: { outcome: 'no_answer', business_name: 'Lakeland Air Pros' },
      5615550166: { outcome: 'preview', business_name: 'Palm Beach HVAC' },
      3215550183: { outcome: 'not_interested', business_name: 'Brevard Climate Control' },
    },
  };
}
