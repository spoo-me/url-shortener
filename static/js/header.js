window.addEventListener('scroll', function() {
    var navbar = document.querySelector('.navbar');
    var mobileNavbar = document.querySelector('.mobile-navbar');
    if (window.pageYOffset > 30) {
        navbar.classList.add('scrolled');
        mobileNavbar.classList.add('scrolled');
    } else {
        navbar.classList.remove('scrolled');
        mobileNavbar.classList.remove('scrolled');
    }
});

// Fetch GitHub stars
async function fetchGitHubStars() {
    try {
        const response = await fetch('https://api.github.com/repos/spoo-me/url-shortener');
        if (response.ok) {
            const data = await response.json();
            const stars = data.stargazers_count;
            const formatted = stars >= 1000 ? (stars / 1000).toFixed(1) + 'k' : stars;
            document.getElementById('github-star-count').textContent = formatted;
        }
    } catch (error) {
        console.log('GitHub API unavailable, using fallback');
    }
}

// Mobile menu toggle
function setupMobileMenu() {
    const burger = document.querySelector('.burger');
    const mobileNavbar = document.querySelector('.mobile-navbar');
    const menu = document.querySelector('.mobile-menu');
    
    if (burger && menu && mobileNavbar) {
        burger.addEventListener('click', function(e) {
            e.stopPropagation();
            const isExpanded = burger.getAttribute('aria-expanded') === 'true';
            burger.setAttribute('aria-expanded', String(!isExpanded));
            
            // Toggle class on navbar to control menu visibility
            if (!isExpanded) {
                mobileNavbar.classList.add('menu-open');
            } else {
                mobileNavbar.classList.remove('menu-open');
            }
        });
        
        // Close menu when clicking outside
        document.addEventListener('click', function(e) {
            if (!burger.contains(e.target) && !menu.contains(e.target)) {
                burger.setAttribute('aria-expanded', 'false');
                mobileNavbar.classList.remove('menu-open');
            }
        });
        
        // Close menu when clicking a link
        menu.querySelectorAll('a').forEach(link => {
            link.addEventListener('click', function() {
                burger.setAttribute('aria-expanded', 'false');
                mobileNavbar.classList.remove('menu-open');
            });
        });
    }
}

// Profile dropdown toggles
document.addEventListener('DOMContentLoaded', function(){
    fetchGitHubStars();
    setupMobileMenu();
    
    function setupProfileMenu(buttonId, dropdownId){
        var btn = document.getElementById(buttonId);
        var dd = document.getElementById(dropdownId);
        if(!btn || !dd) return;
        function toggle(){
            var open = dd.style.display === 'block';
            dd.style.display = open ? 'none' : 'block';
            btn.setAttribute('aria-expanded', String(!open));
        }
        btn.addEventListener('click', function(e){ e.stopPropagation(); toggle(); });
        document.addEventListener('click', function(e){
            if(dd.contains(e.target) || btn.contains(e.target)) return;
            dd.style.display = 'none';
            btn.setAttribute('aria-expanded','false');
        });
    }
    setupProfileMenu('profileButton','profileDropdown');
    setupProfileMenu('mProfileButton','mProfileDropdown');
});