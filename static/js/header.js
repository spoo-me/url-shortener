window.addEventListener('scroll', function() {
    console.log(window.pageYOffset);
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