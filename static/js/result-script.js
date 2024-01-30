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
    var qrCodeSrc = qrcode.src;

    var link = document.createElement("a");

    var xhr = new XMLHttpRequest();
    xhr.responseType = "blob";
    xhr.onload = function () {
        var reader = new FileReader();
        reader.onloadend = function () {
            link.href = reader.result;  // Use the result from the FileReader
            link.download = "qrcode.png";
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);  // Clean up the link element
        };
        reader.readAsDataURL(xhr.response);
    };
    xhr.open("GET", qrCodeSrc);
    xhr.send();
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