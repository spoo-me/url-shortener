var modal = document.querySelector(".modal");

function showContactModal(){
    modal.style.display = "flex";
}

function closeContactModal(){
    modal.style.display = "none";
}

function openContactLink(link){
    window.open(link, '_blank');
    closeContactModal();
}

modal.addEventListener("click", function (e) {
    const isInsideModalContent = e.target.closest(".modal-content");
    const isInsideButtonContainer = e.target.closest(".button-container");

    if (!isInsideModalContent && !isInsideButtonContainer) {
        closeContactModal();
    }
});
