function removeErrorMessage() {
    var passError = document.getElementById("password-error");

    if (passError) {
        setTimeout(function () {
            passError.remove();
        }, 3000);
    }
}
