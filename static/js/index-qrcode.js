// Get all elements with the "stats-button" class
const statsButtons = document.querySelectorAll('.stats-button');

// Add click event listener to each stats button
statsButtons.forEach(button => {
    button.addEventListener('click', () => {
        // Get the URL from the data-url attribute of the button
        const url = "/stats/" + button.parentNode.parentNode.parentNode.querySelector('.short-url a').getAttribute('href');

        // Redirect the user to the stats URL
        window.location.href = url;
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
const qrCodeElements = document.querySelectorAll('.qr-code');

// Iterate over each QR code element
qrCodeElements.forEach(element => {
    // Get the URL from the data-url attribute
    const url = element.getAttribute('data-url');

    // Generate the QR code using QRCode.js
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