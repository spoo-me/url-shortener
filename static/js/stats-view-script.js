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

function downloadQRCode() {
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
            qrcode.style.animation = "none";
        };
        reader.readAsDataURL(xhr.response);
    };
    xhr.open("GET", qrCodeSrc);
    xhr.send();
}
