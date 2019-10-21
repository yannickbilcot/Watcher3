/*global each, echo, _, url_base, notify_error, modal_template, edit_modal, modal_dicts, $checkboxes, $movie_lis */
window.addEventListener("DOMContentLoaded", function(){
    $checkboxes = document.querySelectorAll("ul#movie_list i.c_box");
    $movie_lis = document.querySelectorAll("ul#movie_list > li");

    modal_template = document.querySelector("template#template_modal").innerHTML;
    edit_modal = document.querySelector("template#template_edit").innerHTML;

    echo.init({
        offsetVertical: 100,
        callback: function(element, op){
            element.style.opacity = 1;
        }
    });

    each($checkboxes, function(checkbox){
        checkbox.addEventListener("click", checkbox_switch);
    });

    modal_dicts = {
        "backlog_search": {
            title: "Backlog Search",
            body: "A full backlog search will be performed for selected movies. <br/> Be aware that this will consume one API hit per movie and may take several minutes to complete.",
            task: "_backlog_search"
        },
        "update_metadata": {
            title: "Update Metadata",
            body: "Metadata and posters will be re-downloaded for selected movies. <br/> This may take several minutes.",
            task: "_update_metadata"
        },
        "change_quality": {
            title: "Change Quality Profile",
            body: "Quality profiles will be changed for selected movies." + document.querySelector("template#quality_select").innerHTML,
            task: "_change_quality"
        },
        "change_category": {
            title: "Change Category",
            body: "Category will be changed for selected movies." + document.querySelector("template#category_select").innerHTML,
            task: "_change_category"
        },
        "reset": {
            title: "Reset Movies",
            body: "Selected movies will be reset.<br/>Quality Profile will be set to Default.<br/>Status will be set to wanted.<br/>Search Results will be removed (including Imports).<br/>This cannot be undone.",
            task: "_reset"
        },
        "remove": {
            title: "Remove Movies",
            body: "Selected movies will be removed from the library.<br/>This will not delete movie files.<br/>This cannot be undone.",
            task: "_remove"
        }
    }


});

function checkbox_switch(event){
    var checkbox = event.target;
    // turn on
    if(checkbox.getAttribute("value") === "False"){
        checkbox.setAttribute("value", "True");
        checkbox.classList.remove("mdi-checkbox-blank-outline");
        checkbox.classList.add("mdi-checkbox-marked");
    // turn off
    } else if(checkbox.getAttribute("value") === "True"){
        checkbox.setAttribute("value", "False");
        checkbox.classList.remove("mdi-checkbox-marked");
        checkbox.classList.add("mdi-checkbox-blank-outline");
    }
}

function select_all(){
    each($checkboxes, function(checkbox){
        checkbox.setAttribute("value", "False");
        checkbox_switch({target: checkbox});
    });
}

function select_none(){
    each($checkboxes, function(checkbox){
        checkbox.setAttribute("value", "True");
        checkbox_switch({target: checkbox});
    });
}

function select_inverse(){
    each($checkboxes, function(checkbox){
        checkbox_switch({target: checkbox});
    });
}

function select_attrib(event, button, key, value){
    event.preventDefault();

    each($movie_lis, function(movie){
        if(movie.dataset[key] === value){
            var c = movie.querySelector("i.c_box");
            c.classList.remove("mdi-checkbox-blank-outline");
            c.classList.add("mdi-checkbox-marked");
            c.setAttribute("value", "True");
        }
    });
}

function _selected_movies(){
    // Returns list of dicts of selected movies.
    // IE [{imdbid: 'tt1234567', tmdbid: '123456'}, {imdbid: 'tt7654321', tmdbid: '654321'}]
    var movies = [];
    each($checkboxes, function(checkbox){
        if(checkbox.getAttribute("value") === "True"){
            movies.push({
                "imdbid": checkbox.parentElement.dataset.imdbid,
                "tmdbid": checkbox.parentElement.dataset.tmdbid
            });
        }
    });
    return movies;
}

function show_modal(event, button, task){
    var selected_movies = _selected_movies();
    if(selected_movies.length === 0){
        $.notify({message: _("No movies are selected.")}, {type: "warning"});
        return false;
    }

    var $modal = $(format_template(modal_template, modal_dicts[task]));
    $modal.modal("show");
    // Destory modal after close
    $modal.on("hidden.bs.modal", function(modal){
        $modal.remove();
    });
}

function _manager_request(url, payload){
    /* Fires xhr ajax request for ajax/url_base with payload {movies: movies}
    url: str url tail to be appended to 'url_base/ajax/<url>'
    payload: dict of POST data

    Hides modal body text and shows progress bar.
    Hides modal footer and removes action button

    Sends XHR ajax request to server with payload.

    On progress:
        Adjusts progress bar width %.
        Shows error table and appends any errors if neccesary.

    When done, shows modal footer.
    */
    var $modal = document.getElementById("task_modal");
    var $modal_body = $modal.querySelector("p.body");
    var $progress = $modal.querySelector("div.progress");
    var $progress_bar = $modal.querySelector("div.progress-bar");
    var $error_table = $modal.querySelector(".modal-body > table");
    var $error_table_body = $error_table.querySelector("tbody");
    var $close_button = $modal.querySelector("div.modal-header button");

    $close_button.setAttribute("disabled", true);
    $modal_body.style.maxHeight = "0%";
    $progress.style.maxHeight = "100%";
    $modal.querySelector("div.modal-footer > button").setAttribute("disabled", true);

    var movie_count = payload["movies"].length;
    payload["movies"] = JSON.stringify(payload["movies"]);

    var last_response_len = false;
    $.ajax(url_base + "/ajax/" + url, {
        method: "POST",
        data: payload,
        xhrFields: {
            onprogress: function(e){
                var response_update;
                var response = e.currentTarget.response;
                if(last_response_len === false){
                    response_update = response;
                    last_response_len = response.length;
                } else {
                    response_update = response.substring(last_response_len);
                    last_response_len = response.length;
                }

                response = JSON.parse(response_update);

                var progress = Math.round((parseInt(response["index"]) / movie_count) * 100);
                $progress_bar.style.width = (progress + "%");
                $progress_bar.innerText = `${response["index"]} / ${movie_count}`;

                if(response["response"] === false){
                    $error_table.style.display = "block";
                    $error_table_body.innerHTML += `<tr>
                                                        <td> ${response["imdbid"]} </td>
                                                        <td> ${response["error"]} </td>
                                                    </tr>`;
                }
            }
        }
    })
    .done(function(){
        $modal_body.innerText = "Finished -- Refresh page to see changes.";
        $modal_body.style.maxHeight = "100%";
    })
    .fail(notify_error)
    .always(function(){
        $close_button.removeAttribute("disabled");
    });
}

function begin_task(event, button, task){
    window[task]();
}

function _backlog_search(event, elem){
    var movies = _selected_movies();
    _manager_request("manager_backlog_search", {"movies": movies});
}

function _update_metadata(event, elem){
    // Preps call to _manager_request
    var movies = _selected_movies();
    _manager_request("manager_update_metadata", {"movies": movies});
}

function _change_quality(event, elem){
    // Preps call to _manager_request
    var movies = _selected_movies();

    var quality = document.querySelector("#task_modal .modal-body select#quality").value;
    if(!quality){
        $.notify({message: _("Select a new Quality Profile.")}, {type: "warning"});
        return;
    }

    _manager_request("manager_change_quality", {"movies": movies, "quality": quality});
}

function _change_category(event, elem){
    // Preps call to _manager_request
    var movies = _selected_movies();

    var category = document.querySelector("#task_modal .modal-body select#category").value;
    if(!category){
        $.notify({message: _("Select a new Category.")}, {type: "warning"});
        return;
    }

    _manager_request("manager_change_category", {"movies": movies, "category": category});
}

function _reset(event, elem){
    // Preps call to _manager_request
    var movies = _selected_movies();
    _manager_request("manager_reset_movies", {"movies": movies});
}

function _remove(event, elem){
    // Preps call to _manager_request
    var movies = _selected_movies();
    _manager_request("manager_remove_movies", {"movies": movies});
}

function edit_movie(event, button){
    var tmdbid = button.parentElement.dataset.tmdbid;

    $.post(url_base + "/ajax/single_movie_details", {
        key: "tmdbid",
        value: tmdbid
    })
    .done(function(movie){
        if(movie == {}){
            $.notify({message: "Unable to read movie from database."}, {type: "danger", delay: 0});
            return;
        }

        var $modal = $(format_template(edit_modal, movie));

        $modal.modal("show");
        // Destory modal after close
        $modal.on("hidden.bs.modal", function(modal){
            $modal.remove();
        });

    });
}


function save_movie_details(event, button, tmdbid){
    var data = {};
    var date_format = RegExp(/\d{4}-\d{2}-\d{2}/);

    each(document.querySelectorAll("table#edit_movie_table input"), function(input){
        data[input.dataset.id] = _parse_input(input);
    });

    if(data.release_date && !date_format.test(data.release_date) || data.media_release_date && !date_format.test(data.media_release_date)){
        $.notify({message: "Dates must match format YYYY-MM-DD"}, {type: "danger", delay: 0});
        return;
    }

    var $i = button.children[0];
    $i.classList.remove("mdi-content-save");
    $i.classList.add("mdi-circle");
    $i.classList.add("animated");

    data["tmdbid"] = tmdbid;

    $.post(url_base + "/ajax/set_movie_details", {
        data: JSON.stringify(data)
    })
    .done(function(response){
        if(response["response"] === true){
            $.notify({message: response["message"]});
        } else {
            $.notify({message: response["error"]}, {type: "danger", delay: 0});
        }
    })
    .fail(notify_error)
    .always(function(){
        $i.classList.remove("mdi-circle");
        $i.classList.add("mdi-content-save");
        $i.classList.remove("animated");
    });

}

function _parse_input(input){
    // Parses input elements into their respective type while
    //     modifying for min/max values of numbers, etc
    // input: html node of input
    //
    // Returns declared type of input
    if(input.type === "number"){
        var min = parseInt(input.min || 0);
        var val = Math.max(parseInt(input.value), min);
        return val || min;
    } else if (input.value === ""){
        return null;
    } else {
        return input.value;
    }
}
