$(document).ready(function () {
    $select_usenet = $("select#usenet_client");
    $select_torrent = $("select#torrent_client");

    $usenet_clients = $("div#usenet_client_settings > div");
    $torrent_clients = $("div#torrent_client_settings > div");

    // Set selects on page load
    $usenet_clients.each(function(){
        var $this = $(this);
        if($this.data("enabled") == "True"){
            $this.removeClass("hidden");
            $select_usenet.val($this.attr("id"))
            return false;
        }
    })
    $torrent_clients.each(function(){
        var $this = $(this);
        if($this.data("enabled") == "True"){
            $this.removeClass("hidden");
            $select_torrent.val($this.attr("id"))
            return false;
        }
    })


    $select_usenet.change(function(){
        var $this = $(this);
        var val = $this.val();

        $usenet_clients.slideUp();
        if(val){
            $usenet_clients.filter("#" +val).slideDown();
        }

    });

    $select_torrent.change(function(){
        var $this = $(this);
        var val = $this.val();

        $torrent_clients.slideUp();
        if(val){
            $torrent_clients.filter("#" +val).slideDown();
        }

    });
});


function test_connection(event, elem, client){
    event.preventDefault();

    $this = $(elem);
    var original_contents = $this[0].innerHTML;
    $this.html(`<i class="mdi mdi-circle-outline animated"></i>`)

    var $inputs = $("div#"+client+" input");

    // Gets entered info, not save info
    var settings = {}
    $inputs.each(function(){
        var $this = $(this);
        if($this.attr('type') == 'number'){
            settings[$this.data('id')] = parseInt($this.val())
        } else {
            settings[$this.data('id')] = $this.val()
        }
    });

    settings = JSON.stringify(settings);

    $.post(url_base + "/ajax/test_downloader_connection", {
        "mode": client,
        "data": settings
    })
    .done(function(r){
        var response = JSON.parse(r);
        $this.html(original_contents);

        if(response["response"] == true){
            $.notify({message: `${response["message"]}`});
        } else {
            $.notify({message: `${response["error"]}`}, {type: "danger"})
        }
    })
}


function _get_settings(){

    var settings = {};
    settings["Sources"] = {};
    settings["Torrent"] = {};
    settings["Usenet"] = {};
    var blanks = false;

// DOWNLAODER['USENET']

    $("div#usenet_client_settings > div").each(function(){
        var $this = $(this);
        var client = $this.attr("id");
        settings['Usenet'][client] = {};

        if($this.css("display") != "none"){
            settings['Usenet'][client]['enabled'] = true;
        } else {
            settings['Usenet'][client]['enabled'] = false;
        }

        $this.find("i.c_box").each(function(){
            var $this = $(this);
            settings['Usenet'][client][$this.data("id")] = is_checked($this);
        })

        $this.find(":input:not(button)").each(function(){
            var $this = $(this);

            if($this.attr("type") == "number"){
                settings['Usenet'][client][$this.data("id")] = parseInt($this.val()) || "";
            }
            else{
                settings['Usenet'][client][$this.data("id")] = $this.val();
            }
        });
    });

// DOWNLAODER['TORRENT']

    $("div#torrent_client_settings > div").each(function(){
        var $this = $(this);
        var client = $this.attr("id");
        settings['Torrent'][client] = {};

        if($this.css("display") != "none"){
            settings['Torrent'][client]['enabled'] = true;
        } else {
            settings['Torrent'][client]['enabled'] = false;
        }

        $this.find("i.c_box").each(function(){
            var $this = $(this);
            settings['Torrent'][client][$this.data("id")] = is_checked($this);
        })

        $this.find(":input:not(button)").each(function(){
            var $this = $(this);

            if($this.attr("type") == "number"){
                settings['Torrent'][client][$this.data("id")] = parseInt($this.val()) || "";
            }
            else{
                settings['Torrent'][client][$this.data("id")] = $this.val();
            }
        });
    });

// DOWNLOADER['SOURCES']

    if($("select#usenet_client").val()){
        settings['Sources']['usenetenabled'] = true;
    } else {
        settings['Sources']['usenetenabled'] = false;
    }

    if($("select#torrent_client").val()){
        settings['Sources']['torrentenabled'] = true;
    } else {
        settings['Sources']['torrentenabled'] = false;
    }

    return {"Downloader": settings}
}