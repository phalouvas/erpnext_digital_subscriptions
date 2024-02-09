$(document).ready(function() {
    $('.file-button[href="#"]').each(function() {
        $(this).click(function(event) {
            event.preventDefault();
            let file_url = "/api/method/digital_subscriptions.digital_subscriptions.doctype.file_version.file_version.download?subscription=" + $(this).data('subscription') + "&version=" + $(this).data('version');            
            window.open(file_url);            
        });
    });
});