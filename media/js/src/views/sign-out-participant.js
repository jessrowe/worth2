define([
    'jquery',
    'underscore',
    'backbone'
], function($, _, Backbone) {
    var SignOutParticipantView = Backbone.View.extend({
        el: 'form.worth-sign-out-participant',
        events: {
            submit: 'submit'
        },
        submit: function(e) {
            e.preventDefault();
            var $target = $(e.currentTarget);
            var username = $target.find('input[name="facilitator_username"]')
                .val();
            var password = $target.find('input[name="facilitator_password"]')
                .val();
            $.ajax({
                type: 'POST',
                url: '/api/login_check/',
                data: {
                    facilitator_username: username,
                    facilitator_password: password
                },
                success: function(data) {
                    $target.find('.worth-errors').hide();
                    location = '/';
                },
                error: function(xhr, status, error) {
                    var msg = '';

                    if (xhr.responseJSON) {
                        if (xhr.responseJSON.login_check === false) {
                            msg = '<div>Incorrect password</div>';
                        } else {
                            for (var key in xhr.responseJSON) {
                                msg += '<div>' + xhr.responseJSON[key] +
                                    '</div>';
                            }
                        }
                    } else {
                        msg = error;
                    }

                    $target.find('.worth-errors').show().html(msg);
                }
            });
        }
    });

    return SignOutParticipantView;
});
