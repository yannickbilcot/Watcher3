/*global each, $progress, $progress_bar, $progress_text, $source_select, $quality_select, $category_select, set_stepper, is_checked, url_base, notify_error */
function connect(event, elem){
    event.preventDefault();

    var $address_input = document.querySelector("input#address");
    if(!$address_input.value){
        $address_input.classList.add("border-danger");
        return false;
    }

    var $port_input = document.querySelector("input#port");
    if(!$port_input.value){
        $port_input.classList.add("border-danger");
        return false;
    }

    var $apikey_input = document.querySelector("input#apikey");
    if(!$apikey_input.value){
        $apikey_input.classList.add("border-danger");
        return false;
    }

    var url = $address_input.value + ":" + $port_input.value;

    $("form#connect").slideUp();
    $progress_bar.style.width = "0%";
    $progress.style.maxHeight = "100%";

    var $wanted_div = document.querySelector("div#wanted_movies");
    var $wanted_table = document.querySelector("div#wanted_movies table > tbody");
    var $finished_div = document.querySelector("div#finished_movies");
    var $finished_table = document.querySelector("div#finished_movies table > tbody");

    $.post(url_base + "/ajax/get_cp_movies", {
        "url": url,
        "apikey": $apikey_input.value
    })
    .done(function(response){

        if(response["response"] !== true){
            $("div#server_info").slideDown();
            $("a#scan_library").slideDown();
            $.notify({message: response["error"]}, {type: "warning"});
            return false;
        }

        if(response["movies"].length === 0){
            document.getElementById("no_imports").classList.remove("hidden");
        }

        each(response["movies"], function(movie, index){
            var source_select = $source_select.cloneNode(true);
            source_select.querySelector(`option[value="${movie["resolution"]}"]`).setAttribute("selected", true);
            var category_select = $category_select.cloneNode(true);
            if(movie["category"]){
                category_select.querySelector(`option[value="${movie["category"]}"]`).setAttribute("selected", true);
            }

            var $row;
            if(movie["status"] === "Disabled"){
                $row = $(`<tr>
                                <td>
                                    <i class="mdi mdi-checkbox-marked c_box", value="True"></i>
                                </td>
                                <td>
                                    ${movie["title"]}
                                </td>
                                <td>
                                    ${movie["imdbid"]}
                                </td>
                                <td class="resolution">
                                    ${source_select.outerHTML}
                                </td>
                                <td class="category">
                                    ${category_select.outerHTML}
                                </td>
                            </tr>`)[0];
                $row.dataset.movie = JSON.stringify(movie);
                $finished_table.innerHTML += $row.outerHTML;
                $finished_div.classList.remove("hidden");
            } else {
                $row = $(`<tr>
                                <td>
                                    <i class="mdi mdi-checkbox-marked c_box", value="True"></i>
                                </td>
                                <td>
                                    ${movie["title"]}
                                </td>
                                <td>
                                    ${movie["imdbid"]}
                                </td>
                                <td class="profile">
                                    ${$quality_select.outerHTML}
                                </td>
                                <td class="category">
                                    ${$category_select.outerHTML}
                                </td>
                            </tr>`)[0];
                $row.dataset.movie = JSON.stringify(movie);
                $wanted_table.innerHTML += $row.outerHTML;
                $wanted_div.classList.remove("hidden");
            }

            $progress_bar.style.width = Math.round(index / response["movies"].length * 100);
        });

        set_stepper("import");
        document.getElementById("button_import").classList.remove("hidden");

        $("form#import").slideDown();
        window.setTimeout(function(){
            $progress.style.maxHeight = "0%";
            $progress_text.innerText = "";
            $progress_bar.style.width = "0%";
        }, 500);

    })
    .fail(notify_error);
}

function start_import(event, elem){
    event.preventDefault();

    var wanted_movies = [];
    var finished_movies = [];

    each(document.querySelectorAll("div#finished_movies table > tbody > tr "), function(row, index){
        if(!is_checked(row.querySelector("i.c_box"))){
            return
        }

        var movie = JSON.parse(row.dataset.movie);

        movie["resolution"] = row.querySelector("select.source_select").value;
        movie["category"] = row.querySelector("select.category_select").value;
        finished_movies.push(movie);
    });

    each(document.querySelectorAll("div#wanted_movies table > tbody > tr "), function(row, index){
        if(!is_checked(row.querySelector("i.c_box"))){
            return
        }

        var movie = JSON.parse(row.dataset.movie);
        movie["quality"] = row.querySelector("select.quality_select").value;
        movie["category"] = row.querySelector("select.category_select").value;
        wanted_movies.push(movie);
    });

    $("form#import").slideUp(600);
    $progress_bar.style.width = "0%";
    $progress.style.maxHeight = "100%";

    var $success_div = document.querySelector("div#import_success");
    var $success_table = document.querySelector("div#import_success table > tbody");
    var $error_div = document.querySelector("div#import_error");
    var $error_table = document.querySelector("div#import_error table > tbody");

    var last_response_len = false;
    $.ajax(url_base + "/ajax/import_cp_movies", {
        method: "POST",
        data: {"wanted": JSON.stringify(wanted_movies), "finished": JSON.stringify(finished_movies)},
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
                var r = JSON.parse(response_update), row;

                if(r["response"] === true){
                    $success_div.classList.remove("hidden");
                    row = `<tr>
                                    <td>${r["movie"]["title"]}</td>
                                    <td>${r["movie"]["imdbid"]}</td>
                                </tr>`;
                    $success_table.innerHTML += row;
                } else {
                    $error_div.slideDown();
                    row = `<tr>
                                    <td>${r["movie"]["title"]}</td>
                                    <td>${r["error"]}</td>
                                </tr>`;
                    $error_table.innerHTML += row;
                }

                var progress_percent = Math.round(parseInt(r["progress"][0], 10) / parseInt(r["progress"][1], 10) * 100);
                $progress_text.innerText = `${r["progress"][0]} / ${r["progress"][1]} ${r["movie"]["title"]}.`;
                $progress_bar.style.width = (progress_percent + "%");

            }
        }
    })
    .done(function(data){
        set_stepper("review");
        $("form#review").slideDown();
        window.setTimeout(function(){
            $progress.style.maxHeight = "0%";
            $progress_text.innerText = "";
            $progress_bar.style.width = "0%";
        }, 500)
    })
    .fail(notify_error);
}
