/*global each, category_template, $categories_form */
window.addEventListener("DOMContentLoaded", function(){
    language_template = document.querySelector("template#language_template").innerHTML;
    $categories_form = $("form#languages tbody");
});

function add_language(event){
    event.preventDefault();
    var $new_language = $(language_template);
    $categories_form.append($new_language);
    $new_language.find("[data-toggle=\"tooltip\"]").tooltip();
}

function delete_language(event, button){
    event.preventDefault();
    var $tr = $(button).closest('tr');
    $tr.fadeOut(500, function(){
                        $tr.remove();
                     });
}

function _get_settings(){
    var langs = {};
    var blanks = false;

// Categories
    var required_fields = ["code", "names"];

    each(document.querySelectorAll("#languages tbody tr"), function(element){
        // Name
        var code = element.querySelector("input[data-id=\"code\"]").value;
        if(!code || !code.match(/^[a-z]{2}-[A-Z]{2}$/)){
            element.querySelector("input[data-id=\"code\"]").classList.add("border-danger");
            blanks = true;
            return;
        }
        var names = element.querySelector("input[data-id=\"names\"]").value;
        if(!names){
            element.querySelector("input[data-id=\"names\"]").classList.add("border-danger");
            blanks = true;
            return;
        }

        langs[code] = names;
    });

    if(blanks === true){
        return false;
    }

    return {"Languages": langs};
}
