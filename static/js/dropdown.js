/**
 * Dropdown primitive for spoo.me
 *
 * Declarative markup:
 *   <div class="dropdown" data-dropdown>
 *     <button type="button" class="dropdown-trigger" data-dropdown-trigger>Label</button>
 *     <div class="dropdown-menu" data-dropdown-menu>
 *       <button type="button" class="dropdown-item" data-value="x">One</button>
 *       <button type="button" class="dropdown-item" data-value="y">Two</button>
 *     </div>
 *   </div>
 *
 * Auto-applies to every [data-dropdown] on the page and dispatches
 * `dropdown:select` on the .dropdown element with detail { value, text, item, dropdown }.
 *
 * Programmatic API:
 *   Dropdown.open(dropdownEl)
 *   Dropdown.close(dropdownEl)
 *   Dropdown.toggle(dropdownEl)
 *   Dropdown.isOpen(dropdownEl)
 *   Dropdown.closeAll()
 *
 * Styling hooks:
 *   .dropdown.is-open             on open
 *   .dropdown-trigger.is-active   while open
 *   .dropdown-item.is-active      caller sets this to mark the selected row
 */
(function () {
    var OPEN_CLASS = 'is-open';
    var TRIGGER_ACTIVE_CLASS = 'is-active';

    function getTrigger(dropdown) {
        return dropdown.querySelector('[data-dropdown-trigger]')
            || dropdown.querySelector('.dropdown-trigger');
    }

    function getMenu(dropdown) {
        return dropdown.querySelector('[data-dropdown-menu]')
            || dropdown.querySelector('.dropdown-menu');
    }

    function isOpen(dropdown) {
        return !!dropdown && dropdown.classList.contains(OPEN_CLASS);
    }

    function closeAll(except) {
        document.querySelectorAll('.dropdown.' + OPEN_CLASS).forEach(function (d) {
            if (d !== except) close(d);
        });
    }

    function open(dropdown) {
        if (!dropdown || isOpen(dropdown)) return;
        closeAll(dropdown);
        dropdown.classList.add(OPEN_CLASS);
        var trigger = getTrigger(dropdown);
        if (trigger) {
            trigger.classList.add(TRIGGER_ACTIVE_CLASS);
            trigger.setAttribute('aria-expanded', 'true');
        }
    }

    function close(dropdown) {
        if (!dropdown || !isOpen(dropdown)) return;
        dropdown.classList.remove(OPEN_CLASS);
        var trigger = getTrigger(dropdown);
        if (trigger) {
            trigger.classList.remove(TRIGGER_ACTIVE_CLASS);
            trigger.setAttribute('aria-expanded', 'false');
        }
    }

    function toggle(dropdown) {
        if (isOpen(dropdown)) close(dropdown);
        else open(dropdown);
    }

    function focusItem(menu, item) {
        if (!item) return;
        item.focus();
    }

    function items(menu) {
        return Array.prototype.slice.call(
            menu.querySelectorAll('.dropdown-item:not([disabled])')
        );
    }

    function handleKeydown(e) {
        if (e.key === 'Escape') {
            // Close topmost open modal (uses .modal.active convention).
            // Prefer clicking the modal's own close button so its cleanup runs.
            var openModals = document.querySelectorAll('.modal.active');
            if (openModals.length) {
                var topModal = openModals[openModals.length - 1];
                var closeBtn = topModal.querySelector('.modal-close, [data-modal-close]');
                if (closeBtn) {
                    closeBtn.click();
                } else {
                    topModal.classList.remove('active');
                }
                e.preventDefault();
                return;
            }

            // Close any open primitive dropdown, regardless of focus.
            var openDropdowns = document.querySelectorAll('.dropdown.' + OPEN_CLASS);
            if (openDropdowns.length) {
                var focusTarget = null;
                openDropdowns.forEach(function (d) {
                    if (!focusTarget) focusTarget = getTrigger(d);
                    close(d);
                });
                if (focusTarget) focusTarget.focus();
                e.preventDefault();
                return;
            }
            return;
        }

        var dropdown = e.target.closest('.dropdown');
        if (!dropdown || !isOpen(dropdown)) return;

        var menu = getMenu(dropdown);
        if (!menu) return;
        var list = items(menu);
        if (!list.length) return;
        var currentIdx = list.indexOf(document.activeElement);

        if (e.key === 'ArrowDown') {
            e.preventDefault();
            focusItem(menu, list[(currentIdx + 1) % list.length]);
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            focusItem(menu, list[(currentIdx - 1 + list.length) % list.length]);
        } else if (e.key === 'Home') {
            e.preventDefault();
            focusItem(menu, list[0]);
        } else if (e.key === 'End') {
            e.preventDefault();
            focusItem(menu, list[list.length - 1]);
        }
    }

    function onDocumentClick(e) {
        var trigger = e.target.closest('[data-dropdown-trigger], .dropdown-trigger');
        if (trigger) {
            var dropdown = trigger.closest('.dropdown');
            if (dropdown) {
                e.preventDefault();
                toggle(dropdown);
                return;
            }
        }

        var item = e.target.closest('.dropdown-item');
        if (item && !item.hasAttribute('disabled')) {
            var dd = item.closest('.dropdown');
            if (dd) {
                var detail = {
                    value: item.getAttribute('data-value'),
                    text: (item.textContent || '').trim(),
                    item: item,
                    dropdown: dd
                };
                dd.dispatchEvent(new CustomEvent('dropdown:select', {
                    bubbles: true,
                    detail: detail
                }));
                if (!item.hasAttribute('data-dropdown-keep-open')) {
                    close(dd);
                }
                return;
            }
        }

        // Click anywhere else closes all open dropdowns.
        if (!e.target.closest('.dropdown.' + OPEN_CLASS)) {
            closeAll();
        }
    }

    function init() {
        document.addEventListener('click', onDocumentClick);
        document.addEventListener('keydown', handleKeydown);
        // Prime aria attributes on existing dropdowns.
        document.querySelectorAll('.dropdown').forEach(function (d) {
            var trigger = getTrigger(d);
            if (trigger) {
                trigger.setAttribute('aria-haspopup', 'menu');
                trigger.setAttribute('aria-expanded', 'false');
            }
            var menu = getMenu(d);
            if (menu) menu.setAttribute('role', 'menu');
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    window.Dropdown = {
        open: open,
        close: close,
        toggle: toggle,
        isOpen: isOpen,
        closeAll: closeAll
    };
})();
