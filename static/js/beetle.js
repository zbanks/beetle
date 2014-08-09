//(function(){
    var buis, ui;

    var LightStripView = Backbone.View.extend({
        render: function(){
            this.$el.empty().append(_.map(this.model.get('colors'), function(color){
                return $("<span>").css('background-color', color).width(10).height(10);
            }));
            return this;
        }
    });

    Backbone.listenToOnce(root, "typesLoaded", function(){
        if(!root.Collections.BeetleUI){
            console.warn("No BeetleUI object loaded", root.Collections);
            $(".error").text("No BeetleUI object loaded");
            return;
        }
        console.log(root);

        buis = new root.Collections.BeetleUI();
        buis.fetch({
            success: function(){
                console.log(buis);
                ui = buis.at(0);
                Backbone.trigger("uiLoaded", ui);
            }
        });
    });

    Backbone.listenToOnce(Backbone, "uiLoaded", function(ui){
        $(".content").text("Loaded UI.");
        window.ui = ui;

        ui.on("change:color", function(){
            $(".content").css("background-color", ui.get('color'));
        }).trigger("change:color");

        ui.on("change:tick", function(model, value){
            $(".content").text("Tick: " + value);

        });

        Backbone.trigger("do-refresh");
    });

    Backbone.listenTo("do-refresh", function(){
        if(!window.noRefresh){
            root.all.get('BeetleUI').fetch();
            root.all.get('LightStrip').fetch();
            window.setTimeout(function(){ Backbone.trigger('do-refresh'); }, 500);
        }
    });
//})();
