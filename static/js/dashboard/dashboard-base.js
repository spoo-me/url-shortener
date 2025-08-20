// Dashboard Base JavaScript
document.addEventListener('DOMContentLoaded', function () {
    // Sidebar toggle functionality
    const sidebar = document.getElementById('sidebar');
    const sidebarToggle = document.getElementById('sidebarToggle');
    const profileButton = document.getElementById('profileButton');
    const profileMenu = document.getElementById('profileMenu');

    // Load sidebar state from localStorage
    const sidebarState = localStorage.getItem('sidebarCollapsed');
    if (sidebarState === 'true') {
        sidebar.classList.add('collapsed');
    }

    // Toggle sidebar
    sidebarToggle?.addEventListener('click', function () {
        sidebar.classList.toggle('collapsed');
        const isCollapsed = sidebar.classList.contains('collapsed');
        localStorage.setItem('sidebarCollapsed', isCollapsed);

        // Update toggle icon
        const icon = sidebarToggle.querySelector('i');
        if (icon) {
            if (isCollapsed) {
                icon.className = 'ti ti-layout-sidebar-left-expand';
            } else {
                icon.className = 'ti ti-layout-sidebar-right-expand';
            }
        }

        // Close profile menu when collapsing
        if (isCollapsed && profileMenu) {
            profileMenu.classList.remove('active');
            profileButton.classList.remove('active');
        }
    });

    // Profile dropdown functionality
    profileButton?.addEventListener('click', function (e) {
        e.stopPropagation();
        profileMenu.classList.toggle('active');
        profileButton.classList.toggle('active');
    });

    // Close profile menu when clicking outside
    document.addEventListener('click', function (e) {
        if (profileMenu && !profileMenu.contains(e.target) && !profileButton.contains(e.target)) {
            profileMenu.classList.remove('active');
            profileButton.classList.remove('active');
        }
    });

    // Prevent menu from closing when clicking inside it
    profileMenu?.addEventListener('click', function (e) {
        e.stopPropagation();
    });

    // Mobile sidebar handling
    if (window.innerWidth <= 768) {
        sidebar.classList.add('mobile');

        // Add overlay for mobile
        const overlay = document.createElement('div');
        overlay.className = 'sidebar-overlay';
        document.body.appendChild(overlay);

        sidebarToggle?.addEventListener('click', function () {
            sidebar.classList.toggle('mobile-open');
            overlay.classList.toggle('active');
        });

        overlay.addEventListener('click', function () {
            sidebar.classList.remove('mobile-open');
            overlay.classList.remove('active');
        });
    }

    // Handle active navigation items
    const currentPath = window.location.pathname;
    const navItems = document.querySelectorAll('.nav-item');

    navItems.forEach(item => {
        const href = item.getAttribute('href');
        if (href === currentPath) {
            item.classList.add('active');
        }
    });

    // Add keyboard shortcuts
    document.addEventListener('keydown', function (e) {
        // Alt + S to toggle sidebar
        if (e.altKey && e.key === 's') {
            e.preventDefault();
            sidebarToggle?.click();
        }

        // Escape to close profile menu
        if (e.key === 'Escape' && profileMenu?.classList.contains('active')) {
            profileMenu.classList.remove('active');
            profileButton.classList.remove('active');
        }
    });

    // Handle sidebar resize on window resize
    let resizeTimer;
    window.addEventListener('resize', function () {
        clearTimeout(resizeTimer);
        resizeTimer = setTimeout(function () {
            if (window.innerWidth <= 768) {
                if (!sidebar.classList.contains('mobile')) {
                    sidebar.classList.add('mobile');
                    sidebar.classList.remove('collapsed');

                    // Add overlay if not exists
                    if (!document.querySelector('.sidebar-overlay')) {
                        const overlay = document.createElement('div');
                        overlay.className = 'sidebar-overlay';
                        document.body.appendChild(overlay);

                        overlay.addEventListener('click', function () {
                            sidebar.classList.remove('mobile-open');
                            overlay.classList.remove('active');
                        });
                    }
                }
            } else {
                sidebar.classList.remove('mobile', 'mobile-open');
                const overlay = document.querySelector('.sidebar-overlay');
                if (overlay) {
                    overlay.remove();
                }

                // Restore collapsed state from localStorage
                const savedState = localStorage.getItem('sidebarCollapsed');
                if (savedState === 'true') {
                    sidebar.classList.add('collapsed');
                }
            }
        }, 250);
    });

    // Initialize Tippy.js tooltips for collapsed sidebar
    let tippyInstances = [];

    function initializeTooltips() {
        // Destroy existing instances
        tippyInstances.forEach(instance => instance.destroy());
        tippyInstances = [];

        // Only create tooltips if sidebar is collapsed
        if (sidebar.classList.contains('collapsed')) {
            const navItems = document.querySelectorAll('.nav-item[data-tooltip]');
            
            navItems.forEach(item => {
                const instance = tippy(item, {
                    content: item.getAttribute('data-tooltip'),
                    placement: 'right',
                    offset: [0, 12],
                    theme: 'dark',
                    animation: 'fade',
                    duration: [200, 150],
                    delay: [300, 0],
                    arrow: true,
                    hideOnClick: false,
                    trigger: 'mouseenter focus',
                    zIndex: 10000,
                    appendTo: 'parent'
                });
                tippyInstances.push(instance);
            });
        }
    }

    // Initialize tooltips on load if collapsed
    initializeTooltips();

    // Reinitialize tooltips when sidebar is toggled
    const originalToggleHandler = sidebarToggle?.onclick;
    sidebarToggle?.addEventListener('click', function() {
        // Wait for the transition to complete
        setTimeout(() => {
            initializeTooltips();
        }, 350); // Slightly longer than CSS transition
    });
});

// Add styles for mobile overlay
const style = document.createElement('style');
style.textContent = `
    .sidebar-overlay {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(0, 0, 0, 0.5);
        opacity: 0;
        visibility: hidden;
        transition: opacity 0.3s, visibility 0.3s;
        z-index: 90;
    }
    
    .sidebar-overlay.active {
        opacity: 1;
        visibility: visible;
    }
    
    @media (max-width: 768px) {
        .dashboard-sidebar.mobile {
            transform: translateX(-100%);
            transition: transform 0.3s ease;
        }
        
        .dashboard-sidebar.mobile.mobile-open {
            transform: translateX(0);
        }
    }
`;
document.head.appendChild(style);
