// Get all elements with the "stats-button" class
const statsButtons = document.querySelectorAll('.stats-button');

// Add click event listener to each stats button
statsButtons.forEach(button => {
    button.addEventListener('click', () => {
        const href = button.parentNode.parentNode.parentNode.querySelector('.short-url a').getAttribute('href');
        const alias = href.replace(/^\//, '');
        window.location.href = `/stats/${alias}`;
    });
});


const copyButtons = document.querySelectorAll('.copy-button');
// Add click event listener to each copy button
copyButtons.forEach(button => {
    button.addEventListener('click', () => {
        // Get the URL from the data-url attribute of the button
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
    });
});
// Get all elements with the "qr-code" class
function renderRecentURLs() {
    const container = document.getElementById('recentURLs');
    if (!container) return;

    let list = [];
    try { list = JSON.parse(localStorage.getItem('recentURLs')) || []; } catch (_) { list = []; }
    container.innerHTML = '';

    list.forEach((alias) => {
        const shortUrl = `${window.location.origin}/${alias}`;

        const wrapper = document.createElement('div');
        wrapper.className = 'url-container';
        wrapper.innerHTML = `
            <div class="section-1">
                <div class="left-section">
                    <span class="short-url">
                        <a href="/${alias}" target="_blank">${shortUrl}</a>
                    </span>
                </div>
                <div class="right-section">
                    <div class="qr-code" data-url="${shortUrl}"></div>
                </div>
            </div>
            <div class="section-2">
                <div class="button-container">
                    <button class="copy-button" data-url="${shortUrl}">Copy</button>
                    <button class="stats-button">Stats</button>
                </div>
            </div>
        `;
        container.appendChild(wrapper);
    });

    // Re-bind copy and stats buttons for newly rendered items
    const copyButtonsDynamic = container.querySelectorAll('.copy-button');
    copyButtonsDynamic.forEach(button => {
        button.addEventListener('click', () => {
            const url = button.getAttribute('data-url');
            const tempInput = document.createElement('input');
            tempInput.value = url;
            document.body.appendChild(tempInput);
            tempInput.select();
            tempInput.setSelectionRange(0, 99999);
            document.execCommand('copy');
            document.body.removeChild(tempInput);
            button.innerText = 'Copied!';
            setTimeout(() => { button.innerText = 'Copy'; }, 1000);
        });
    });

    const statsButtonsDynamic = container.querySelectorAll('.stats-button');
    statsButtonsDynamic.forEach(button => {
        button.addEventListener('click', () => {
            const href = button.parentNode.parentNode.parentNode.querySelector('.short-url a').getAttribute('href');
            const alias = href.replace(/^\//, '');
            window.location.href = `/stats/${alias}`;
        });
    });

    // Generate QR codes for newly rendered items
    const qrCodeElements = container.querySelectorAll('.qr-code');
    qrCodeElements.forEach(element => {
        const url = element.getAttribute('data-url');
        const qrcode = new QRCode(element, {
            text: url,
            width: 40,
            height: 40,
            correctLevel: QRCode.CorrectLevel.L,
            margin: 0,
            colorDark: '#000000',
            colorLight: '#ffffff',
        });
    });
}

document.addEventListener('DOMContentLoaded', renderRecentURLs);