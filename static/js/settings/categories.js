/*global each, category_template, $categories_form */
window.addEventListener("DOMContentLoaded", function(){
    category_template = document.querySelector("template#category_template").innerHTML;
    $categories_form = $("form#categories");
});

function edit_category(event, button){
    event.preventDefault();
    var $i = button.children[0];
    var $contents = $(button).closest("div.category").find("div.category_contents");
    if($i.classList.contains("mdi-chevron-down")){
        $i.classList.remove("mdi-chevron-down");
        $i.classList.add("mdi-chevron-up");
        $contents.slideDown();
    } else {
        $i.classList.remove("mdi-chevron-up");
        $i.classList.add("mdi-chevron-down");
        $contents.slideUp();
    }
}

function add_category(event){
    event.preventDefault();
    var $new_category = $(category_template);
    $categories_form.append($new_category);
    $new_category.find("[data-toggle=\"tooltip\"]").tooltip();
}

function delete_category(event, button){
    event.preventDefault();
    var $category = $(button).closest("div.category");
    $category.slideUp(500, function(){
        $category.remove();
    });
}

function _get_settings(){
    var categories = {};
    var blanks = false;

// Categories
    var required_fields = ["name", "moverpath"];

    each(document.querySelectorAll("div.category"), function(element){
        var category = {};

        // Name
        var name = element.querySelector("input#name").value;
        if(!name){
            element.querySelector("input#name").classList.add("border-danger");
            blanks = true;
            return;
        }

        var moverpath = element.querySelector("input#moverpath").value;
        if(!moverpath){
            element.querySelector("input#moverpath").classList.add("border-danger");
            blanks = true;
            return;
        }
        category["moverpath"] = moverpath;

        // Word Lists
        each(element.querySelectorAll("div[data-sub-category='filters'] input"), function(input){
            category[input.id] = input.value;
        });

        categories[name] = category;
    });

    return {"Categories": categories};
}
