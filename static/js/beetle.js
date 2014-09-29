//(function(){
    var buis, ui;

    var LightStripView = Backbone.View.extend({
        render: function(){
            this.$el.text(this.model.get('sid'))
                    .append(_.map(this.model.get('html_colors'), function(color){
                return $("<span>").width(8).height(12).css("display", "inline-block").css('background-color', color);
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

        ui.on("change:graph_data", function(model, value){
            //console.log(value)
            if(!value.length){ return; }
            var $table = $("<table>");
            var header = _.keys(value[0]).sort();
            var $thead = $("<tr>").appendTo($table);
            _.each(header, function(h){
                $thead.append($("<th>").text(h));
            });
            _.each(value.reverse(), function(row){
                var $tr = $("<tr>").appendTo($table);
                _.each(header, function(h){
                    var dat = row[h] || 0;
                    var $td = $("<td>").appendTo($tr).width(101);
                    var $s = $("<span>").appendTo($td).height("100%").width(dat * $td.width() + 1).css("background-color", "#336633").css('display', 'inline-block');
                });
            });
            $(".levels").html($table);
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
