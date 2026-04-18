/**
 * Shared modal tab helper for spoo.me.
 *
 * Markup contract (unchanged from existing modals):
 *   <div class="tabs" data-active="0">
 *     <button class="tab active" data-tab="basic">…</button>
 *     <button class="tab" data-tab="security">…</button>
 *   </div>
 *   …
 *   <div class="tab-content active" data-tab="basic">…</div>
 *   <div class="tab-content" data-tab="security">…</div>
 *
 * Auto-initializes every `.tabs` on DOMContentLoaded. Tab-content panes must
 * live under the same `.modal` ancestor as the `.tabs` container.
 *
 *   ModalTabs.setActive(tabsContainer, index)
 *   ModalTabs.reset(modalEl)   // always back to tab 0 — content, buttons, indicator
 */
(function () {
    function getContents(tabsContainer) {
        var scope = tabsContainer.closest('.modal') || tabsContainer.closest('form') || document;
        return scope.querySelectorAll('.tab-content');
    }

    function setActive(tabsContainer, index) {
        if (!tabsContainer) return;
        var tabs = tabsContainer.querySelectorAll('.tab');
        if (!tabs.length) return;
        var idx = Math.max(0, Math.min(index, tabs.length - 1));
        var targetTab = tabs[idx].getAttribute('data-tab');

        tabsContainer.setAttribute('data-active', String(idx));
        tabs.forEach(function (t, i) {
            t.classList.toggle('active', i === idx);
        });
        getContents(tabsContainer).forEach(function (content) {
            content.classList.toggle('active', content.getAttribute('data-tab') === targetTab);
        });
    }

    function init(tabsContainer) {
        if (!tabsContainer || tabsContainer._modalTabsBound) return;
        tabsContainer._modalTabsBound = true;
        var tabs = tabsContainer.querySelectorAll('.tab');
        tabs.forEach(function (tab, index) {
            tab.addEventListener('click', function (e) {
                e.preventDefault();
                setActive(tabsContainer, index);
            });
        });
    }

    function reset(modal) {
        if (!modal) return;
        var tabsContainer = modal.querySelector('.tabs');
        if (tabsContainer) setActive(tabsContainer, 0);
        modal.querySelectorAll('.tab.has-error').forEach(function (t) {
            t.classList.remove('has-error');
        });
    }

    function paneHasErrors(pane) {
        return !!(pane && (pane.querySelector('.field.has-error') || pane.querySelector('.field-error')));
    }

    /**
     * Scan each tab pane and toggle `.has-error` on its tab button so the red
     * dot reflects real state. Cheap enough to call on every field change.
     */
    function refreshErrors(modal) {
        if (!modal) return;
        var tabs = modal.querySelectorAll('.tabs .tab');
        tabs.forEach(function (tab) {
            var targetTab = tab.getAttribute('data-tab');
            var pane = modal.querySelector('.tab-content[data-tab="' + targetTab + '"]');
            tab.classList.toggle('has-error', paneHasErrors(pane));
        });
    }

    /**
     * If the currently active tab has no errors but another tab does, jump to
     * the first (leftmost) tab with errors. Otherwise stay put.
     */
    function jumpToFirstInvalid(modal) {
        if (!modal) return;
        var tabsContainer = modal.querySelector('.tabs');
        if (!tabsContainer) return;
        var tabs = tabsContainer.querySelectorAll('.tab');
        var activeTab = tabsContainer.querySelector('.tab.active');
        if (activeTab) {
            var activePane = modal.querySelector('.tab-content[data-tab="' + activeTab.getAttribute('data-tab') + '"]');
            if (paneHasErrors(activePane)) return;
        }
        for (var i = 0; i < tabs.length; i++) {
            var pane = modal.querySelector('.tab-content[data-tab="' + tabs[i].getAttribute('data-tab') + '"]');
            if (paneHasErrors(pane)) {
                setActive(tabsContainer, i);
                return;
            }
        }
    }

    function autoInit() {
        document.querySelectorAll('.tabs').forEach(init);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', autoInit);
    } else {
        autoInit();
    }

    window.ModalTabs = {
        setActive: setActive,
        init: init,
        reset: reset,
        refreshErrors: refreshErrors,
        jumpToFirstInvalid: jumpToFirstInvalid
    };
})();
