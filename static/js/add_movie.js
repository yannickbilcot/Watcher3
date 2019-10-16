/* global url_base, notify_error, each */
window.addEventListener("DOMContentLoaded", function(){
    details_template = document.querySelector("template#details_template").innerHTML;
    item_template = document.querySelector("template#movie_template").innerHTML;

    $search_input = document.querySelector("div#search_bar input");
    $search_button = document.querySelector("div#search_bar #search_button");
    $movie_list = document.getElementById("movies");
    $thinker = document.getElementById("thinker");
    $similar_select = document.getElementById("movie_names");

    $search_input.addEventListener("keyup", function(event){
        if(event.keyCode === 13){
            search(event, $search_button);
        }
    });

    $pills = $("ul.nav-pills a");
    $pills.on("shown.bs.tab", function(e){
        clear_movies();
        if(e.target.dataset.cat === "search"){
            return;
        } else if(e.target.dataset.cat === "similar"){
            if($similar_select.children.length === 0){
                populate_movie_select();
            }
            return;
        }
        load_suggestions(e.target.dataset.cat);
    });

    cache = {};
    similar_cache = {};
});

function search(event, button){
    // Sends term to ajax handler
    event.preventDefault();

    clear_movies();
    button.setAttribute("disabled", true);

    var search_term = $search_input.value;
    if(search_term == ""){
        return false;
    }
    $thinker.style.maxHeight = "100%";

    $movie_list.style.maxHeight = "0%";
    $movie_list.innerHTML = "";

    var movie_results_dict = {};

    $.post(url_base + "/ajax/search_tmdb", {
        "search_term": search_term
    })
        .done(function(results){
            display_movies(results);
        })
        .fail(notify_error)
        .always(function(){
            button.removeAttribute("disabled");
            $thinker.style.maxHeight = "0%";
        });
}

function load_suggestions(category, tmdbid = null){
    /* Loads and displays TMDB categories
    category (str): name of cat to load

    If possible, caches and loads cached page.

    */

    if(["popular", "now_playing", "top_rated", "upcoming"].includes(category) && cache[category]){
        display_movies(cache[category]);
        return;
    }

    if(category === "similar"){
        clear_movies();
        tmdbid = $similar_select.value;
        if(similar_cache[tmdbid]){
            display_movies(similar_cache[tmdbid]);
            return;
        }
    }

    $pills.addClass("disabled");
    $thinker.style.maxHeight = "100%";

    $.post(url_base + "/ajax/tmdb_categories", {
        cat: category,
        tmdbid: tmdbid
    })
        .done(function(results){
            display_movies(results);
            if(category === "similar"){
                similar_cache[tmdbid] = results;
            } else {
                cache[category] = results;
            }
        })
        .fail(notify_error)
        .always(function(){
            $thinker.style.maxHeight = "0%";
            $pills.removeClass("disabled");
        });
}

function clear_movies(){
    $movie_list.style.maxHeight = "0%";
    $movie_list.innerHTML = "";
}

function display_movies(movies){
    var status_colors = {
        Finished: "success",
        Snatched: "primary",
        Found: "warning",
        Bad: "danger",
        Wanted: "wanted",
        Available: "available",
        Waiting: "waiting",
    };
    each(movies, function(movie, index){
        var poster_path;
        if(movie["poster_path"] != null){
            poster_path = movie["poster_url"] = "http://image.tmdb.org/t/p/w300" + movie["poster_path"];
        } else {
            poster_path = movie["poster_url"] = url_base + "/static/images/missing_poster.jpg";
        }

        movie["year"] = (movie["release_date"] || "N/A").slice(0, 4);

        var template_dictionary = {
            "img_url": poster_path,
            "title": movie["title"],
            "year": movie["year"]
        };
        if(movie["status"]){
            template_dictionary["translated_status"] = _(movie["status"]);
            template_dictionary["status_color"] = status_colors[movie["status"]];
        }

        var $li = format_template(item_template, template_dictionary);
        if(movie["status"]){
            $li.querySelector('.btn-group').remove();
        } else {
            $li.querySelector('.card-body.status').remove();
        }
        $li.dataset.movie = JSON.stringify(movie);
        $movie_list.innerHTML += $li.outerHTML;
    });

    $movie_list.style.maxHeight = "200%";
}

function populate_movie_select(){
    $.post(url_base + "/ajax/quick_titles", {})
        .done(function(titles){
            each(titles, function(title, index){
                $similar_select.innerHTML += `<option value="${title[1]}">
                                          ${title[0]}
                                          </option>`;
            });
        })
        .fail(notify_error)
        .always(function(){
            $thinker.style.maxHeight = "0%";
            $pills.removeClass("disabled");
        });
}

function add_movie_settings(event, button){
    event.preventDefault();
    $contents = $(button).closest("div.card").find("div.add-movie-form");
    if($contents.is(":visible")){
        $contents.slideUp();
    } else {
        $contents.slideDown();
    }
}

function select_item(event, item){
    event.preventDefault();
    $dropdown = $(item).closest("div.dropdown-menu");
    $dropdown.find(".mdi.mdi-star").removeClass("mdi mdi-star");
    $(item).addClass("mdi mdi-star");
    $dropdown.parent().find("button[data-toggle=\"dropdown\"]").text($(item).text());
}

function add_movie(event, elem, modal = false){
    var $this = $(elem), data;

    var $add_button = $this;
    add_oc = $add_button.html();
    $add_button.html("<i class='mdi mdi-circle animated'></i>");
    $add_button.attr("disabled", true);

    if(modal){
        data = $modal.data("movie");
    } else {
        data = $this.closest("li").data("movie");
    }
    var $form = $this.closest(".add-movie-form");
    data["quality"] = $form.find(".quality_profile").text().trim();
    data["category"] = $form.find(".category").text().trim();

    var title = data["title"];

    $.post(url_base + "/ajax/add_wanted_movie", {"data": JSON.stringify(data)})
        .done(function(response){
            if(response["response"] === true){
                $.notify({message: response["message"]});
            } else {
                $.notify({message: response["error"]}, {type: "warning"});
            }
        })
        .fail(notify_error)
        .always(function(){
            $add_button.html(add_oc);
            $add_button.removeAttr("disabled");
        });
}

function show_details(event, elem){
    event.preventDefault();
    var $this = $(elem);
    var movie = $this.closest("li").data("movie");

    movie["trailer"] = "";

    var modal = format_template(details_template, movie);
    $modal = $(modal);
    $modal.data("movie", movie);
    $modal.modal("show");
    $modal.on("hidden.bs.modal", function(){
        $modal.remove();
    });

    $.post(url_base + "/ajax/get_trailer", {
        "title": movie["title"],
        "year": movie["title"]
    })
        .done(function(r){
            document.querySelector("#trailer + preload-icon").classList.remove("loading");
            if(r){
                $modal.find("iframe#trailer").attr("src", `https://www.youtube.com/embed/${r}?&showinfo=0`);
            } else {
                document.getElementById("trailer").classList.add("unavailable");
            }
        });
}
