function validatePassword() {
    var password = document.getElementById("password").value;
    if (password.trim() === "") {
        // Password field is empty, skip validation
        document.getElementById("password-error").innerText = "";
        document.getElementById("password-error").style.background = ""
        document.getElementById("password-error").style.marginTop = "-25px"
        return true;
    }
    var passwordRegex = /^(?=.*[A-Za-z])(?=.*\d)(?=.*[@.])[A-Za-z\d@.]{8,}$/;
    if (!passwordRegex.test(password)) {
        document.getElementById("password-error").innerText = "Password must be at least 8 characters long and contain an alphabet, a number, a special character '@' or '.'";
        document.getElementById("password-error").style.background = "rgba(255, 255, 255, 0.15)"
        document.getElementById("password-error").style.marginTop = "0px"
        setTimeout(function () {
            document.getElementById("password-error").innerText = "";
            document.getElementById("password-error").style.background = "";
            document.getElementById("password-error").style.marginTop = "-25px";
        }, 3000);
        return false;
    }
    else {
        document.getElementById("password-error").innerText = "";
        document.getElementById("password-error").style.background = ""
        document.getElementById("password-error").style.marginTop = "-25px"
        return true;
    }
}
function validateURL() {
    var url = document.getElementById("long-url").value;
    var urlRegex = /^(ftp|http|https):\/\/[^ "]+$/;

    if (!urlRegex.test(url) || url.includes('spoo.me')) {
        document.getElementById("url-error").innerText = "Please Enter a Valid URL";
        document.getElementById("url-error").style.background = "rgba(255, 255, 255, 0.15)"
        document.getElementById("url-error").style.marginTop = "-15px"
        setTimeout(function () {
            document.getElementById("url-error").innerText = "";
            document.getElementById("url-error").style.background = "";
            document.getElementById("url-error").style.marginTop = "-30px";
        }, 3000);
        return false;
    } else {
        document.getElementById("url-error").innerText = "";
        document.getElementById("url-error").style.background = ""
        document.getElementById("url-error").style.marginTop = "-30px"
        return true;
    }
}

function removeErrorMessage() {
    var aliasError = document.getElementById("alias-error");

    if (aliasError) {
        setTimeout(function () {
            aliasError.remove();
        }, 3000);
    }
}
