(function(){
    var buis, ui;
    /*
    Backbone.listenToOnce(root, "typesLoaded", function(){
        if(!root.Collections.BeetleUI){
            console.warn("No BeetleUI object loaded", root.Collections);
            $(".error").text("No BeetleUI object loaded");
            return;
        }
        console.log(root);

        buis = new root.Collections.BeetleUI();
        return;
        buis.fetch({
            success: function(){
                console.log(buis);
                ui = buis.at(0);
                Backbone.trigger("uiLoaded", ui);
            }
        });
    });
    */

    /*
    Backbone.listenToOnce(Backbone, "uiLoaded", function(ui){
        $(".content").text("Loaded UI.");

        ui.on("change:color", function(){
            $(".content").css("background-color", ui.get('color'));
        });

        //window.setTimeout(ui.fetch, 400);
    });
    */
})();
