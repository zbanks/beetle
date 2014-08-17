
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
        root.all.get('LightStrip').comparator = "sid";
        Backbone.trigger("do-refresh");
    });

    Backbone.listenToOnce(Backbone, "refreshed", function(ui){
        $(".content").text("Loaded UI.");
        var demo = window.demo = root.all.get('DemoLightApp').at(0);

        demo.on("change:tick", function(model, value){
            $(".content").text("Tick: " + value);
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
            root.all.get('DemoLightApp').fetch().fail(failFn).always(function(){
                root.all.get('LightStrip').fetch().fail(failFn).always(function(){
                    Backbone.trigger("refreshed");
                    window.setTimeout(function(){ Backbone.trigger('do-refresh'); }, root.get("backoff"));
                });
            });
        }
    });
