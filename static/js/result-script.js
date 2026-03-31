function copyShortUrl() {
    const shortUrl = document.getElementById('short-url');
    navigator.clipboard.writeText(shortUrl.textContent)
        .then(() => {
            alert('Short URL copied to clipboard!');
        })
        .catch((error) => {
            console.error('Error copying short URL:', error);
        });
}

function downloadQRCode() {
    var qrcode = document.getElementById("qrcode");
    fetch(qrcode.src, { mode: "cors" })
        .then(function (res) { return res.blob(); })
        .then(function (blob) {
            var link = document.createElement("a");
            link.href = URL.createObjectURL(blob);
            link.download = "qrcode.png";
            link.click();
            URL.revokeObjectURL(link.href);
        });
}

function shortenAnotherLink() {
    window.location.href = "/";
}

var qrcode = document.getElementById("qrcode");

qrcode.onload = function () {

    var qrcodeContainer = document.getElementById("qr-code-container");
    qrcodeContainer.style.animation = "none";

    qrcodeContainer.addEventListener("mouseenter", function () {
        qrcodeContainer.style.cursor = "pointer";
        var qrcodeOverlay = document.getElementById("qrcode-overlay");
        qrcodeOverlay.style.display = "flex";
    });

    qrcodeContainer.addEventListener("mouseleave", function () {
        const qrcodeOverlay = document.getElementById("qrcode-overlay");
        qrcodeOverlay.style.display = "none";
    });

    qrcodeContainer.addEventListener("click", function () {
        downloadQRCode();
    });

};

var copyButton = document.querySelector(".copy-button");

copyButton.addEventListener("click", function () {
    copyShortUrl();
});

// ── Manage Token (anonymous URL claim) ────────────────────────────────────

(function initManageTokenBanner() {
    // Extract short code from current URL: /result/<alias>
    const alias = window.location.pathname.split('/').pop();
    if (!alias) return;

    let token = null;
    try {
        const list = JSON.parse(localStorage.getItem('recentURLs')) || [];
        const entry = list.find(item => typeof item === 'object' && item.alias === alias);
        token = entry ? entry.manage_token : null;
    } catch (_) { token = null; }
    if (!token) return;

    // Show the banner and populate it
    const banner = document.getElementById('claim-token-banner');
    const valueEl = document.getElementById('claim-token-value');
    if (!banner || !valueEl) return;

    valueEl.textContent = token;
    banner.style.display = 'flex';
})();

function copyManageToken() {
    const valueEl = document.getElementById('claim-token-value');
    if (!valueEl) return;
    navigator.clipboard.writeText(valueEl.textContent.trim()).then(() => {
        const btn = document.getElementById('claim-token-copy-btn');
        if (btn) { btn.textContent = 'Copied!'; setTimeout(() => { btn.textContent = 'Copy'; }, 2000); }
    }).catch(console.error);
}

async function claimNow() {
    // Redirect to home with a flag so the auth modal opens.
    // sweepAndClaimTokens() in auth.js handles the actual claim after login.
    const alias = window.location.pathname.split('/').pop();
    if (alias) {
        // Store current result page so we can redirect back after login
        sessionStorage.setItem('spoo_claim_redirect', window.location.href);
    }
    if (typeof openAuthModal === 'function') {
        openAuthModal();
    } else {
        window.location.href = '/';
    }
}