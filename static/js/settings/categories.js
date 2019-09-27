window.addEventListener("DOMContentLoaded", function(){
    category_template = document.querySelector("template#category_template").innerHTML;

    $categories_form = $("form#categories");

    each(document.querySelectorAll('i.mdi.radio'), function(r, i){
        r.addEventListener('click', function(){
            toggle_default()
        })
    })

});

function toggle_default(){
    var $i = event.target;
    if($i.getAttribute('value') == 'True'){
        return;
    } else {
        each(document.querySelectorAll('i.mdi.radio'), function(radio){
            radio.classList.remove('mdi-star');
            radio.classList.add('mdi-star-outline');
            radio.setAttribute('value', 'False');
        })
        $i.setAttribute('value', 'True');
        $i.classList.remove('mdi-star-outline');
        $i.classList.add('mdi-star');
    }
}

function edit_category(event, button){
    event.preventDefault();
    $i = button.children[0];
    $contents = $(button).closest('div.category').find('div.category_contents')
    if($i.classList.contains('mdi-chevron-down')){
        $i.classList.remove('mdi-chevron-down');
        $i.classList.add('mdi-chevron-up');
        $contents.slideDown();
    } else {
        $i.classList.remove('mdi-chevron-up');
        $i.classList.add('mdi-chevron-down');
        $contents.slideUp();
    }
}

function add_category(event){
    event.preventDefault();
    var $new_category = $(category_template);
    $new_category.find("i.c_box").each(function(){
        var $this = $(this);
        if(this.getAttribute("value") == "True"){
            this.classList.remove("mdi-checkbox-blank-outline");
            this.classList.add("mdi-checkbox-marked");
        }
    })
    $categories_form.append($new_category)
    $new_category.find('[data-toggle="tooltip"]').tooltip()
    $new_category.find('i.mdi.radio').click(toggle_default);
}

function delete_category(event, button){
    event.preventDefault();
    var $category = $(button).closest('div.category');
    $category.slideUp(500, function(){
        $category.remove();
        $rads = $('i.mdi.radio');
        if($rads.filter('[value="true"]').length == 0){
            $rads[0].click();
        }
    });
}

function _get_settings(){
    var categories = {};
    var blanks = false;

// Categories
    var required_fields = ['name', 'moverpath']

    each(document.querySelectorAll('div.category'), function(element){
        category = {};

        // Name
        var name = element.querySelector('input#name').value;
        if(!name){
            element.querySelector('input#name').classList.add('border-danger');
            blanks = true;
            return;
        }

        var moverpath = element.querySelector('input#moverpath').value;
        if(!moverpath){
            element.querySelector('input#moverpath').classList.add('border-danger');
            blanks = true;
            return;
        }
        category['moverpath'] = moverpath;

        // Word Lists
        each(element.querySelectorAll("div[data-sub-category='filters'] input"), function(input){
            category[input.id] = input.value;
        });

        categories[name] = category;
    });

    return {"Categories": categories};
}
