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

// Handle form submission via API v1
document.addEventListener('DOMContentLoaded', () => {
    const form = document.querySelector('.form-section form');
    if (!form) return;

    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        if (typeof validateURL === 'function' && !validateURL()) {
            return;
        }
        if (typeof validatePassword === 'function' && !validatePassword()) {
            return;
        }

        const url = document.getElementById('long-url').value.trim();
        const alias = document.getElementById('alias').value.trim();
        const password = document.getElementById('password').value;
        const maxClicksInput = document.getElementById('max-clicks').value;
        const blockBots = document.getElementById('block-bots').checked;

        const payload = {
            long_url: url,
            alias: alias || undefined,
            password: password || undefined,
            max_clicks: maxClicksInput ? parseInt(maxClicksInput, 10) : undefined,
            block_bots: blockBots ? true : undefined,
        };

        const submitBtn = form.querySelector('button[type="submit"]');
        const prevText = submitBtn ? submitBtn.textContent : '';
        if (submitBtn) { submitBtn.disabled = true; submitBtn.textContent = 'Shortening...'; }

        try {
            const res = await authFetch('/api/v1/shorten', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
                body: JSON.stringify(payload)
            });

            const data = await res.json().catch(() => ({}));
            if (!res.ok) {
                const err = data && data.error ? data.error : 'Failed to shorten URL';
                customTopNotification('ShortenError', err, 8, 'error');
                return;
            }

            // Maintain recent URLs in localStorage (latest 3)
            const key = 'recentURLs';
            let list = [];
            try { list = JSON.parse(localStorage.getItem(key)) || []; } catch (_) { list = []; }
            list.unshift(data.alias);
            list = Array.from(new Set(list)).slice(0, 3);
            localStorage.setItem(key, JSON.stringify(list));

            // Navigate to result page
            window.location.href = `/result/${encodeURIComponent(data.alias)}`;
        } catch (err) {
            customTopNotification('NetworkError', 'Network error. Please try again.', 8, 'error');
        } finally {
            if (submitBtn) { submitBtn.disabled = false; submitBtn.textContent = prevText; }
        }
    });
});