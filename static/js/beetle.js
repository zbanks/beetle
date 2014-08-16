//(function(){
    var buis, ui;

    var LightStripView = Backbone.View.extend({
        render: function(){
            this.$el.text(this.model.get('sid'))
                    .append(_.map(this.model.get('html_colors'), function(color){
                return $("<span>").width(20).height(15).css("display", "inline-block").css('background-color', color);
            }));
            return this;
        }
    });

    var LightStripsView = Backbone.View.extend({
        render: function(){
            this.$el.empty().append(this.collection.map(function(strip){
                var $stripEl = $("<div>");
                var v = new LightStripView({ el: $stripEl, model: strip});
                v.render();
                return $stripEl;
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
        root.all.get('LightStrip').comparator = "sid";
        Backbone.trigger("do-refresh");
    });

    Backbone.listenToOnce(Backbone, "refreshed", function(ui){
        $(".content").text("Loaded UI.");
        window.ui = ui = root.all.get("BeetleUI").at(0);
        window.ui = ui;

        ui.on("change:color", function(){
            $(".content").css("background-color", ui.get('color'));
        })

        ui.on("change:tick", function(model, value){
            $(".content").text("Tick: " + value);
        });

        ui.on("change:spectrum", function(model, value){
            $(".spectrum").text(value);
        });

        lsv = new LightStripsView({ collection: root.all.get("LightStrip"), el: "div.strip" });
        Backbone.listenTo(root.all.get("LightStrip"), "change", function(){
            lsv.render();
        });
        lsv.render();

    });

    Backbone.on("do-refresh", function(){
        if(!window.noRefresh){
            var failFn = function(response){
                var backoff = root.get("backoff");
                backoff = Math.min(backoff * 2, 10000);
                root.set("backoff", backoff);
                Backbone.trigger("lost-connection");
                return response;
            };
            root.all.get('BeetleUI').fetch().fail(failFn).always(function(){
                root.all.get('LightStrip').fetch().fail(failFn).always(function(){
                    Backbone.trigger("refreshed");
                    window.setTimeout(function(){ Backbone.trigger('do-refresh'); }, root.get("backoff"));
                });
            });
        }
    });
//})();
