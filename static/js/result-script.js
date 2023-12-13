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

function generateQRCode() {
    const shortUrl = document.getElementById('short-url').textContent;
    const qrCodeContainer = document.getElementById('qr-code-container');
    qrCodeContainer.innerHTML = ''; // Clear previous QR code, if any

    const qrcode = new QRCode(qrCodeContainer, {
        text: shortUrl,
        width: 200,
        height: 200,
        correctLevel: QRCode.CorrectLevel.H,
        colorDark: "#000000",
        colorLight: "#ffffff"
    });
}

function downloadQRCode() {
    const qrCodeContainer = document.getElementById('qr-code-container');
    const qrCodeImage = qrCodeContainer.querySelector('canvas');

    qrCodeImage.toBlob(function (blob) {
        const url = URL.createObjectURL(blob);
        const downloadLink = document.createElement('a');
        downloadLink.href = url;
        downloadLink.download = 'qr_code.png';
        downloadLink.click();
        URL.revokeObjectURL(url);
    });
}

function shortenAnotherLink() {
    window.location.href = "/";
}