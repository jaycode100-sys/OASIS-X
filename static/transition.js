/* ── OASIS-X Page Transition Loader ── */
(function () {
  // Don't add loader on dashboard (it has its own auth flow)
  if (window.location.pathname === '/dashboard') return;

  // Create loader overlay
  var overlay = document.createElement('div');
  overlay.id = 'page-loader-overlay';
  overlay.innerHTML = '<div class="pl-spinner"><div class="pl-blob"></div><div class="pl-text">OASIS-X</div></div>';
  overlay.style.cssText = 'position:fixed;inset:0;z-index:99999;background:#030a12;display:none;align-items:center;justify-content:center;opacity:0;transition:opacity 0.3s ease;';
  document.body.appendChild(overlay);

  // Add styles
  var style = document.createElement('style');
  style.textContent = '\
    #page-loader-overlay { flex-direction: column; gap: 20px; }\
    .pl-spinner { display: flex; flex-direction: column; align-items: center; gap: 16px; }\
    .pl-blob { width: 48px; height: 48px; border-radius: 50%; background: radial-gradient(circle, #00ff88 0%, transparent 70%); animation: pl-pulse 1s ease-in-out infinite; }\
    .pl-text { font-family: "Space Grotesk", sans-serif; font-size: 18px; font-weight: 700; color: #00ff88; letter-spacing: 2px; animation: pl-fade 1s ease-in-out infinite alternate; }\
    @keyframes pl-pulse { 0%, 100% { transform: scale(0.8); opacity: 0.5; } 50% { transform: scale(1.2); opacity: 1; } }\
    @keyframes pl-fade { 0% { opacity: 0.4; } 100% { opacity: 1; } }\
  ';
  document.head.appendChild(style);

  var loader = overlay;
  var transitioning = false;

  function showLoader(href) {
    if (transitioning) return;
    transitioning = true;
    loader.style.display = 'flex';
    requestAnimationFrame(function () { loader.style.opacity = '1'; });
    setTimeout(function () { window.location.href = href; }, 1200);
  }

  // Intercept internal links
  document.addEventListener('click', function (e) {
    var link = e.target.closest('a');
    if (!link) return;
    var href = link.getAttribute('href');
    if (!href) return;
    // Skip external, hash-only, javascript:, mailto:, anchor clicks
    if (href.startsWith('http') || href.startsWith('mailto:') || href.startsWith('javascript:') || href.startsWith('#')) return;
    // Skip if target=_blank
    if (link.target === '_blank') return;
    // Skip if modifier key pressed
    if (e.ctrlKey || e.metaKey || e.shiftKey) return;
    e.preventDefault();
    showLoader(href);
  });

  // Handle back/forward browser navigation
  window.addEventListener('popstate', function () {
    loader.style.display = 'flex';
    loader.style.opacity = '1';
  });
})();
