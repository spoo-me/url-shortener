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

// Profile dropdown toggles
document.addEventListener('DOMContentLoaded', function(){
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