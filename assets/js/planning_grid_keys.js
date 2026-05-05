/**
 * planning_grid_keys.js
 *
 * Two responsibilities:
 * 1. Prevent the browser's default arrow-key scroll on the focused grid root
 *    (must happen synchronously – cannot be done via Reflex server round-trip).
 * 2. Scroll the active cell into view ONLY when it is outside the visible area,
 *    accounting for the sticky header and the sticky label column.
 */
(function () {
  'use strict';

  var ARROW = ['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'];

  // Keep in sync with planning_grid_state.py constants
  var LABEL_W  = 302;  // LABEL_COL_PX (300) + 1px border
  var HEADER_H = 126;  // 4 header rows × ~30px + small buffer

  function scrollIfNeeded(root) {
    var active = root.querySelector('[data-active-cell="true"]');
    if (!active) return;
    var rr = root.getBoundingClientRect();
    var ar = active.getBoundingClientRect();

    // Vertical
    if (ar.bottom > rr.bottom) {
      root.scrollTop += ar.bottom - rr.bottom + 2;
    } else if (ar.top < rr.top + HEADER_H) {
      root.scrollTop -= (rr.top + HEADER_H) - ar.top + 2;
    }

    // Horizontal
    if (ar.right > rr.right) {
      root.scrollLeft += ar.right - rr.right + 2;
    } else if (ar.left < rr.left + LABEL_W) {
      root.scrollLeft -= (rr.left + LABEL_W) - ar.left + 2;
    }
  }

  function attach(root) {
    if (root._alloqGridAttached) return;
    root._alloqGridAttached = true;

    // 1. Prevent default browser scroll for arrow keys when NOT inside an input
    root.addEventListener('keydown', function (e) {
      if (
        ARROW.indexOf(e.key) !== -1 &&
        e.target.tagName !== 'INPUT' &&
        e.target.tagName !== 'TEXTAREA'
      ) {
        e.preventDefault();
      }
    });

    // 2. Scroll active cell into view only when it leaves the visible area
    var observer = new MutationObserver(function () {
      scrollIfNeeded(root);
    });
    observer.observe(root, {
      subtree: true,
      attributeFilter: ['data-active-cell'],
    });
  }

  function tryAttach() {
    var root = document.getElementById('planning-grid-root');
    if (root) {
      attach(root);
    } else {
      setTimeout(tryAttach, 250);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', tryAttach);
  }
  tryAttach();
})();
