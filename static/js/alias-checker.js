/**
 * Alias availability checker + random generator.
 *
 *   window.AliasChecker.attach({
 *       inputId, diceBtn, indicator, getCurrentAlias?, onValidityChange?,
 *   })
 *   window.AliasChecker.randomAlias()
 *
 * Debounces server hits; resolves client-side length/format first.
 * Uses the shared setFieldError/clearFieldError primitive for error text.
 */
(function () {
    const ALPHABET =
        'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';
    const LENGTH = 7;
    const DEBOUNCE_MS = 300;

    function randomAlias() {
        const rng = window.crypto || window.msCrypto;
        if (rng && rng.getRandomValues) {
            const buf = new Uint32Array(LENGTH);
            rng.getRandomValues(buf);
            let out = '';
            for (let i = 0; i < LENGTH; i++) out += ALPHABET[buf[i] % ALPHABET.length];
            return out;
        }
        let out = '';
        for (let i = 0; i < LENGTH; i++) {
            out += ALPHABET[Math.floor(Math.random() * ALPHABET.length)];
        }
        return out;
    }

    function clientValidate(alias) {
        if (alias.length < 3) return 'Must be at least 3 characters';
        if (alias.length > 16) return 'Must be at most 16 characters';
        if (!/^[a-zA-Z0-9_-]+$/.test(alias)) {
            return 'Only letters, numbers, underscores, and hyphens are allowed';
        }
        return null;
    }

    function reasonToMessage(reason) {
        switch (reason) {
            case 'length':
                return 'Must be 3-16 characters';
            case 'format':
                return 'Only letters, numbers, underscores, and hyphens are allowed';
            case 'taken':
                return 'This alias is already taken';
            default:
                return 'Alias is not available';
        }
    }

    function attach(options) {
        const input = document.getElementById(options.inputId);
        if (!input) return;
        const { diceBtn, indicator, getCurrentAlias, onValidityChange } = options;

        let debounceTimer = null;
        let inFlight = null;

        function setIndicator(state) {
            indicator.classList.remove('show', 'is-checking', 'is-available', 'is-unavailable');
            if (state === 'idle') {
                indicator.innerHTML = '';
                return;
            }
            indicator.classList.add('show');
            if (state === 'loading') {
                indicator.classList.add('is-checking');
                indicator.innerHTML = '<i class="ti ti-loader-2"></i>';
            } else if (state === 'available') {
                indicator.classList.add('is-available');
                indicator.innerHTML = '<i class="ti ti-check"></i>';
            } else {
                indicator.classList.add('is-unavailable');
                indicator.innerHTML = '<i class="ti ti-x"></i>';
            }
        }

        function emit(valid) {
            if (typeof onValidityChange === 'function') onValidityChange(valid);
        }

        function applyResult(alias, valid, message) {
            if (input.value.trim() !== alias) return;
            if (valid) {
                setIndicator('available');
                window.clearFieldError(options.inputId);
                emit(true);
            } else {
                setIndicator('unavailable');
                window.setFieldError(options.inputId, message);
                emit(false);
            }
        }

        function runServerCheck(alias) {
            if (inFlight) inFlight.abort();
            const controller = new AbortController();
            inFlight = controller;
            fetch(
                `/api/v1/shorten/check-alias?alias=${encodeURIComponent(alias)}`,
                { signal: controller.signal, credentials: 'same-origin' },
            )
                .then((r) => r.json())
                .then((data) => {
                    if (data.available) {
                        applyResult(alias, true);
                    } else {
                        applyResult(alias, false, reasonToMessage(data.reason));
                    }
                })
                .catch((err) => {
                    if (err.name === 'AbortError') return;
                    setIndicator('idle');
                });
        }

        input.addEventListener('input', () => {
            if (debounceTimer) clearTimeout(debounceTimer);
            if (inFlight) inFlight.abort();

            const alias = input.value.trim();
            if (!alias) {
                setIndicator('idle');
                window.clearFieldError(options.inputId);
                emit(null);
                return;
            }

            if (typeof getCurrentAlias === 'function' && alias === getCurrentAlias()) {
                setIndicator('idle');
                window.clearFieldError(options.inputId);
                emit(true);
                return;
            }

            const clientError = clientValidate(alias);
            if (clientError) {
                setIndicator('unavailable');
                window.setFieldError(options.inputId, clientError);
                emit(false);
                return;
            }

            setIndicator('loading');
            debounceTimer = setTimeout(() => runServerCheck(alias), DEBOUNCE_MS);
        });

        if (diceBtn) {
            diceBtn.addEventListener('click', (e) => {
                e.preventDefault();
                input.value = randomAlias();
                input.dispatchEvent(new Event('input', { bubbles: true }));
                input.focus();
            });
        }

        function reset() {
            if (debounceTimer) clearTimeout(debounceTimer);
            if (inFlight) inFlight.abort();
            setIndicator('idle');
        }

        return { reset };
    }

    window.AliasChecker = { attach, randomAlias };
})();
