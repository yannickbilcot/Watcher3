/* global url_base, notify_error, each, templates */
window.addEventListener("DOMContentLoaded", function(){
    templates = {
        newznab: document.querySelector("template#new_newznab").innerHTML,
        torznab: document.querySelector("template#new_torznab").innerHTML
    };
});

function test_indexer(event, button){
    event.preventDefault();
    button.setAttribute("disabled", true)

    var icon = button.children[0]
    var tr = button.parentElement.parentElement;

    var url = tr.querySelector("input[data-id=\"url\"").value;

    if(!url){
        return
    }

    icon.classList.remove("mdi-lan-pending");
    icon.classList.add("mdi-circle");
    icon.classList.add("animated");

    var api = tr.querySelector("input[data-id=\"api\"]").value;
    var mode = tr.parentElement.dataset.category;

    $.post(url_base + "/ajax/indexer_test", {
        "indexer": url,
        "apikey": api,
        "mode": mode
    })
    .done(function(response){
        if(response["response"] === true){
            $.notify({message: response["message"]})
        } else {
            $.notify({message: response["error"]}, {type: "danger"})
        }
    })
    .fail(notify_error)
    .always(function(){
        button.removeAttribute("disabled");
        icon.classList.remove("mdi-circle");
        icon.classList.add("mdi-lan-pending");
        icon.classList.remove("animated");
    });
}

function add_indexer(event, mode){
    event.preventDefault();
    document.querySelector(`tbody[data-category="${mode}"]`).insertAdjacentHTML("beforeend", templates[mode]);
}

function remove_indexer(event, button){
    event.preventDefault();
    var $tr = $(button).closest("tr");
    $tr.fadeOut(500, function(){
        $tr.remove()
    })
}

function _get_settings(){

    var settings = {};
    settings["NewzNab"] = {};
    settings["TorzNab"] = {};
    settings["Torrent"] = {};
    var blanks = false;

// INDEXERS['NEWZNAB']

    each(document.querySelectorAll("tbody[data-category='newznab'] > tr"), function(row, index){
        var $url = row.querySelector("input[data-id='url']");
        var url = $url.value;
        var $api = row.querySelector("input[data-id='api']");
        var api = $api.value;

        if(api && !url){
            $url.classList.add("border-danger");
            blanks = true;
            return false;
        } else if(api && url){
            var enabled = is_checked(row.querySelector("i.c_box"));
            settings["NewzNab"][index] = [url, api, enabled];
        }

    });

// INDEXERS['TORZNAB']

    each(document.querySelectorAll("tbody[data-category='torznab'] > tr"), function(row, index){
        var $url = row.querySelector("input[data-id='url']");
        var url = $url.value;
        var $api = row.querySelector("input[data-id='api']");
        var api = $api.value;

        if(api && !url){
            $url.classList.add("border-danger");
            blanks = true;
            return false;
        } else if(api && url){
            var enabled = is_checked(row.querySelector("i#enabled.c_box"));
            var no_year = is_checked(row.querySelector("i#no_year.c_box"));
            settings["TorzNab"][index] = [url, api, enabled, no_year];
        }
    });

// INDEXERS['TORRENT']

    each(document.querySelectorAll("form[data-category='torrent'] i.c_box"), function(checkbox){
        settings["Torrent"][checkbox.id] = is_checked(checkbox);
    });

// INDEXERS['PRIVATETORRENT']
    var privateTrackers = {};

    each(document.querySelectorAll("form[data-category='privtorrent'] > div"), function(dataelement){
        var key = dataelement.dataset.id;

        if(privateTrackers[key] == null){
            privateTrackers[key] = {};
        }

        var enabledelement = dataelement.querySelector("i.c_box");
        if(enabledelement != null){
            privateTrackers[key]["enabled"] = is_checked(enabledelement);
        }

        each(dataelement.querySelectorAll("input"), function(inputelement){
            var inputId = inputelement.dataset.id;
            privateTrackers[key][inputId] = inputelement.value;
        });
    });

    settings["PrivateTorrent"] = privateTrackers;

    if(blanks === true){
        return false;
    }

    return {"Indexers": settings}
}
