// Reusable handler for copy button clicks
function handleCopyClick(button) {
    const url = button.getAttribute('data-url');

    // Create a temporary input element to copy the URL
    const tempInput = document.createElement('input');
    tempInput.value = url;
    document.body.appendChild(tempInput);

    // Select the URL in the input element
    tempInput.select();
    tempInput.setSelectionRange(0, 99999); // For mobile devices

    // Copy the URL to the clipboard
    document.execCommand('copy');

    // Remove the temporary input element
    document.body.removeChild(tempInput);

    // Provide visual feedback to indicate successful copying
    button.innerText = 'Copied!';
    setTimeout(() => {
        button.innerText = 'Copy';
    }, 1000);
}

// Reusable handler for stats button clicks
function handleStatsClick(button) {
    const href = button.parentNode.parentNode.parentNode.querySelector('.short-url a').getAttribute('href');
    const alias = href.replace(/^\//, '');
    window.location.href = `/stats/${alias}`;
}

// Handler for edit button clicks
function handleEditClick(button) {
    const alias = button.getAttribute('data-alias');
    if (typeof openLandingEditModal === 'function') {
        openLandingEditModal(alias);
    }
}

// Single document-level event delegation for copy, stats, and edit buttons
document.addEventListener('click', (e) => {
    // Handle copy button clicks
    if (e.target.classList.contains('copy-button')) {
        handleCopyClick(e.target);
    }
    // Handle stats button clicks
    else if (e.target.classList.contains('stats-button')) {
        handleStatsClick(e.target);
    }
    // Handle edit button clicks
    else if (e.target.classList.contains('edit-button')) {
        handleEditClick(e.target);
    }
});

// Render recent URLs without QR codes
function renderRecentURLs() {
    const container = document.getElementById('recentURLs');
    if (!container) return;

    // Don't show recent URLs for signed-up users
    if (window.isLoggedIn === true) {
        container.innerHTML = '';
        return;
    }

    let list = [];
    try { list = JSON.parse(localStorage.getItem('recentURLs')) || []; } catch (_) { list = []; }
    container.innerHTML = '';

    list.forEach((item) => {
        // Support both old string format and new object format
        const alias = typeof item === 'string' ? item : item.alias;
        const hasToken = typeof item === 'object' && item.manage_token;
        const shortUrl = `${window.location.origin}/${alias}`;

        const wrapper = document.createElement('div');
        wrapper.className = 'url-container';

        // Section 1
        const section1 = document.createElement('div');
        section1.className = 'section-1';

        const leftSection = document.createElement('div');
        leftSection.className = 'left-section';

        const shortUrlSpan = document.createElement('span');
        shortUrlSpan.className = 'short-url';

        const link = document.createElement('a');
        link.href = `/${alias}`;
        link.target = '_blank';
        link.textContent = shortUrl.replace(/^https?:\/\//, '');

        shortUrlSpan.appendChild(link);
        leftSection.appendChild(shortUrlSpan);

        if (hasToken) {
            const badge = document.createElement('span');
            badge.className = 'unclaimed-badge';
            badge.textContent = 'Unclaimed';
            leftSection.appendChild(badge);
        }

        section1.appendChild(leftSection);

        // Section 2
        const section2 = document.createElement('div');
        section2.className = 'section-2';

        const buttonContainer = document.createElement('div');
        buttonContainer.className = 'button-container';

        const copyBtn = document.createElement('button');
        copyBtn.className = 'copy-button';
        copyBtn.setAttribute('data-url', shortUrl);
        copyBtn.textContent = 'Copy';

        const editBtn = document.createElement('button');
        editBtn.className = 'edit-button';
        editBtn.setAttribute('data-alias', alias);
        editBtn.textContent = 'Edit';

        const statsBtn = document.createElement('button');
        statsBtn.className = 'stats-button';
        statsBtn.textContent = 'Stats';

        buttonContainer.appendChild(copyBtn);
        buttonContainer.appendChild(editBtn);
        buttonContainer.appendChild(statsBtn);
        section2.appendChild(buttonContainer);

        wrapper.appendChild(section1);
        wrapper.appendChild(section2);
        container.appendChild(wrapper);
    });

    // Show Claim All button if there are unclaimed URLs
    const hasUnclaimed = list.some(item => typeof item === 'object' && item.manage_token);
    if (hasUnclaimed) {
        const claimAllWrapper = document.createElement('div');
        claimAllWrapper.id = 'claim-all-wrapper';

        const claimAllBtn = document.createElement('button');
        claimAllBtn.id = 'claim-all-btn';
        claimAllBtn.onclick = claimAllAnonymousURLs;
        claimAllBtn.textContent = 'Sign in to claim all your links';

        claimAllWrapper.appendChild(claimAllBtn);
        container.appendChild(claimAllWrapper);
    }
}

document.addEventListener('DOMContentLoaded', renderRecentURLs);

// Re-render when authentication state changes
document.addEventListener('auth:init', renderRecentURLs);

function claimAllAnonymousURLs() {
    sessionStorage.setItem('spoo_claim_redirect', window.location.href);
    if (typeof openAuthModal === 'function') {
        openAuthModal();
    } else {
        window.location.href = '/';
    }
}