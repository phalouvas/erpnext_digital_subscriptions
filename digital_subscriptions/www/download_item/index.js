$(document).ready(function() {
    $('.file-button[href="#"]').each(function() {
        $(this).click(function(event) {
            event.preventDefault();
            let file_url = "/download_file?subscription=" + $(this).data('subscription') + "&version=" + $(this).data('version');            
            window.open(file_url);            
        });
    });
});