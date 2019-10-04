/* global url_base, notify_error */
window.addEventListener("DOMContentLoaded", function(){
    $log_display = document.querySelector("samp#log_text");
    $select_log = document.querySelector("select#log_file");
});

// Open log file
function view_log(){
    $log_display.style.display = "none";
    var logfile = $select_log.value;

    $.post(url_base + "/ajax/get_log_text", {"logfile": logfile})
    .done(function(r){
        $log_display.innerText = r;
        $log_display.style.display = "block";
    })
    .fail(notify_error);
}

function download_log(){
    var logfile = $select_log.value;
    window.open(url_base + "/settings/download_log/" + logfile, "_blank")
}
