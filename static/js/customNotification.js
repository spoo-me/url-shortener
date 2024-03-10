function createNotification(id) {
    var notification = document.createElement("div");
    notification.classList.add("custom-top-notification");
    notification.id = id;
    notification.innerHTML = '<span class="closebtn" onclick="this.parentElement.style.display=\'none\';">&times;</span><p>This is a custom top notification</p><div class="close-progress-bar"></div>';
    document.body.appendChild(notification);
}

function customTopNotification(Id, text, time) {
    var element = document.getElementById("customNotification"+Id);
    if (element) {
        element.remove();
    }

    createNotification("customNotification"+Id);

    var newNotification = document.getElementById("customNotification"+Id);
    newNotification.getElementsByTagName("p")[0].innerHTML = text;
    newNotification.style.display = "block";

    var progressbar = newNotification.getElementsByClassName("close-progress-bar")[0];
    var animation = "progress-bar-animation " + time + "s linear";
    progressbar.style.animation = animation;

    setTimeout(function () {
        newNotification.remove();
    }, time * 1000 - 200);
}