function toggleDropdown() {
    const dropdown = document.querySelector('.dropdown');
    dropdown.classList.toggle('dropdown-expanded');
}

const inputBox = document.querySelector('#alias');

inputBox.addEventListener('focus', (e) => {
    document.querySelector('.buttonIn').classList.add('focus');
});

inputBox.addEventListener('blur', (e) => {
    document.querySelector('.buttonIn').classList.remove('focus');
});