function toggleDropdown() {
    const dropdown = document.querySelector('.dropdown');
    dropdown.classList.toggle('dropdown-expanded');
}

const inputBox = document.querySelector('#alias');

// Track if the alias notification has been shown
let aliasNotificationShown = false;

inputBox.addEventListener('focus', (e) => {
    document.querySelector('.buttonIn').classList.add('focus');
});

inputBox.addEventListener('blur', (e) => {
    document.querySelector('.buttonIn').classList.remove('focus');
});

inputBox.addEventListener('click', (e) => {
    // Show the notification about 16-character limit only once per session
    if (!aliasNotificationShown) {
        customTopNotification("AliasUpdate", "✨ <b>New:</b> Custom aliases can now be up to <b>16 characters</b> long!", 10, "success");
        aliasNotificationShown = true;
    }
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