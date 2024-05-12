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

function get_metrics() {
    fetch('/metric')
        .then(response => response.json())
        .then(data => {
            document.querySelector('#total-urls').textContent = data["total-shortlinks"];
            document.querySelector('#total-clicks').textContent = data["total-clicks"];
        });

    fetch('https://discord.com/api/guilds/1192388005206433892/widget.json')
        .then(response => response.json())
        .then(data => {
            document.querySelector('#discord-online').textContent = data["presence_count"]+"+";
        });

    fetch('https://api.github.com/repos/spoo-me/url-shortener')
        .then(response => response.json())
        .then(data => {
            document.querySelector('#github-stars').textContent = data["stargazers_count"];
        });
}

document.onload = get_metrics();
setInterval(get_metrics, 60000);