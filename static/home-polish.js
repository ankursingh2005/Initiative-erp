(() => {
  'use strict';
  const stage = document.querySelector('.infinity-stage');
  if (!stage) return;
  const descriptions = {
    'Attendance': 'Check in and keep track of your workdays',
    'Identity Card': 'View your employee identity card',
    'Schemes': 'Explore schemes and manage claims',
    'Purchase Orders': 'Manage orders and track receiving',
    'AI Analysis': 'Explore insights across your business',
    'Daily Profitability': 'Review sales, margins and performance',
    'Price System': 'Find the pricing information you need',
    'Ageing Stock': 'Review inventory and stock movement',
    'Scheme Calculator': 'Calculate offers and scheme benefits',
    'Incentive Report': 'Review incentives and sales rewards',
    'EMS': 'Manage employees, payroll and records'
  };
  const section = document.createElement('section');
  section.className = 'home-tools'; section.setAttribute('aria-labelledby', 'homeToolsTitle');
  section.innerHTML = '<div class="home-section-heading"><div><span class="home-section-kicker">GET TO WORK</span><h2 id="homeToolsTitle">Your everyday tools</h2></div><p>Choose a workspace to get started.</p></div><div class="home-tool-grid"></div>';
  const grid = section.querySelector('.home-tool-grid');
  document.querySelectorAll('.nav a.nav-item').forEach(link => {
    const label = link.textContent.trim();
    // Follow the existing role-based menu, including on phones where the menu is collapsed.
    if (!descriptions[label] || getComputedStyle(link).display === 'none') return;
    const card = document.createElement('a');
    card.className = 'home-tool-card'; card.href = link.href;
    const color = getComputedStyle(link).getPropertyValue('--nav-color').trim();
    if (color) card.style.setProperty('--tool-color', color);
    const icon = document.createElement('span'); icon.className = 'home-tool-icon'; icon.setAttribute('aria-hidden', 'true');
    const svg = link.querySelector('svg'); if (svg) icon.append(svg.cloneNode(true));
    const copy = document.createElement('span'); copy.className = 'home-tool-copy';
    const title = document.createElement('strong'); title.textContent = label;
    const detail = document.createElement('span'); detail.textContent = descriptions[label];
    copy.append(title, detail);
    const arrow = document.createElement('span'); arrow.className = 'home-tool-arrow'; arrow.textContent = '\u2197'; arrow.setAttribute('aria-hidden', 'true');
    card.append(icon, copy, arrow); grid.append(card);
  });
  if (grid.children.length) stage.after(section);
})();
