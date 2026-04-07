// Initialize segmented controls for the options dropdown
document.addEventListener('DOMContentLoaded', function () {
    function initSegments() {
        const segs = document.querySelectorAll('.seg');
        segs.forEach(seg => {
            const targetId = seg.getAttribute('data-target');
            const hidden = document.getElementById(targetId);
            const buttons = Array.from(seg.querySelectorAll('button[data-value]'));
            const indexByValue = new Map(buttons.map((b, i) => [b.getAttribute('data-value'), i]));

            function apply(value) {
                if (hidden) { hidden.value = value; }
                const idx = indexByValue.has(value) ? indexByValue.get(value) : 0;
                seg.setAttribute('data-active', String(idx));

                // Update button states
                buttons.forEach((btn, i) => {
                    btn.classList.toggle('active', i === idx);
                });
            }

            apply(hidden ? hidden.value : '');
            buttons.forEach(btn => btn.addEventListener('click', (e) => {
                e.preventDefault();
                apply(btn.getAttribute('data-value') || '');
            }));
        });
    }

    initSegments();

    // Initialize datetime icon clicks
    initDateTimeIcons();
});

function initDateTimeIcons() {
    const datetimeIcons = document.querySelectorAll('.datetime-icon');

    datetimeIcons.forEach(icon => {
        icon.addEventListener('click', function () {
            const input = this.previousElementSibling;
            if (input && input.type === 'datetime-local') {
                input.focus();
                input.showPicker?.();
            }
        });
    });
}

// Global confetti management
window.confettiAnimationId = null;
window.confettiActive = false;

// Create Link Modal Functions
function openCreateLinkModal() {
    const modal = document.getElementById('create-link-modal');

    if (modal) {
        modal.classList.add('active');
        document.body.style.overflow = 'hidden';

        // Focus on the first input
        setTimeout(() => {
            const firstInput = modal.querySelector('#create-long-url');
            if (firstInput) firstInput.focus();
        }, 100);
    }
}

function closeCreateLinkModal() {
    const modal = document.getElementById('create-link-modal');
    if (modal) {
        modal.classList.remove('active');
        document.body.style.overflow = '';

        // Reset form
        const form = document.getElementById('create-link-form');
        if (form) form.reset();

        // Clear any error states
        const errorFields = modal.querySelectorAll('.error');
        errorFields.forEach(field => field.classList.remove('error'));
        const errorMessages = modal.querySelectorAll('.field-error');
        errorMessages.forEach(msg => msg.remove());

        // Reset to first tab
        const tabs = modal.querySelectorAll('.tab');
        const contents = modal.querySelectorAll('.tab-content');
        tabs.forEach((tab, i) => {
            tab.classList.toggle('active', i === 0);
        });
        contents.forEach((content, i) => {
            content.classList.toggle('active', i === 0);
        });
    }
}

function openLinkSuccessModal(shortUrl, linkData) {
    const modal = document.getElementById('link-success-modal');
    const input = document.getElementById('created-link-input');
    const visitLink = document.getElementById('created-link-visit');
    const qrImg = document.getElementById('created-link-qr');

    if (modal && input && visitLink) {
        input.value = shortUrl;
        visitLink.href = shortUrl;

        // Show loading state for QR code
        if (qrImg) {
            qrImg.removeAttribute("src");
            qrImg.style.opacity = "0";
            qrImg.parentElement.style.animation = "qr-loading 1.5s infinite";

            const enc = encodeURIComponent(shortUrl);
            qrImg.onload = function () {
                qrImg.parentElement.style.animation = "none";
                qrImg.style.opacity = "1";
                setupQRCodeInteractions();
            };
            qrImg.src = `https://qr.spoo.me/api/v1/gradient?content=${enc}&size=280&start=%231d1919&end=%23322c29`;
        }

        modal.classList.add('active');
        document.body.style.overflow = 'hidden';

        // Auto-copy the URL to clipboard
        setTimeout(() => {
            try {
                navigator.clipboard.writeText(shortUrl).then(() => {
                    // Update the copy button to show copied state
                    const copyBtn = document.getElementById('btn-copy-created-link');
                    const icon = copyBtn?.querySelector('i');
                    if (copyBtn) {
                        copyBtn.classList.add('copied');
                        if (icon) {
                            icon.className = 'ti ti-check';
                        }
                        setTimeout(() => {
                            copyBtn.classList.remove('copied');
                            if (icon) {
                                icon.className = 'ti ti-copy';
                            }
                        }, 2000);
                    }
                }).catch(() => {
                    // Fallback for older browsers
                    input.select();
                    input.setSelectionRange(0, 99999);
                    document.execCommand('copy');
                    // Update the copy button to show copied state
                    const copyBtn = document.getElementById('btn-copy-created-link');
                    const icon = copyBtn?.querySelector('i');
                    if (copyBtn) {
                        copyBtn.classList.add('copied');
                        if (icon) {
                            icon.className = 'ti ti-check';
                        }
                        setTimeout(() => {
                            copyBtn.classList.remove('copied');
                            if (icon) {
                                icon.className = 'ti ti-copy';
                            }
                        }, 2000);
                    }
                });
            } catch (err) {
                console.log('Auto-copy failed:', err);
            }
        }, 500);

        // Trigger confetti effect
        setTimeout(() => {
            if (window.confetti && !window.confettiActive) {
                // Check for reduced motion preference
                const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

                if (!prefersReducedMotion) {
                    window.confettiActive = true;

                    // Launch confetti from multiple directions with higher z-index
                    const duration = 3000;
                    const end = Date.now() + duration;

                    // Initial big burst
                    confetti({
                        particleCount: 100,
                        spread: 70,
                        origin: { y: 0.6 },
                        colors: ['#6366f1', '#8b5cf6', '#06b6d4', '#10b981', '#f59e0b'],
                        zIndex: 10000
                    });

                    // Continuous smaller bursts
                    (function frame() {
                        if (!window.confettiActive) return; // Stop if confetti was disabled

                        confetti({
                            particleCount: 3,
                            angle: 60,
                            spread: 55,
                            origin: { x: 0, y: 0.7 },
                            colors: ['#6366f1', '#8b5cf6', '#06b6d4'],
                            zIndex: 10000
                        });
                        confetti({
                            particleCount: 3,
                            angle: 120,
                            spread: 55,
                            origin: { x: 1, y: 0.7 },
                            colors: ['#6366f1', '#8b5cf6', '#06b6d4'],
                            zIndex: 10000
                        });

                        if (Date.now() < end && window.confettiActive) {
                            window.confettiAnimationId = requestAnimationFrame(frame);
                        } else {
                            window.confettiAnimationId = null;
                            window.confettiActive = false;
                        }
                    }());
                }
            }
        }, 100);
    }
}

function closeLinkSuccessModal() {
    const modal = document.getElementById('link-success-modal');
    if (modal) {
        modal.classList.remove('active');
        document.body.style.overflow = '';

        // Stop confetti animation immediately
        window.confettiActive = false;

        if (window.confettiAnimationId) {
            cancelAnimationFrame(window.confettiAnimationId);
            window.confettiAnimationId = null;
        }

        // Clear all existing confetti
        if (window.confetti && window.confetti.reset) {
            confetti.reset();
        }
    }
}

function copyCreatedLinkToClipboard() {
    try {
        const input = document.getElementById('created-link-input');
        const btn = document.getElementById('btn-copy-created-link');
        const icon = btn?.querySelector('i');

        navigator.clipboard.writeText(input.value).then(() => {
            btn?.classList.add('copied');
            if (icon) {
                icon.className = 'ti ti-check';
            }
            if (typeof showNotification === 'function') {
                showNotification('Link copied to clipboard again!', 'success');
            }
            setTimeout(() => {
                btn?.classList.remove('copied');
                if (icon) {
                    icon.className = 'ti ti-copy';
                }
            }, 1200);
        }).catch(() => {
            input.select();
            input.setSelectionRange(0, 99999);
            document.execCommand('copy');
            btn?.classList.add('copied');
            if (icon) {
                icon.className = 'ti ti-check';
            }
            if (typeof showNotification === 'function') {
                showNotification('Link copied to clipboard again!', 'success');
            }
            setTimeout(() => {
                btn?.classList.remove('copied');
                if (icon) {
                    icon.className = 'ti ti-copy';
                }
            }, 1200);
        });
    } catch (_) {
        console.log('Copy failed');
    }
}

function createAnotherLink() {
    closeLinkSuccessModal();
    openCreateLinkModal();
}

// QR Code interaction setup (similar to result.html)
function setupQRCodeInteractions() {
    const qrContainer = document.getElementById('qr-container');
    const qrOverlay = document.getElementById('qr-overlay');

    if (qrContainer && qrOverlay) {
        qrContainer.style.cursor = "pointer";

        qrContainer.addEventListener("mouseenter", function () {
            qrOverlay.style.opacity = "1";
            qrOverlay.style.visibility = "visible";
        });

        qrContainer.addEventListener("mouseleave", function () {
            qrOverlay.style.opacity = "0";
            qrOverlay.style.visibility = "hidden";
        });

        qrContainer.addEventListener("click", function () {
            downloadQRCodeFromModal();
        });
    }
}

// QR Code download — uses the already-loaded image via canvas to avoid CORS
function downloadQRCodeFromModal() {
    const qrImg = document.getElementById("created-link-qr");
    if (!qrImg || !qrImg.naturalWidth === 0) return;

    const canvas = document.createElement("canvas");
    canvas.width = qrImg.naturalWidth;
    canvas.height = qrImg.naturalHeight;
    canvas.getContext("2d").drawImage(qrImg, 0, 0);

    const link = document.createElement("a");
    link.href = canvas.toDataURL("image/png");
    link.download = "qrcode.png";
    link.click();

    if (typeof showNotification === 'function') {
        showNotification('QR code downloaded successfully!', 'success');
    }
}

// Form Validation Functions
function validateUrl(url) {
    if (!url) return { valid: false, message: 'URL is required' };

    // Basic URL pattern check
    const urlPattern = /^https?:\/\/.+/i;
    if (!urlPattern.test(url)) {
        return { valid: false, message: 'URL must start with http:// or https://' };
    }

    // Check if URL contains spoo.me (not allowed)
    if (url.toLowerCase().includes('spoo.me')) {
        return { valid: false, message: 'Cannot shorten spoo.me URLs' };
    }

    return { valid: true, message: '' };
}

function validateAlias(alias) {
    if (!alias) return { valid: true, message: '' }; // Optional field

    // Check pattern: alphanumeric, underscore, hyphen only
    const aliasPattern = /^[a-zA-Z0-9_-]+$/;
    if (!aliasPattern.test(alias)) {
        return { valid: false, message: 'Alias can only contain letters, numbers, underscores, and hyphens' };
    }

    if (alias.length > 16) {
        return { valid: false, message: 'Alias cannot be longer than 16 characters' };
    }

    return { valid: true, message: '' };
}

function validatePassword(password) {
    if (!password) return { valid: true, message: '' }; // Optional field

    if (password.length < 8) {
        return { valid: false, message: 'Password must be at least 8 characters long' };
    }

    if (!/[a-zA-Z]/.test(password)) {
        return { valid: false, message: 'Password must contain at least one letter' };
    }

    if (!/\d/.test(password)) {
        return { valid: false, message: 'Password must contain at least one number' };
    }

    if (!/[@.]/.test(password)) {
        return { valid: false, message: 'Password must contain @ or .' };
    }

    if (/[@.]{2}/.test(password)) {
        return { valid: false, message: 'Password cannot have consecutive @ or . characters' };
    }

    return { valid: true, message: '' };
}

function validateMaxClicks(maxClicks) {
    if (!maxClicks) return { valid: true, message: '' }; // Optional field

    const clicks = parseInt(maxClicks);
    if (isNaN(clicks) || clicks <= 0) {
        return { valid: false, message: 'Max clicks must be a positive number' };
    }

    return { valid: true, message: '' };
}

function validateExpireAfter(expireAfter) {
    if (!expireAfter) return { valid: true, message: '' }; // Optional field

    const expireDate = new Date(expireAfter);
    const now = new Date();

    if (expireDate <= now) {
        return { valid: false, message: 'Expiration date must be in the future' };
    }

    return { valid: true, message: '' };
}

function showFieldError(fieldId, message) {
    const field = document.getElementById(fieldId);
    if (!field) return;

    // Remove existing error
    const existingError = field.parentNode.querySelector('.field-error');
    if (existingError) existingError.remove();

    if (message) {
        // Add error styling
        field.classList.add('error');

        // Add error message
        const errorEl = document.createElement('small');
        errorEl.className = 'field-error';
        errorEl.textContent = message;
        field.parentNode.appendChild(errorEl);
    } else {
        // Remove error styling
        field.classList.remove('error');
    }
}

function validateForm() {
    let isValid = true;

    // Get form values
    const longUrl = document.getElementById('create-long-url').value.trim();
    const alias = document.getElementById('create-alias').value.trim();
    const password = document.getElementById('create-password').value;
    const maxClicks = document.getElementById('create-max-clicks').value;
    const expireAfter = document.getElementById('create-expire-after').value;

    // Validate each field
    const urlValidation = validateUrl(longUrl);
    const aliasValidation = validateAlias(alias);
    const passwordValidation = validatePassword(password);
    const maxClicksValidation = validateMaxClicks(maxClicks);
    const expireAfterValidation = validateExpireAfter(expireAfter);

    // Show errors
    showFieldError('create-long-url', urlValidation.valid ? '' : urlValidation.message);
    showFieldError('create-alias', aliasValidation.valid ? '' : aliasValidation.message);
    showFieldError('create-password', passwordValidation.valid ? '' : passwordValidation.message);
    showFieldError('create-max-clicks', maxClicksValidation.valid ? '' : maxClicksValidation.message);
    showFieldError('create-expire-after', expireAfterValidation.valid ? '' : expireAfterValidation.message);

    return urlValidation.valid && aliasValidation.valid && passwordValidation.valid &&
        maxClicksValidation.valid && expireAfterValidation.valid;
}

// Form Submission
async function submitCreateForm(event) {
    event.preventDefault();

    if (!validateForm()) {
        return;
    }

    const submitBtn = document.getElementById('btn-create-submit');
    const originalText = submitBtn.innerHTML;

    // Show loading state
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<i class="ti ti-loader-2 spinning"></i><span>Creating...</span>';

    try {
        // Prepare form data
        const formData = {
            long_url: document.getElementById('create-long-url').value.trim(),
            alias: document.getElementById('create-alias').value.trim() || undefined,
            password: document.getElementById('create-password').value || undefined,
            max_clicks: document.getElementById('create-max-clicks').value ?
                parseInt(document.getElementById('create-max-clicks').value) : undefined,
            expire_after: document.getElementById('create-expire-after').value || undefined,
            block_bots: document.getElementById('create-block-bots').checked,
            private_stats: document.getElementById('create-private-stats').checked
        };

        // Remove undefined values
        Object.keys(formData).forEach(key => {
            if (formData[key] === undefined) {
                delete formData[key];
            }
        });

        // Submit to API
        const response = await authFetch('/api/v1/shorten', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(formData)
        });

        const result = await response.json();

        if (response.ok) {
            // Success - close create modal and show success modal
            closeCreateLinkModal();
            openLinkSuccessModal(result.short_url, result);

            // Refresh the links list to show the new URL
            if (typeof window.fetchData === 'function') {
                setTimeout(() => {
                    window.fetchData();
                }, 500); // Small delay to ensure any confetti animation doesn't interfere
            }
        } else {
            // Handle API errors
            handleApiError(result);
        }

    } catch (error) {
        console.error('Error creating link:', error);
        if (typeof showNotification === 'function') {
            showNotification('Failed to create link. Please try again.', 'error');
        }
    } finally {
        // Reset button state
        submitBtn.disabled = false;
        submitBtn.innerHTML = originalText;
    }
}

function handleApiError(result) {
    // Handle email verification error specifically
    if (result.code === 'EMAIL_NOT_VERIFIED') {
        if (typeof showVerificationModal === 'function') {
            showVerificationModal('create short URLs');
        } else {
            if (typeof showNotification === 'function') {
                showNotification(result.message || 'Email verification required', 'error');
            }
        }
        return;
    }

    // Handle field-specific errors
    if (result.field) {
        const fieldMap = {
            'long_url': 'create-long-url',
            'url': 'create-long-url',
            'alias': 'create-alias',
            'password': 'create-password',
            'max_clicks': 'create-max-clicks',
            'expire_after': 'create-expire-after'
        };

        const fieldId = fieldMap[result.field];
        if (fieldId) {
            showFieldError(fieldId, result.error);
            return;
        }
    }

    // Handle general errors
    let errorMessage = result.error || 'An error occurred while creating the link';

    // Customize common error messages
    if (errorMessage.includes('Alias already exists')) {
        showFieldError('create-alias', 'This alias is already taken. Please choose another.');
    } else if (errorMessage.includes('Blocked URL')) {
        showFieldError('create-long-url', 'This URL is not allowed to be shortened.');
    } else if (errorMessage.includes('api key lacks required scope')) {
        errorMessage = 'You do not have permission to create links. Please check your account settings.';
    } else if (errorMessage.includes('ratelimit exceeded')) {
        errorMessage = 'You are creating links too quickly. Please wait a moment and try again.';
    }

    // Show general notification
    if (typeof showNotification === 'function') {
        showNotification(errorMessage, 'error');
    }
}

// Event Listeners
document.addEventListener('DOMContentLoaded', function () {
    // Create Link button
    const createBtn = document.getElementById('btn-create-link');
    if (createBtn) {
        createBtn.addEventListener('click', function (e) {
            e.preventDefault();
            if (checkVerificationBeforeShorten()) {
                openCreateLinkModal();
            }
        });
    }

    // Modal close buttons
    const cancelBtn = document.getElementById('btn-cancel-create');
    if (cancelBtn) {
        cancelBtn.addEventListener('click', closeCreateLinkModal);
    }

    // Form submission
    const createForm = document.getElementById('create-link-form');
    if (createForm) {
        createForm.addEventListener('submit', submitCreateForm);
    }

    // Real-time validation on input
    const inputs = ['create-long-url', 'create-alias', 'create-password', 'create-max-clicks', 'create-expire-after'];
    inputs.forEach(inputId => {
        const input = document.getElementById(inputId);
        if (input) {
            input.addEventListener('blur', function () {
                // Clear previous errors when user starts typing
                showFieldError(inputId, '');
            });
        }
    });

    // Close modal on backdrop click
    const modal = document.getElementById('create-link-modal');
    if (modal) {
        modal.addEventListener('click', function (e) {
            if (e.target === modal || e.target.classList.contains('modal-backdrop')) {
                closeCreateLinkModal();
            }
        });
    }

    // Close modal on X button
    const closeBtn = modal?.querySelector('.modal-close');
    if (closeBtn) {
        closeBtn.addEventListener('click', closeCreateLinkModal);
    }

    // Tab switching for create modal
    const createTabs = document.querySelectorAll('#create-link-modal .tab');
    createTabs.forEach((tab, index) => {
        tab.addEventListener('click', function () {
            const targetTab = this.dataset.tab;
            const modal = document.getElementById('create-link-modal');
            const tabsContainer = modal.querySelector('.tabs');

            // Update tab indicator position
            if (tabsContainer) {
                tabsContainer.setAttribute('data-active', index.toString());
            }

            // Update tab states
            modal.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            modal.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));

            this.classList.add('active');
            modal.querySelector(`[data-tab="${targetTab}"].tab-content`).classList.add('active');
        });
    });

    // ESC key to close modals
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') {
            const createModal = document.getElementById('create-link-modal');
            const successModal = document.getElementById('link-success-modal');

            if (successModal?.classList.contains('active')) {
                closeLinkSuccessModal();
            } else if (createModal?.classList.contains('active')) {
                closeCreateLinkModal();
            }
        }
    });

    // Close modal on backdrop click for success modal
    const successModal = document.getElementById('link-success-modal');
    if (successModal) {
        successModal.addEventListener('click', function (e) {
            if (e.target === successModal || e.target.classList.contains('modal-backdrop')) {
                closeLinkSuccessModal();
            }
        });
    }

    // Success modal actions: copy (download now handled by QR hover overlay)
    const copyBtn = document.getElementById('btn-copy-created-link');
    copyBtn?.addEventListener('click', copyCreatedLinkToClipboard);
});
(function () {
    // Get host URL from window config or fallback to root element
    const rawHost = window.dashboardConfig?.hostUrl || document.querySelector('[data-host]')?.getAttribute('data-host') || '';
    const host = rawHost.replace(/\/+$/, '');
    const displayHost = host ? (host + '/') : '/';

    const els = {
        search: document.getElementById('f-search'),
        status: document.getElementById('f-status'),
        password: document.getElementById('f-password'),
        maxClicks: document.getElementById('f-maxclicks'),
        createdAfter: document.getElementById('f-created-after'),
        createdBefore: document.getElementById('f-created-before'),
        sortBy: document.getElementById('f-sortby'),
        order: document.getElementById('f-order'),
        pageSize: document.getElementById('f-pagesize'),
        apply: document.getElementById('btn-apply'),
        reset: document.getElementById('btn-reset'),
        optionsBtn: document.getElementById('btn-options'),
        optionsDropdown: document.getElementById('options-dropdown'),
        loading: document.getElementById('list-loading'),
        empty: document.getElementById('list-empty'),
        list: document.getElementById('links-list'),
        pagination: document.getElementById('pagination'),
        tpl: document.getElementById('tpl-link-item'),
    };

    let state = {
        page: 1,
        hasNext: false,
        total: 0,
        pageSize: 20,
        sortBy: 'last_click',
        sortOrder: 'descending',
        filters: {},
    };

    function toEpochSeconds(value) {
        if (!value) return undefined;
        try { return Math.floor(new Date(value).getTime() / 1000); } catch { return undefined; }
    }

    function buildQuery() {
        const filter = {};
        if (els.search.value.trim()) filter.search = els.search.value.trim();
        if (els.status.value) filter.status = els.status.value;
        if (els.password.value) filter.passwordSet = els.password.value;
        if (els.maxClicks.value) filter.maxClicksSet = els.maxClicks.value;
        if (els.createdAfter.value) filter.createdAfter = toEpochSeconds(els.createdAfter.value);
        if (els.createdBefore.value) filter.createdBefore = toEpochSeconds(els.createdBefore.value);

        const params = new URLSearchParams();
        params.set('page', String(state.page));
        params.set('pageSize', String(els.pageSize.value || state.pageSize));
        params.set('sortBy', els.sortBy.value || state.sortBy);
        params.set('sortOrder', els.order.value || state.sortOrder);
        if (Object.keys(filter).length) { params.set('filter', JSON.stringify(filter)); }
        return params.toString();
    }

    function setLoading(isLoading) {
        els.loading.style.display = isLoading ? 'block' : 'none';
    }

    function clearList() {
        els.list.innerHTML = '';
    }

    function formatDate(iso) {
        if (!iso) return '—';
        return window.SmartDatetime ? window.SmartDatetime.formatCreated(iso) :
            (() => { try { return new Date(iso).toLocaleString(); } catch { return '—'; } })();
    }

    function formatTs(ts) {
        if (!ts && ts !== 0) return '—';
        return window.SmartDatetime ? window.SmartDatetime.formatLastClick(ts) :
            (() => { try { return new Date(ts * 1000).toLocaleString(); } catch { return '—'; } })();
    }

    function trimProtocol(url) {
        if (!url) return '';
        return String(url).replace(/^https?:\/\//i, '');
    }

    function createItem(it) {
        const node = els.tpl.content.firstElementChild.cloneNode(true);
        const shortA = node.querySelector('.link-short');
        const long = node.querySelector('.link-long');
        const activeBadge = node.querySelector('.badge-active');
        const inactiveBadge = node.querySelector('.badge-inactive');
        const blockedBadge = node.querySelector('.badge-blocked');
        const expiredBadge = node.querySelector('.badge-expired');
        const pwBadge = node.querySelector('.badge-password');
        const mcBadge = node.querySelector('.badge-max-clicks');
        const privBadge = node.querySelector('.badge-private');
        const blockBotsBadge = node.querySelector('.badge-block-bots');
        const created = node.querySelector('.created-date');
        const last = node.querySelector('.last-click-date');
        const total = node.querySelector('.total-clicks-count');

        // Short URL
        shortA.textContent = trimProtocol(displayHost) + (it.alias ? it.alias : '');
        shortA.href = '/' + (it.alias || '');

        // Long URL
        long.textContent = it.long_url || '';
        long.title = it.long_url || '';

        // Dates and clicks
        created.textContent = formatDate(it.created_at);
        last.textContent = formatTs(it.last_click);
        total.textContent = (it.total_clicks ?? '0');

        // Status badges - show appropriate badge based on status
        if (it.status === 'ACTIVE') {
            activeBadge.style.display = 'inline-flex';
        } else if (it.status === 'INACTIVE') {
            inactiveBadge.style.display = 'inline-flex';
        } else if (it.status === 'BLOCKED') {
            blockedBadge.style.display = 'inline-flex';
            node.classList.add('row-blocked');
        } else if (it.status === 'EXPIRED') {
            expiredBadge.style.display = 'inline-flex';
        }

        // Password badge
        if (it.password_set) {
            pwBadge.style.display = 'inline-flex';
        }

        // Max clicks badge
        if (typeof it.max_clicks === 'number') {
            mcBadge.style.display = 'inline-flex';
            mcBadge.setAttribute('data-tooltip', `Max clicks: ${it.max_clicks}`);
        }

        // Private stats badge
        if (it.private_stats) {
            privBadge.style.display = 'inline-flex';
        }

        // Block bots badge
        if (it.block_bots) {
            blockBotsBadge.style.display = 'inline-flex';
        }

        // Store full URL data on the row for the modal
        node.setAttribute('data-url-data', JSON.stringify(it));
        node.style.cursor = 'pointer';
        node.classList.add('clickable-row');

        return node;
    }

    async function fetchData() {
        setLoading(true);
        els.empty.style.display = 'none';
        try {
            const qs = buildQuery();
            const doFetch = (typeof window.authFetch === 'function') ? window.authFetch : fetch;
            const res = await doFetch(`/api/v1/urls?${qs}`, { credentials: 'include' });
            if (!res.ok) { throw new Error('Request failed'); }
            const data = await res.json();
            state.page = data.page;
            state.pageSize = data.pageSize;
            state.total = data.total;
            state.hasNext = data.hasNext;
            state.sortBy = data.sortBy;
            state.sortOrder = data.sortOrder;

            clearList();
            if (!data.items || data.items.length === 0) {
                els.empty.style.display = 'block';
                document.getElementById('links-table').style.display = 'none';
                els.pagination.style.display = 'none';
                return;
            }
            document.getElementById('links-table').style.display = 'block';
            const frag = document.createDocumentFragment();
            for (const it of data.items) { frag.appendChild(createItem(it)); }
            els.list.appendChild(frag);
            renderPagination();

            // Initialize tooltips for the newly created items
            initializeTooltips();
        } catch (err) {
            clearList();
            els.empty.style.display = 'block';
            document.getElementById('links-table').style.display = 'none';
        } finally {
            setLoading(false);
        }
    }

    // Initialize Tippy.js tooltips for attribute badges
    function initializeTooltips() {
        // Destroy existing tooltips first
        if (window.attributeTooltips) {
            window.attributeTooltips.forEach(instance => instance.destroy());
        }
        window.attributeTooltips = [];

        // Find all tooltip triggers and initialize Tippy.js
        const tooltipTriggers = document.querySelectorAll('.tooltip-trigger[data-tooltip]');

        tooltipTriggers.forEach(element => {
            // Remove the title attribute to prevent native tooltips
            element.removeAttribute('title');

            const instance = tippy(element, {
                content: element.getAttribute('data-tooltip'),
                placement: 'top',
                theme: 'dark',
                animation: 'fade',
                duration: [200, 150],
                delay: [200, 0],
                arrow: true,
                hideOnClick: false,
                trigger: 'mouseenter focus',
                zIndex: 9999
            });
            window.attributeTooltips.push(instance);
        });
    }

    function renderPagination() {
        const totalPages = Math.max(1, Math.ceil(state.total / state.pageSize));
        if (totalPages <= 1) { els.pagination.style.display = 'none'; return; }
        els.pagination.style.display = 'flex';
        const start = (state.page - 1) * state.pageSize + 1;
        const end = Math.min(state.total, state.page * state.pageSize);
        els.pagination.innerHTML = '';
        const info = document.createElement('div');
        info.className = 'pagination-info';
        info.textContent = `Showing ${start} to ${end} of ${state.total}`;

        const container = document.createElement('div');
        container.className = 'pagination-controls';
        const prev = document.createElement('button'); prev.className = 'btn'; prev.textContent = 'Prev'; prev.disabled = state.page <= 1;
        const next = document.createElement('button'); next.className = 'btn'; next.textContent = 'Next'; next.disabled = !state.hasNext;
        prev.addEventListener('click', () => { if (state.page > 1) { state.page -= 1; fetchData(); } });
        next.addEventListener('click', () => { if (state.hasNext) { state.page += 1; fetchData(); } });
        container.appendChild(prev);
        container.appendChild(next);

        els.pagination.appendChild(info);
        els.pagination.appendChild(container);
    }

    function applyFilters() {
        state.page = 1;
        fetchData();
        // Close the options dropdown with animation
        if (els.optionsDropdown) {
            els.optionsDropdown.classList.remove('show');
        }
    }

    function resetFilters() {
        for (const key of ['search', 'status', 'password', 'maxClicks', 'createdAfter', 'createdBefore']) {
            if (els[key]) els[key].value = '';
        }
        if (els.sortBy) els.sortBy.value = 'last_click';
        if (els.order) els.order.value = 'descending';
        // reset segmented visual state
        document.querySelectorAll('.seg').forEach(seg => {
            const targetId = seg.getAttribute('data-target');
            const hidden = document.getElementById(targetId);
            const defaultValue = (targetId === 'f-order') ? 'descending' : '';
            if (hidden) hidden.value = defaultValue;
            seg.setAttribute('data-active', (targetId === 'f-order') ? '0' : '2');
        });
        if (els.pageSize) els.pageSize.value = '20';
        applyFilters();
    }

    // wire events
    els.apply.addEventListener('click', applyFilters);
    els.reset.addEventListener('click', resetFilters);
    els.search.addEventListener('keydown', (e) => { if (e.key === 'Enter') { applyFilters(); } });

    // options dropdown toggle
    function toggleOptions() {
        if (!els.optionsDropdown) return;
        const isOpen = els.optionsDropdown.classList.contains('show');
        if (isOpen) {
            els.optionsDropdown.classList.remove('show');
        } else {
            els.optionsDropdown.classList.add('show');
        }
    }
    if (els.optionsBtn) { els.optionsBtn.addEventListener('click', toggleOptions); }
    window.addEventListener('click', (e) => {
        if (!els.optionsDropdown) return;
        if (e.target === els.optionsBtn || els.optionsBtn.contains(e.target)) { return; }
        if (!els.optionsDropdown.contains(e.target)) { els.optionsDropdown.classList.remove('show'); }
    });

    // segmented controls behavior
    function initSegments() {
        const segs = document.querySelectorAll('.seg');
        segs.forEach(seg => {
            const targetId = seg.getAttribute('data-target');
            const hidden = document.getElementById(targetId);
            const buttons = Array.from(seg.querySelectorAll('button[data-value]'));
            const indexByValue = new Map(buttons.map((b, i) => [b.getAttribute('data-value'), i]));
            function apply(value) {
                if (hidden) { hidden.value = value; }
                const idx = indexByValue.has(value) ? indexByValue.get(value) : 0;
                seg.setAttribute('data-active', String(idx));
            }
            apply(hidden ? hidden.value : '');
            buttons.forEach(btn => btn.addEventListener('click', () => apply(btn.getAttribute('data-value') || '')));
        });
    }

    initSegments();

    // Expose fetchData globally for other components to refresh the list
    window.fetchData = fetchData;

    // initial load
    fetchData();
})();


