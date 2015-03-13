define([
    'jquery',
    'underscore',
    'backbone',
    'bootstrap'
], function($, _, Backbone) {
    var BreakModal = Backbone.View.extend({
        el: '#worth-break-modal',
        events: {
            submit: 'submit'
        },
        initialize: function() {
            this.$el.on('shown.bs.modal', function(e) {
                console.log('show');
                $.post('/api/breakmodal', {'start': 1}, function(data) {
                });
            });
            this.$el.on('hidden.bs.modal', function(e) {
                console.log('hide');
                $.put('/api/breakmodal', {'stop': 1}, function(data) {
                });
            });
        }
    });

    return BreakModal;
});
