// =========================================================================
// Fantasy War Room - Yahoo Draft Room Auto-Sync Content Script (Manifest V3)
// =========================================================================

(function() {
  console.log('%c🏈 Fantasy War Room Extension Active!', 'background: #6b21a8; color: #fff; font-size: 14px; padding: 4px 8px; border-radius: 4px;');

  const channel = new BroadcastChannel('yahoo_draft_sync');
  const seenPicks = new Set();
  let syncCount = 0;

  // Create subtle floating HUD indicator in Yahoo Draft room
  const hud = document.createElement('div');
  hud.id = 'war-room-sync-hud';
  hud.style.position = 'fixed';
  hud.style.bottom = '16px';
  hud.style.right = '16px';
  hud.style.zIndex = '999999';
  hud.style.backgroundColor = 'rgba(15, 23, 42, 0.95)';
  hud.style.border = '1px solid rgba(147, 51, 234, 0.8)';
  hud.style.color = '#ffffff';
  hud.style.padding = '8px 14px';
  hud.style.borderRadius = '12px';
  hud.style.fontFamily = '-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif';
  hud.style.fontSize = '12px';
  hud.style.fontWeight = 'bold';
  hud.style.boxShadow = '0 10px 25px rgba(0,0,0,0.5)';
  hud.style.display = 'flex';
  hud.style.alignItems = 'center';
  hud.style.gap = '8px';
  hud.style.cursor = 'pointer';
  hud.title = 'Click to open your Fantasy War Room Dashboard';
  hud.innerHTML = '<span style="color:#10b981; animation: pulse 2s infinite;">●</span> <span>War Room Auto-Syncing:</span> <span id="war-room-pick-count" style="color:#c084fc; font-weight:800;">0 picks</span>';

  hud.addEventListener('click', () => {
    window.open('https://gtlucian.github.io/FantasyDashboard/', '_blank');
  });

  if (document.body) {
    document.body.appendChild(hud);
  } else {
    document.addEventListener('DOMContentLoaded', () => document.body.appendChild(hud));
  }

  function updateHud(count) {
    const el = document.getElementById('war-room-pick-count');
    if (el) el.textContent = count + ' pick' + (count === 1 ? '' : 's');
  }

  function cleanPlayerName(str) {
    if (!str) return '';
    // Remove position notes, team notes, and extraneous stats
    let clean = str.replace(/(QB|RB|WR|TE|K|DEF|DST|IR|PUP|O|Q|D|SSPD|FA|W)/g, '')
                   .replace(/\s+/g, ' ')
                   .replace(/[()#-]/g, '')
                   .trim();
    return clean;
  }

  const ignoreWords = new Set([
    'player', 'team', 'pos', 'rank', 'bye', 'adp', 'status', 'round', 'pick',
    'action', 'queue', 'draft', 'roster', 'projections', 'stats', 'time', 'search',
    'all', 'filter', 'edit', 'cancel', 'done', 'view', 'hide', 'my team'
  ]);

  function scanDraftRoom() {
    // Select all potential pick elements in Yahoo draft room DOM
    const selectors = [
      '.grid-pick-player',
      '.yui-dt-liner',
      '.ys-player',
      '[data-player-name]',
      'tr.pick',
      'div.pick-history-item',
      '.player-name',
      '.ys-stat',
      '.draft-pick-name',
      'td.player',
      '.pick-item',
      '.ys-name',
      '.player-info-name'
    ];

    const elements = document.querySelectorAll(selectors.join(', '));
    elements.forEach(el => {
      let rawName = el.getAttribute('data-player-name') || el.innerText || el.textContent || '';
      let clean = cleanPlayerName(rawName);

      if (clean && clean.length >= 4 && !seenPicks.has(clean.toLowerCase()) && !ignoreWords.has(clean.toLowerCase())) {
        // Exclude purely numeric or single-word headers
        if (clean.includes(' ') && !/^[0-9\s]+$/.test(clean)) {
          seenPicks.add(clean.toLowerCase());
          syncCount++;
          updateHud(syncCount);
          console.log('⚡ [War Room Auto-Sync] New Yahoo Pick Captured:', clean);
          channel.postMessage({
            type: 'YAHOO_PICK',
            player_name: clean,
            raw_text: rawName,
            timestamp: Date.now()
          });
        }
      }
    });
  }

  // Active DOM Observer for instant detection
  const observer = new MutationObserver(() => {
    scanDraftRoom();
  });

  observer.observe(document.documentElement, {
    childList: true,
    subtree: true
  });

  // Fast polling fallback (every 800ms)
  setInterval(scanDraftRoom, 800);
  scanDraftRoom();
})();
