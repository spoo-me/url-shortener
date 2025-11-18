// V2 Announcement Modal
class V2Announcement {
    constructor() {
        this.currentStep = 1;
        this.totalSteps = 7; // Welcome + 5 features + API + CTA (removed Performance slide)
        this.modalShown = false;
        this.autoShowDelay = 30000; // 30 seconds
        this.autoAdvanceInterval = 15000; // 15 seconds per slide
        this.slideTimer = null;
        this.prefersReducedMotion = (typeof window !== 'undefined' && window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) || false;
        this.confettiPromise = null;
        this.confettiInstance = null;
        this.preloadedPreviewImages = new Set();
        this.init();
    }

    init() {
        // Check if user has already seen the announcement
        if (localStorage.getItem('v2_announcement_seen') === 'true') {
            return;
        }

        // Show badge
        this.showBadge();

        // Auto-show modal after delay
        setTimeout(() => {
            if (!this.modalShown) {
                this.openModal();
            }
        }, this.autoShowDelay);

        // Setup event listeners
        this.setupEventListeners();
        // Setup preview tooltips
        this.setupPreviewTooltips();
    }

    showBadge() {
        const badge = document.getElementById('v2-badge');
        if (badge) {
            badge.style.display = 'flex';
        }
    }

    setupEventListeners() {
        // Badge click
        const badge = document.getElementById('v2-badge');
        if (badge) {
            badge.addEventListener('click', () => this.openModal());
        }

        // Overlay click
        const overlay = document.getElementById('v2-modal-overlay');
        if (overlay) {
            overlay.addEventListener('click', (e) => {
                if (e.target === overlay) {
                    this.closeModal();
                }
            });
        }

        // Keyboard navigation
        document.addEventListener('keydown', (e) => {
            if (!this.modalShown) return;
            
            if (e.key === 'Escape') {
                this.closeModal();
            } else if (e.key === 'ArrowRight') {
                this.nextStep();
            } else if (e.key === 'ArrowLeft') {
                this.prevStep();
            }
        });

        // Navigation buttons
        const nextBtns = document.querySelectorAll('.v2-next-btn');
        nextBtns.forEach(btn => {
            btn.addEventListener('click', () => this.nextStep());
        });

        const prevBtns = document.querySelectorAll('.v2-prev-btn');
        prevBtns.forEach(btn => {
            btn.addEventListener('click', () => this.prevStep());
        });

        // Progress dots
        const dots = document.querySelectorAll('.v2-progress-dot');
        dots.forEach((dot, index) => {
            dot.addEventListener('click', () => this.showStep(index + 1));
        });

        // Continue as guest
        const guestBtn = document.getElementById('v2-guest-btn');
        if (guestBtn) {
            guestBtn.addEventListener('click', () => this.closeModal());
        }

        // Login button
        const loginBtn = document.getElementById('v2-login-btn');
        if (loginBtn) {
            loginBtn.addEventListener('click', () => {
                this.closeModal();
                // Trigger your existing login modal
                setTimeout(() => {
                    const authBtn = document.querySelector('[onclick="openAuthModal(\'login\')"]');
                    if (authBtn) {
                        authBtn.click();
                    } else {
                        // Fallback: try to call the function directly
                        if (typeof openAuthModal === 'function') {
                            openAuthModal('login');
                        }
                    }
                }, 300);
            });
        }
    }

    openModal() {
        if (this.modalShown) return;
        
        this.modalShown = true;
        const overlay = document.getElementById('v2-modal-overlay');
        if (overlay) {
            overlay.classList.add('active');
            document.body.style.overflow = 'hidden';
            
            // Show first step
            this.showStep(1);
            // Preload preview images used in feature tooltips
            this.preloadPreviewImages();
            // start auto-advance timer and progress animation
            this.startSlideTimer();
            
            // Trigger confetti after a short delay
            setTimeout(() => {
                this.fireConfetti();
            }, 400);
        }
    }

    preloadPreviewImages() {
        if (this.prefersReducedMotion) return;

        const items = document.querySelectorAll('.v2-feature-highlight-item[data-preview-url], .v2-preview-tooltip[data-preview-url]');
        items.forEach((el) => {
            const url = el.getAttribute('data-preview-url');
            if (!url || this.preloadedPreviewImages.has(url)) return;

            const img = new Image();
            img.src = url;
            this.preloadedPreviewImages.add(url);
        });
    }

    setupPreviewTooltips() {
        // don't run on touch devices
        if ('ontouchstart' in window) return;

        // create or reuse a single global tooltip element appended to body
        let globalTooltip = document.querySelector('.v2-preview-tooltip-global');
        if (!globalTooltip) {
            globalTooltip = document.createElement('div');
            globalTooltip.className = 'v2-preview-tooltip-global';
            document.body.appendChild(globalTooltip);
        }

        const bullets = document.querySelectorAll('.v2-feature-highlight-item');
        bullets.forEach(item => {
            const url = item.getAttribute('data-preview-url');
            if (!url) return;

            item.addEventListener('mouseenter', (e) => {
                // only show when this slide is active
                const slide = item.closest('.v2-modal-content');
                if (!slide || !slide.classList.contains('active')) return;

                // set image
                globalTooltip.style.backgroundImage = `url('${url}')`;

                // position tooltip near the bullet
                const rect = item.getBoundingClientRect();
                const tooltipW = 320; // matches CSS
                const tooltipH = 190;

                // position above the bullet and biased to the right (top-right)
                let top = Math.round(rect.top - tooltipH - 12);
                // bias the tooltip to the right side of the bullet (so its left edge sits near the bullet's right)
                let left = Math.round(rect.right - Math.round(tooltipW * 0.15));

                // clamp into viewport (prefer to shift left if overflowing right)
                const padding = 12;
                const vw = Math.max(document.documentElement.clientWidth || 0, window.innerWidth || 0);
                if (left + tooltipW + padding > vw) {
                    left = vw - tooltipW - padding;
                }
                if (left < padding) left = padding;

                // clamp top into viewport (if not enough room above, place below the bullet)
                const vh = Math.max(document.documentElement.clientHeight || 0, window.innerHeight || 0);
                if (top < padding) {
                    // fallback: place below the bullet
                    top = rect.bottom + 12;
                    if (top + tooltipH + padding > vh) top = Math.max(padding, vh - tooltipH - padding);
                }

                globalTooltip.style.left = `${Math.round(left)}px`;
                globalTooltip.style.top = `${Math.round(top)}px`;

                // show with animation
                globalTooltip.classList.add('visible');
            });

            item.addEventListener('mouseleave', () => {
                globalTooltip.classList.remove('visible');
            });
        });
    }

    /* Slide auto-advance timer and progress animation */
    startSlideTimer() {
        if (this.prefersReducedMotion) return;
        this.clearSlideTimer();
        // start visual progress on active dot
        this.animateProgressForDot(this.currentStep);

        // don't auto-advance if we're already on the last step
        if (this.currentStep >= this.totalSteps) {
            return;
        }

        // start a timer to advance slides
        this.slideTimer = setTimeout(() => {
            if (this.modalShown) {
                this.nextStep();
                this.startSlideTimer();
            }
        }, this.autoAdvanceInterval);
    }

    clearSlideTimer() {
        if (this.slideTimer) {
            clearTimeout(this.slideTimer);
            this.slideTimer = null;
        }
        // remove any progress-fill elements
        const fills = document.querySelectorAll('.v2-progress-fill');
        fills.forEach(f => f.remove());
    }

    restartSlideTimer() {
        this.clearSlideTimer();
        if (this.modalShown && !this.prefersReducedMotion) {
            // small delay to allow UI updates before starting animation
            setTimeout(() => this.startSlideTimer(), 80);
        }
    }

    animateProgressForDot(stepNumber) {
        if (this.prefersReducedMotion) return;
        const dots = document.querySelectorAll('.v2-progress-dot');
        dots.forEach((dot, idx) => {
            // ensure relative positioning for fill
            dot.style.position = 'relative';
            // remove existing fill
            const existing = dot.querySelector('.v2-progress-fill');
            if (existing) existing.remove();
            // only add fill to active dot
            if (idx + 1 === stepNumber) {
                const fill = document.createElement('span');
                fill.className = 'v2-progress-fill';
                // initial styles
                fill.style.position = 'absolute';
                fill.style.left = '0';
                fill.style.top = '0';
                fill.style.height = '100%';
                fill.style.width = '0%';
                fill.style.borderRadius = '999px';
                fill.style.background = 'linear-gradient(90deg, rgba(124,58,237,0.9), rgba(99,102,241,0.9))';
                fill.style.zIndex = '0';
                fill.style.transition = `width ${this.autoAdvanceInterval}ms linear`;
                dot.appendChild(fill);
                // force layout then animate to full width
                // expand to match the dot's computed width
                requestAnimationFrame(() => {
                    // ensure the dot has been sized (active dot may be wider)
                    const targetW = dot.clientWidth + 'px';
                    // use percentage to fill entire dot
                    fill.style.width = '100%';
                });
            }
        });
    }

    closeModal() {
        const overlay = document.getElementById('v2-modal-overlay');
        if (overlay) {
            overlay.classList.remove('active');
            document.body.style.overflow = '';
            
            // Mark as seen
            localStorage.setItem('v2_announcement_seen', 'true');
            
            // Hide badge
            const badge = document.getElementById('v2-badge');
            if (badge) {
                badge.style.display = 'none';
            }
        }
        this.modalShown = false;
        // clear timers and progress
        this.clearSlideTimer();
    }

    showStep(stepNumber) {
        // Validate step number
        if (stepNumber < 1 || stepNumber > this.totalSteps) return;

        // Hide all steps
        const allSteps = document.querySelectorAll('.v2-modal-content');
        allSteps.forEach(step => step.classList.remove('active'));

        // Show current step
        const currentStepEl = document.getElementById(`v2-step-${stepNumber}`);
        if (currentStepEl) {
            currentStepEl.classList.add('active');
        }

        // Update progress dots
        this.updateProgressDots(stepNumber);

        this.currentStep = stepNumber;
        // restart auto-advance timer and progress animation when step changes
        this.restartSlideTimer();
    }

    updateProgressDots(activeStep) {
        const dots = document.querySelectorAll('.v2-progress-dot');
        dots.forEach((dot, index) => {
            if (index + 1 === activeStep) {
                dot.classList.add('active');
                // ensure active dot has progress animation started
                this.animateProgressForDot(activeStep);
            } else {
                dot.classList.remove('active');
            }
        });
    }

    nextStep() {
        if (this.currentStep < this.totalSteps) {
            this.showStep(this.currentStep + 1);
        }
    }

    prevStep() {
        if (this.currentStep > 1) {
            this.showStep(this.currentStep - 1);
        }
    }

    fireConfetti() {
        const runSequence = () => {
            const confettiInstance = this.getConfettiInstance();
            if (!confettiInstance) {
                console.warn('[V2Announcement] Confetti instance missing even though library is present');
                return;
            }

            const count = 200;
            const defaults = {
                origin: { y: 0.7 }
            };

            const fire = (particleRatio, opts) => {
                confettiInstance({
                    ...defaults,
                    ...opts,
                    particleCount: Math.floor(count * particleRatio)
                });
            };

            fire(0.25, {
                spread: 26,
                startVelocity: 55,
            });
            
            setTimeout(() => {
                fire(0.2, {
                    spread: 60,
                });
            }, 100);
            
            setTimeout(() => {
                fire(0.35, {
                    spread: 100,
                    decay: 0.91,
                    scalar: 0.8
                });
            }, 200);
            
            setTimeout(() => {
                fire(0.1, {
                    spread: 120,
                    startVelocity: 25,
                    decay: 0.92,
                    scalar: 1.2
                });
            }, 300);
            
            setTimeout(() => {
                fire(0.1, {
                    spread: 120,
                    startVelocity: 45,
                });
            }, 400);
        };

        const ensureConfetti = () => {
            if (typeof confetti !== 'undefined') {
                return Promise.resolve();
            }

            if (this.confettiPromise) {
                return this.confettiPromise;
            }

            this.confettiPromise = new Promise((resolve, reject) => {
                const existingScript = document.querySelector('script[src*="canvas-confetti"]');

                if (existingScript) {
                    existingScript.addEventListener('load', () => resolve());
                    existingScript.addEventListener('error', () => reject(new Error('Failed to load confetti script')));
                    return;
                }

                const script = document.createElement('script');
                script.src = 'https://cdn.jsdelivr.net/npm/canvas-confetti@1.9.4/dist/confetti.browser.min.js';
                script.async = true;
                script.addEventListener('load', () => resolve());
                script.addEventListener('error', () => reject(new Error('Failed to load confetti script')));
                document.head.appendChild(script);
            });

            return this.confettiPromise;
        };

        ensureConfetti()
            .then(runSequence)
            .catch((err) => {
                console.warn('[V2Announcement] Confetti library not loaded', err);
                this.confettiPromise = null;
            });
    }

    getConfettiInstance() {
        if (this.confettiInstance) {
            return this.confettiInstance;
        }

        if (typeof confetti === 'undefined') {
            return null;
        }

        let canvas = document.getElementById('v2-confetti-canvas');
        if (!canvas) {
            canvas = document.createElement('canvas');
            canvas.id = 'v2-confetti-canvas';
            canvas.style.position = 'fixed';
            canvas.style.top = '0';
            canvas.style.left = '0';
            canvas.style.width = '100%';
            canvas.style.height = '100%';
            canvas.style.pointerEvents = 'none';
            canvas.style.zIndex = '1000000';
            canvas.style.inset = '0';
            document.body.appendChild(canvas);
        }

        this.confettiInstance = confetti.create(canvas, {
            resize: true,
            useWorker: true
        });

        return this.confettiInstance;
    }
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        new V2Announcement();
    });
} else {
    new V2Announcement();
}
