const closeButton = document.querySelector('.self-promo-close');

if (closeButton) {
    closeButton.addEventListener('click', closeSelfPromo);
}

function closeSelfPromo() {
    const promo = document.querySelector('.self-promo');
    if (promo) {
        promo.classList.add('hidden');
    }
}