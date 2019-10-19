/* global url_base, notify_error */
$(document).ready(function () {
    document.title = "Watcher - Shutting Down Server";

    var $thinker = document.getElementById("thinker");
    $thinker.style.maxHeight = '100%';

    $.post(url_base + "/ajax/server_status", {
        "mode": "shutdown"
    })
    .fail(notify_error);

    /*
    This repeats every 3 seconds to check if the server is still online.
    */
    var check = setInterval(function(){
        $.post(url_base + "/ajax/server_status", {
            "mode": "online",
        })
        .done(function(r){
            //do nothing
        })
        .fail(function(r){
            clearInterval(check);
            document.title = "Watcher";
            $thinker.style.maxHeight = '0%';
            $("div.message").css("opacity", 0);
            $("div#content").css("background-position", "50% 45%");
        })
    }, 3000);
});
